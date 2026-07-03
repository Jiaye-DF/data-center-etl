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

腳本同時把 `common/ jobs/ transforms/` 打包為 **`etl_pkg.zip`** 一併上傳
(Glue `--extra-py-files` 只接受檔案清單、**不接受目錄**;zip 根層即套件目錄,
Glue 加進 sys.path 後 `import common` / `import jobs` 可直接解析)。

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
    "--extra-py-files": "s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'etl_pkg.zip",
    "--additional-python-modules": "pyyaml",
    "--config-s3-uri": "s3://'"$ETL_BUCKET"'/'"$ETL_PREFIX"'config/",
    "--source-db-secret-id": "<source-db-secret-name>",
    "--target-db-secret-id": "<target-db-secret-name>",
    "--job-language": "python"
  }'
```

重點:

- **`--additional-python-modules pyyaml`**:`common/config.py` 需要 PyYAML;Glue 執行環境預設**不含** PyYAML,務必帶上,否則 import 失敗(boto3 Glue 已內建,不必列)。
- **`--extra-py-files` 指向單一 zip**:`main.py` 以 `importlib` 動態載入 `jobs.*` / `common.*` / `transforms.*`;`deploy_s3.sh` 已打包 `etl_pkg.zip`,直接指向即可。**不可**指向 S3「目錄」(該參數只接受檔案清單)。
- **`--config-s3-uri`**:config yaml **不會**隨 `--extra-py-files` 進到執行環境;`main.py` 依此參數用 boto3 從 S3 直讀 `config/*.yaml` 與 `config/mapping/*.yaml`。**改 S3 上的 yaml,下次 run 直接生效,不需重新部署程式碼、不需改 Job 定義**(見〈設定與效能調校〉)。
- **DB 憑證走 Secrets Manager**:Glue **沒有**設定 OS 環境變數的介面,`SOURCE_DB_*` / `TARGET_DB_*` env 在 Glue 上不存在。`main.py` 啟動時依 `--source-db-secret-id` / `--target-db-secret-id` 從 Secrets Manager 解出 `host / port / dbname / username / password`(RDS 標準 secret 格式)填入 process env;本地執行時既有 env 一律優先,行為不變。
- **JDBC driver**:PostgreSQL 走 `org.postgresql.Driver`(見 `common/writer.py`)。Glue 4.0 內建 PostgreSQL JDBC driver;若版本不符可透過 `--extra-jars` 指向 S3 上的 `postgresql-*.jar`。
- **Glue Connection**:綁定 VPC / Subnet / Security Group,讓 Glue 能連到 RDS(來源 / 目標庫)。
- 傳給程式的 job 名稱(`--job ds_migrate` / `--job m2201`)於步驟 3 用 `--arguments` 注入;Glue 自動注入的內建參數(`--JOB_NAME` 等)由 `main.py` 的 `parse_known_args` 忽略,不會報錯。

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
2. **子套件 import path**:`main.py` 以 `importlib` 動態載入 `jobs.*` / `common.*` / `transforms.*`。`--extra-py-files` 必須指向 `deploy_s3.sh` 產的 `etl_pkg.zip`(單一 zip),指向目錄或漏帶會 `ModuleNotFoundError: No module named 'jobs'`。
3. **config yaml 不會自己出現在執行環境**:忘記帶 `--config-s3-uri` 時,Glue 上 `load_config()` 找不到本地 `config/` 會 `FileNotFoundError`。務必在 default arguments 帶 `--config-s3-uri`。
4. **DB 憑證**:Glue 上沒有 `SOURCE_DB_*` / `TARGET_DB_*` env;忘記帶 `--source-db-secret-id` / `--target-db-secret-id` 會在 reader / writer fail-fast「缺少來源 DB 連線 env」。
5. **(延伸)Glue Connection 網路**:Glue 需經 Connection 綁定的 VPC / Subnet / Security Group 才連得到 RDS;Security Group 未放行 5432 或 Subnet 無 NAT / VPC endpoint 會導致連線逾時(常見於 Glue 卡在 RUNNING 後 FAILED)。

---

## 設定與效能調校

### 改 yaml 的生效方式(不需重新部署)

config 由 `--config-s3-uri` 指向的 S3 位置**於每次 run 啟動時讀取**:

```bash
# 只改設定:直接改本地 yaml 後同步 config/ 即可(或重跑完整 deploy_s3.sh)
aws s3 sync etl/config/ "s3://$ETL_BUCKET/${ETL_PREFIX}config/"
# 下一次 start-job-run 即讀到新值;不需重 create-job、不需重傳 etl_pkg.zip
```

改 `.py` 程式碼才需要重跑 `deploy_s3.sh`(重傳 `main.py` + `etl_pkg.zip`)。

### 大表 / 大量表效能(來源約 5000 張表時必讀)

**單表讀取**:mapping yaml 的表定義支援效能欄位(皆可省略,省略走預設):

```yaml
tables:
  GAT_FILE:
    fetchsize: 20000        # JDBC 逐批抓取列數,預設 10000
    partition:              # 大表必設:以數值欄切 N 個並行連線讀取
      column: pid           # 單調遞增的數值欄(主鍵 / serial)
      num_partitions: 8
      lower_bound: 1
      upper_bound: 5000000  # 該欄實際 min/max 範圍
    columns:
      ...
```

- 無 `partition` → 單連線整表拉(小表可接受;大表會慢且 driver 可能 OOM)
- 寫入端已預設 `batchsize=10000` + `reWriteBatchedInserts=true`(PostgreSQL 批次寫入最佳化)

**量級注意(5000 張表)**:

1. **UDF 是最大瓶頸**:`ds_migrate_job._transform_df` 對每欄掛 Python UDF,每個值都經 Python 序列化往返,吞吐比原生 Spark 函式(`F.trim` / `cast` / `F.when`)慢一個量級以上。表數量大時應改寫 transforms 為原生 column expression(行為不變,僅執行路徑不同)。
2. **拆批執行**:5000 張表塞單一 job run 會跑數小時且中途失敗需整批重來;建議按 schema / 表名區段拆多個 run(`--arguments` 傳不同 mapping 子集),或以 Glue Workflow / Step Functions 編排。
3. **來源 DB 連線壓力**:`num_partitions` × 並行 run 數 = 對來源 RDS 的同時連線數,調高前先確認來源 `max_connections` 與工作時段負載。
4. **Comment 逐條執行**:`writer._apply_comments` 每欄一條 `COMMENT ON COLUMN`;5000 表 × 平均欄數的往返可觀,若成為瓶頸可改單連線批次執行(同 statement 多 execute 已是單連線,通常可接受)。
