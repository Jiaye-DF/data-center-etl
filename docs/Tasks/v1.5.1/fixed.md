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

## 3. semantic_mappings `updated_by` 型別偏離規範(text → uuid)

- **症狀**:user 查 RDS `erp_metadata.semantic_mappings` 發現 `updated_by` 是 text(值混雜 UUID 字串 / 工具標記 / NULL),與 `04-databases/00-overview.md` 必備欄位「updated_by = UUID」不符;自有 DB 副本的 `source_updated_by` 亦為 String(2026-07-21 user 指正)。
- **根因**:propose v1.5.0 A1 只寫「欄位含 updated_by」未指定型別;task-001 拆解時**自行具體化為 text**,實作照拆解檔執行;v1.5.0 scan 未比對必備欄位型別 → 雙重漏網。非 user 核可的例外。
- **修法**:
  - RDS 端:`ensure_semantic_schema` 冪等轉型(text → uuid,合法 UUID 原值保留、工具標記與 NULL 一律轉系統全零 UUID)+ 補 `NOT NULL DEFAULT 全零`(user 決議 2026-07-21:無值一律填全零);建表 DDL 同步修正。已對真實 RDS 執行(12,192 全零 / 54 真實 UUID / 34 NULL 回填全零)。
  - 自有 DB 副本:`source_updated_by` String → UUID(alembic v152,round-trip 驗證過);`SemanticMappingRow` / `_coerce_uuid` / admin service 綁定型別連動修正。
- **影響檔案**:`backend/app/etl/semantic_schema.py`、`backend/alembic/versions/v151_semantic_source_updated_by_uuid.py`、`backend/app/models/semantic_mapping.py`、`backend/app/repositories/semantic_mapping_repo.py`、`backend/app/worker/tasks.py`、`backend/app/services/semantic_admin_service.py`、對應測試。
- **升規候選**:scan 檢查清單應加「表結構 vs `04-databases` 必備欄位型別比對」;拆解階段 orchestrator 對 propose 未指定的型別應回查規範地板而非自行發明。

## 4. ETL 同步撞 `pg_namespace_nspname_index`(CREATE SCHEMA 併發 race)

- **症狀**:ETL 同步時單表失敗,traceback 為 `CREATE SCHEMA IF NOT EXISTS "G2203"` 撞 `duplicate key value violates unique constraint "pg_namespace_nspname_index"`(2026-07-21 user 回報)。
- **根因**:PostgreSQL 的 `CREATE SCHEMA IF NOT EXISTS` **非併發安全** — v1.4.0 改多表並行同步(`asyncio.gather`)後,同一 schema 首次落地時多張表同時通過「不存在」檢查再搶建,搶輸者拋 UniqueViolation 且該表整筆鏡像交易中止 → 記為失敗。屬 v1.4.0 併發化的潛伏邊界(既有 schema 不觸發,只在「新 schema × 並行首同步」出現),v1.4.0/v1.5.0 兩次 scan 的併發面向均未涵蓋「DDL 併發安全」。
- **修法**:`write_mirror` 的 CREATE SCHEMA 以 SAVEPOINT(`conn.begin_nested()`)包裹,catch `IntegrityError` 吞掉續行(搶輸即代表 schema 已由並行交易建立);回歸測試 `test_write_mirror_swallows_schema_create_race`。
- **影響檔案**:`backend/app/etl/mirror.py`、`backend/tests/test_mirror.py`。
