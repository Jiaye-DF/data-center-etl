# ETL Framework(`etl/`)

AWS Glue Job 的 ETL framework 骨架:以**設定驅動的動態派工**執行各 job,搭配共用的 config 載入器 / logger / utils / transform 基底。本骨架只含共用層,不含具體來源 reader、目標 writer 與各 job 實作(見 task-002~005)。

## 目錄結構

```
etl/
├── main.py                 # Glue Job 入口,動態派工到 jobs.<name>_job
├── requirements.txt        # 依賴版本鎖定(pyspark / PyYAML)
├── common/
│   ├── config.py           # yaml 設定載入器(集中解析 config/*.yaml + mapping/*.yaml)
│   ├── logger.py           # 結構化 logging(ISO 8601 +08:00 時戳)
│   └── utils.py            # 純函式小工具(now_tw / 命名正規化)
├── transforms/
│   └── common.py           # 共用轉換 helper(trim / 型別轉換 / null 正規化)
├── jobs/                   # 各 job 模組(<name>_job.py,後續 task 落地)
├── tests/                  # 單元測試
└── config/
    ├── job_config.yaml     # job 清單(name → jobs.<name>_job)
    ├── table_config.yaml   # 來源 / 目標 database 與 schema 設定
    └── mapping/            # 欄位對應 yaml(後續 task 落地)
```

## 設定驅動的動態派工原理

`main.py` **不**以 if/elif 硬列 job 名稱,而是:

1. `common/config.py` 讀 `config/job_config.yaml` 取出允許的 job 清單。
2. 由 `--job <name>` 指定要跑的 job。
3. `importlib.import_module(f"jobs.{name}_job")` 動態載入模組,呼叫其 `run(spark, config)`。

因此**新增 job 只需**:在 `config/job_config.yaml` 加一筆 `name`,並建立 `jobs/<name>_job.py`(內含 `run(spark, config)`),**無需回頭改 `main.py`**。

## 本地執行

```bash
# 於 repo 根目錄
pip install -r etl/requirements.txt

# 執行指定 job(需對應 jobs/<name>_job.py 已存在)
python etl/main.py --job ds_migrate
```

`main.py` 內對 `pyspark` 的 import 放在函式內,語法檢查與載入設定不需先裝 pyspark。

## 規範底線

- **輸出語言**:繁體中文(註解 / docstring / 文件)。
- **時區**:一律 UTC+8 / Asia/Taipei;取現在時間用 `utils.now_tw()`,禁 `datetime.utcnow()` / naive `now()`。
- **機密走 env**:DB / S3 憑證禁寫入 yaml 或程式碼字面值(見 `docs/Design-Base/00-overview/02-secrets.md`)。

---

## 部署到 S3 + Glue Job 建置 + 端到端驗證

> **本章為手動 runbook**:以下 `aws` / `psql` 指令需要**真實 AWS 環境與 RDS 連線**才能執行,
> 無法在無憑證的 CI / agent 環境跑。腳本本身(`deploy_s3.sh` / `verify_target_db.sql`)已做語法與安全檢查,
> 但「S3 上傳確認 / Glue job SUCCEEDED / 目標表筆數 > 0 / 每欄 Comment 非空」屬**人工驗收**,
> 需由具 AWS 憑證的人於部署環境依本章逐步執行。

### 前置:環境變數與憑證

所有 bucket / job / DB 連線一律走 env,**禁**寫進 repo(對齊 `00-overview/02-secrets.md`)。

| 類別 | 變數 | 說明 |
| --- | --- | --- |
| S3 部署 | `ETL_BUCKET` | 目標 S3 bucket 名(必填,缺則 `deploy_s3.sh` fail-fast) |
| S3 部署 | `ETL_PREFIX` | S3 前綴,預設 `etl/`(可省略) |
| 來源 DB | `SOURCE_DB_HOST` / `SOURCE_DB_PORT` / `SOURCE_DB_NAME` / `SOURCE_DB_USER` / `SOURCE_DB_PASSWORD` | 來源 `erp_migration_test`(Glue Job 執行時讀取) |
| 目標 DB | `TARGET_DB_HOST` / `TARGET_DB_PORT` / `TARGET_DB_NAME` / `TARGET_DB_USER` / `TARGET_DB_PASSWORD` | 目標 `erp_etl_hub_test`(writer 寫入用,見 `common/writer.py`) |
| Glue | `GLUE_JOB_NAME` | Glue Job 名稱(建立 / 觸發 / 查詢時引用) |

