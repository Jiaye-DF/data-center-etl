# fixed.md — v1.5.1

> 條目格式依 `01-propose/04-fixed-format.md`(根因為核心)。

## 1. ETL 資料管理「資料分類」出現 `erp_metadata`

- **症狀**:快照同步後,ETL 資料管理頁資料分類多出 `erp_metadata(1)` pill(2026-07-21 user 回報截圖)。
- **根因**:快照內省 `introspect._ALL_TABLES_SQL` 只排除 pg 系統 schema;v1.5.0 在目標 RDS 建立 `erp_metadata.semantic_mappings` **實體表**後,下一次 target 快照就把系統 metadata schema 當業務分類收進 `rds_table_meta`。
- **修法**:`introspect.py` 抽共用排除條件 `_EXCLUDED_SCHEMA_CONDS`(`erp_metadata` + `%_view` + 舊制 `%_en`),`_ALL_TABLES_SQL` 與 `_SCHEMAS_SQL` 同套;自有 DB 既有殘留快照列軟刪(`is_deleted=true`,本機已執行;**測試站部署後需重跑一次快照同步或同樣軟刪**);新增 `tests/test_introspect_exclusions.py` 防回歸。
- **影響檔案**:`backend/app/etl/introspect.py`、`backend/tests/test_introspect_exclusions.py`。

## 2. 殭屍 run 收殮(本機 etl_runs pid=30)

- **症狀**:全局進度條永遠顯示「同步中(手動)681 / 11,385(6%)」,無同步在跑。
- **根因**:2026-07-20 17:02 的手動全量同步跑到 681 表時 worker **容器層中斷**(stop / rebuild),行程死亡無人收尾;既有 `_mark_failed_if_dangling` 只接得住行程內例外,接不住 SIGKILL → `etl_runs.status` 永遠 `running`,`/runs/active` 持續回傳。
- **修法**:手動 UPDATE 標 `failed`(run + 2 筆卡 running 的逐表 log;`finished_at` 依通則寫 UTC+8 naive);**治本待做**:worker 啟動時掃「running 且 started_at 早於 worker 啟動」的 run 自動補標 failed(v1.4.0 遺留「殭屍 run」項,建議下版納 scope)。
- **影響檔案**:無程式改動(資料修正);治本項未實作。
