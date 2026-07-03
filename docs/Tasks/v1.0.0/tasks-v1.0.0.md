# Tasks v1.0.0

> 狀態:程式碼完成 6/6(001–005 全綠;006 部署腳本 + runbook 完成,實際 AWS/RDS 執行待人工於有憑證環境跑)
> 來源:`propose-v1.0.0.md`(scope 地板,禁動)
> 範圍:**僅 ETL 群(獨立 `etl/` 目錄)**。經 user 指示,本版 ETL 為 MVP,**完全不動本專案 `backend/` `frontend/`**,亦不受鎖定技術棧(Next.js/FastAPI/PostgreSQL)限制(PySpark/Glue 另案)。設定以 `etl/config/*.yaml` 檔管理,無管理後台。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | ETL framework 核心骨架 | done | ✓ | — | `etl/main.py` / `etl/common/config.py` / `etl/common/logger.py` / `etl/common/utils.py` / `etl/transforms/common.py` / `etl/config/job_config.yaml` / `etl/config/table_config.yaml` / `etl/requirements.txt` / `etl/README.md`(全 14 檔逐檔列於 task 檔) |
| 002 | common/reader — 來源讀取(erp_migration_test:DS/M2201) | done | ✓ | 001 | `etl/common/reader.py` / `etl/tests/test_reader.py` |
| 003 | common/writer — 目標寫入 + erp_etl_hub_test bootstrap + 欄位 Comment | done | ✓ | 001 | `etl/common/writer.py` / `etl/common/ddl.py` / `etl/scripts/bootstrap_target_db.sql` / `etl/tests/test_ddl.py` |
| 004 | DS schema 搬移 job | done | ✓ | 002,003 | `etl/jobs/ds_migrate_job.py` / `etl/transforms/ds.py` / `etl/config/mapping/ds.yaml` / `etl/tests/test_transform_ds.py` |
| 005 | GAT_FILE/GAQ_FILE → M2201 對應轉換 job | done | ✓ | 002,003 | `etl/jobs/m2201_job.py` / `etl/transforms/m2201.py` / `etl/config/mapping/m2201.yaml` / `etl/tests/test_transform_m2201.py` |
| 006 | S3 部署 + Glue Job 建置 + 端到端執行驗證 | code-done(部署待人工) | ✗ | 004,005 | `etl/scripts/deploy_s3.sh` / `etl/scripts/verify_target_db.sql` / `etl/README.md` |

## 拆解摘要

- **總數**:6 個 task,預估 ~18 hr,全部落在 `etl/`(不觸及 `backend/` `frontend/`)
- **並行**:001–005 `affected_files` 互不重疊(全 `parallel: true`);006 與 001 同檔(`etl/README.md`)故 `parallel: false`,依賴鏈保證序列化;實際併發受依賴鏈限制
- **起手可認領(無依賴)**:task-001
- **依賴鏈**:`001 → (002 ∥ 003) → (004 ∥ 005) → 006`
- **阻塞點**:004、005 皆需 002 + 003 完成(reader + writer + Comment 機制)才可開跑;006 為版本驗收收口,需 004 + 005 全綠
- **執行環境註記**:各 task Acceptance 指令為 bash 語法(`[ -d ... ]` / `! grep` 等);本機為 Windows,worker 一律以 **Git Bash** 執行驗證指令
- **關鍵設計約束(供 worker 對齊,避免同檔互鎖)**:
  1. `etl/main.py` 以**設定驅動的動態派工**載入 `jobs.<name>_job`,新增 job **不改** `main.py`(故 004/005 不動 001 的檔)
  2. 欄位 Comment 機制集中在 `etl/common/ddl.py`(task-003),各 job 只**提供** GAQ 欄位描述資料(mapping yaml),不各自實作 DDL
  3. `etl/transforms/common.py`(task-001 建立基底)供共用轉換 helper;004/005 各自新增 `transforms/ds.py`、`transforms/m2201.py`,**不改** `common.py`
- **待補規範**:`docs/Design-Base/` 尚無 ETL 專屬規範,必讀檔暫引用 DB/機密/時區通用底線;後續若要正式化走 `/reflect-rules` 補 ETL 規範區