- **AWS 憑證**:本機 `aws configure`(access key / region),或在 Glue / EC2 使用 **IAM Role**(建議)。
- **JDBC 憑證禁進 repo**:來源 / 目標 DB 的 JDBC 帳密建議存 **AWS Secrets Manager**,並以 **Glue Connection** 綁定 VPC / Subnet / Security Group;Glue Job 執行時由 Connection 注入,而非寫死在指令或 yaml。

### 步驟 1:上傳 etl/ 到 S3

```bash
# 於 repo 根目錄(Git Bash)
export ETL_BUCKET=my-etl-bucket      # 換成實際 bucket
export ETL_PREFIX=etl/               # 可省略,預設 etl/
bash etl/scripts/deploy_s3.sh
```

`deploy_s3.sh` 以 `aws s3 sync` 上傳 `etl/`,排除 `tests/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`;
**不加** `--delete`(不刪 S3 既有物件)。上傳後 `main.py` 位於 `s3://$ETL_BUCKET/$ETL_PREFIX/main.py`。

驗證上傳:

```bash
aws s3 ls "s3://$ETL_BUCKET/" --recursive | grep -q "main.py" && echo "main.py 已上傳"
```

### 步驟 2:建立 / 設定 Glue Job

Glue Job 的 Script location 指向步驟 1 上傳的 `main.py`。以 CLI 範例(Console 亦可,對應欄位相同):

```bash
aws glue create-job \
  --name "$GLUE_JOB_NAME" \
  --role "arn:aws:iam::<ACCOUNT_ID>:role/<GlueServiceRole>" \
  --command '{
    "Name": "glueetl",
    "PythonVersion": "3",
    "ScriptLocation": "s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'main.py"
  }' \
  --glue-version "4.0" \
  --connections '{"Connections":["<your-glue-connection-name>"]}' \
  --default-arguments '{
    "--extra-py-files": "s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'common/,s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'jobs/,s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'transforms/",
    "--additional-python-modules": "pyyaml",
    "--job-language": "python"
  }'
```

重點:

- **`--additional-python-modules pyyaml`**:`common/config.py` 需要 PyYAML;Glue 執行環境預設**不含** PyYAML,務必帶上,否則 import 失敗。
- **`--extra-py-files`**:`main.py` 以 `importlib` 動態載入 `jobs.*` / `common.*` / `transforms.*`,需把這些子套件一併帶入 Glue 的 Python path(可打包成 `.zip` 上傳後指向該 zip,或如上逐目錄帶入;實作時擇一並確認 import path 一致)。config yaml 隨上傳,Glue 執行時以相對路徑讀取。
- **JDBC driver**:PostgreSQL 走 `org.postgresql.Driver`(見 `common/writer.py`)。Glue 4.0 內建 PostgreSQL JDBC driver;若版本不符可透過 `--extra-jars` 指向 S3 上的 `postgresql-*.jar`。
- **Glue Connection**:綁定 VPC / Subnet / Security Group,讓 Glue 能連到 RDS(來源 / 目標庫);JDBC 帳密建議由 Secrets Manager 提供。
- 傳給程式的 job 名稱(`--job ds_migrate` / `--job m2201`)於步驟 3 用 `--arguments` 注入。

驗證 Job 存在:

```bash
aws glue get-job --job-name "$GLUE_JOB_NAME"   # exit 0 且 ScriptLocation 指向 S3
```

### 步驟 3:各執行一次 DS 搬移與 M2201 job

`main.py` 以 `--job <name>` 決定跑哪支 job。兩支各觸發一次並輪詢至 `SUCCEEDED`:

