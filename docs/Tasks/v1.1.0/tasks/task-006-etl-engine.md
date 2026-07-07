---
id: task-006
title: ETL 執行核心(純 Python,DB 設定驅動 + 逐表詳細 log)
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/etl/__init__.py
  - backend/app/etl/engine.py
  - backend/app/etl/reader.py
  - backend/app/etl/writer.py
  - backend/app/etl/comments.py
  - backend/app/etl/transforms.py
  - backend/tests/test_etl_engine.py
  - backend/tests/test_etl_transforms.py
estimated_hours: 4
---

## 目標

實作容器內可執行的 ETL 核心(**不依賴 Glue / Spark**):讀自有 DB 的表設定與 mapping → 從來源 `erp_migration_test` 讀取 → 轉換(DS 搬移、GAT_FILE/GAQ_FILE → M2201)→ 寫入目標 `erp_etl_hub_test` 並套每欄位繁中 Comment;全程逐表寫 `etl_runs` / `etl_run_logs` 詳細 log。轉換與 Comment 規則**移植** v1.0.0 `etl/transforms/*` 與 `etl/config/mapping/*.yaml` 之行為(唯讀參考,**不改** `etl/` 任何檔)。

## 範圍要點

- 來源 / 目標 RDS 連線由 env 注入(`SOURCE_DB_*` / `TARGET_DB_*`),缺值 fail-fast;禁硬編、禁 log 帳密。
- 只處理 `etl_tables` 中**啟用**的表;停用表跳過並在 run log 標記 skipped。
- 逐表記錄:起訖時間、讀取/寫入筆數、耗時、狀態;例外捕捉後寫入錯誤明細(**含 stack trace**)再繼續下一表(單表失敗不中斷整個 run,run 總狀態標 failed)。
- 寫入策略**禁 DROP**:表存在則 truncate + insert,不存在則 CREATE TABLE;Comment 以 `COMMENT ON COLUMN` 套用,缺 comment 欄位 fail(不靜默)。
- SQL 組裝走參數綁定與識別字白名單(`04-sql-safety.md`)。
- 單元測試以本地 PG(或 SQLAlchemy 測試 fixture)驗證轉換與 log 寫入,不需連真 RDS。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_etl_engine.py tests/test_etl_transforms.py -q` 全綠,涵蓋:DS/M2201 欄位對映與 v1.0.0 mapping 行為一致、停用表 skipped、單表失敗續跑且 log 含 stack trace、每欄位 comment 缺值 fail
- [x] `! grep -inE "drop (table|column|schema|database)" backend/app/etl/` 成立(無 DROP)
- [x] `! grep -nE "password\s*=\s*['\"]" backend/app/etl/` 成立(無硬編密碼)
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md` + `04-sql-safety.md`
- `docs/Design-Base/04-databases/06-timezone.md` + `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`(結構化 log / 機密過濾)
