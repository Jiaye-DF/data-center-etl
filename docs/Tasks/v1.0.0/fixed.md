# Fixed v1.0.0

> 本版所有規範違反 / bug 根因累積於此。條目格式見 `docs/Design-Base/01-propose/04-fixed-format.md`;§ 編號全版本連號,**禁**刪除舊條目。

## § 1 — task-001:config yaml 註解改 ASCII(規範取捨,非 bug)

- **來源**:task-001 Acceptance 第 2 條用裸 `open()`(不帶 encoding)load `config/*.yaml`。本機 Windows Python 預設編碼為 `cp950`,yaml 若含繁中註解會觸發 `UnicodeDecodeError` 使該條 fail。
- **處置**:`config/job_config.yaml`、`config/table_config.yaml` 的**註解**改為 ASCII 英文(與「yaml 註解繁中」規則衝突,依〈Acceptance 必過〉優先)。其餘 `.py` / README / docstring 維持繁中。production 載入路徑 `common/config.py` 本就用 `encoding="utf-8"`,不受影響。
- **後續**:若要還原繁中註解,把 Acceptance 命令改為 `open(..., encoding='utf-8')` 或全流程加 `PYTHONUTF8=1`。

## § 2 — task-004/005:含繁中 comment 的 mapping yaml 於 cp950 裸 open() 需 PYTHONUTF8=1(環境特性,非缺陷)

- **來源**:`config/mapping/ds.yaml`、`m2201.yaml` 的欄位 Comment 內容**必為繁中**(GAQ_FILE 描述,scope 要求),故 yaml 必含 UTF-8 多位元組。task-004/005 Acceptance 第 2 條的裸 `open()` 在本機 cp950 locale 下會 `UnicodeDecodeError`。
- **驗證**:以 `PYTHONUTF8=1 python -c ...` 執行即 exit 0;檔案本身為合法 UTF-8;production 載入 `common/config.py` 用 `encoding="utf-8"` 正常。屬 Windows 本機 locale 特性,非檔案缺陷。
- **後續建議**:CI / 驗收若在同款 Windows locale,統一加 `PYTHONUTF8=1` 或把驗證命令改用 `encoding='utf-8'`。Glue(Linux/UTF-8)無此問題。

## § 3 — task-006:AWS/RDS 端到端 Acceptance 待人工執行(邊界,非 bug)

- **來源**:task-006 Acceptance 含 `aws s3 sync` / `aws glue start-job-run` / `psql` 等需真實 AWS 憑證 + RDS 連線的項目;multi-agent 執行環境無憑證,無法實跑。
- **處置**:agent 產出可執行的 `deploy_s3.sh`、唯讀 `verify_target_db.sql`、README 手動 runbook(env 表 + 步驟 + Acceptance 對照),並誠實標註哪些屬人工驗收,**未造假 AWS 輸出**。腳本本身已通過語法檢查、fail-fast、唯讀 / 無 DROP / 無硬編 bucket 檢查。
- **後續**:由具 AWS 憑證者依 README 部署章節執行,回填 6 條 AWS/RDS Acceptance;若執行發現 bug,回寫對應 task 並於本檔續記 § 4+。