```bash
# --- DS 搬移 ---
RUN_ID=$(aws glue start-job-run \
  --job-name "$GLUE_JOB_NAME" \
  --arguments '{"--job":"ds_migrate"}' \
  --query 'JobRunId' --output text)

# 輪詢至 SUCCEEDED / FAILED
while true; do
  STATE=$(aws glue get-job-run --job-name "$GLUE_JOB_NAME" --run-id "$RUN_ID" \
    --query 'JobRun.JobRunState' --output text)
  echo "ds_migrate: $STATE"
  case "$STATE" in
    SUCCEEDED) break ;;
    FAILED|STOPPED|TIMEOUT|ERROR) echo "job 失敗:$STATE" >&2; break ;;
  esac
  sleep 15
done

# --- M2201 對應(需在 DS 搬移 SUCCEEDED 後執行,因 M2201 由 GAT/GAQ 來源產生)---
RUN_ID=$(aws glue start-job-run \
  --job-name "$GLUE_JOB_NAME" \
  --arguments '{"--job":"m2201"}' \
  --query 'JobRunId' --output text)

while true; do
  STATE=$(aws glue get-job-run --job-name "$GLUE_JOB_NAME" --run-id "$RUN_ID" \
    --query 'JobRun.JobRunState' --output text)
  echo "m2201: $STATE"
  case "$STATE" in
    SUCCEEDED) break ;;
    FAILED|STOPPED|TIMEOUT|ERROR) echo "job 失敗:$STATE" >&2; break ;;
  esac
  sleep 15
done
```

### 步驟 4:驗證目標 DB(唯讀)

```bash
psql "postgresql://$TARGET_DB_USER:$TARGET_DB_PASSWORD@$TARGET_DB_HOST:$TARGET_DB_PORT/$TARGET_DB_NAME" \
  -f etl/scripts/verify_target_db.sql
```

`verify_target_db.sql` 全為 `SELECT`(唯讀),輸出五段:

1. 各目標表筆數(`DS.GAT_FILE` / `DS.GAQ_FILE` / `DS.GAM_FILE` / `M2201.M2201`)。
2. 筆數為 0 的表(理想 **0 列**)。
3. 每一欄位的 Comment(逐欄列出)。
4. 缺 Comment 的欄位(理想 **0 列**)。
5. 缺 Comment 欄位總數 `missing_comment_count`(理想 **0**)。

### Acceptance 對照(哪些屬人工驗收)

| Acceptance 條目 | 驗收指令 | 屬性 |
| --- | --- | --- |
| 腳本已上傳 S3 | `aws s3 ls s3://$ETL_BUCKET/ --recursive \| grep -q "main.py"` | 人工(需 AWS) |
| Glue Job 存在且指向 S3 | `aws glue get-job --job-name "$GLUE_JOB_NAME"` | 人工(需 AWS) |
| DS 搬移 job SUCCEEDED | 步驟 3 輪詢 `JobRun.JobRunState` | 人工(需 AWS) |
| M2201 job SUCCEEDED | 步驟 3 輪詢 `JobRun.JobRunState` | 人工(需 AWS) |
| DS 表存在且筆數 > 0 | `verify_target_db.sql` 段 [1][2] | 人工(需 RDS) |
| 每一欄位 Comment 非空 | `verify_target_db.sql` 段 [4][5](0 列 / 0) | 人工(需 RDS) |
| `git diff --stat` 不含 backend/ frontend/ | `git diff --stat` | 可本地驗(已通過) |

### 部署最容易踩雷的點

1. **PyYAML 依賴**:Glue 執行環境**不含** PyYAML,`common/config.py` 一 import 就會 `ModuleNotFoundError`。務必在 Job 帶 `--additional-python-modules pyyaml`。
2. **子套件 import path**:`main.py` 以 `importlib` 動態載入 `jobs.*` / `common.*` / `transforms.*`。若 `--extra-py-files` 未正確涵蓋這些目錄(或未打包成可被 Python path 解析的 zip),Glue 上會 `ModuleNotFoundError: No module named 'jobs'`。建議把 `etl/` 打包為單一 zip 並確認執行時工作目錄 / sys.path 能解析到頂層套件。
3. **(延伸)Glue Connection 網路**:Glue 需經 Connection 綁定的 VPC / Subnet / Security Group 才連得到 RDS;Security Group 未放行 5432 或 Subnet 無 NAT / VPC endpoint 會導致連線逾時(常見於 Glue 卡在 RUNNING 後 FAILED)。
