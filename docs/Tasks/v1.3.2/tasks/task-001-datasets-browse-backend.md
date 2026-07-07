---
id: task-001
title: 資料瀏覽後端 — ETL 快照時間欄 + 原始資料筆數區間 + schema 統計摘要端點
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/rawdata.py
  - backend/app/services/snapshot_service.py
  - backend/app/api/v1/datasets.py
  - backend/app/repositories/rds_table_meta_repo.py
estimated_hours: 4
---

## 目標

`TableSummary` 補吐 `snapshot_at`(供 ETL 資料頁改顯示快照時間);`list_tables` 加筆數區間 `row_min`/`row_max`;新增 `GET /datasets/{dataset}/summary` schema 統計摘要(表數分布 + 1000+ 桶,**不做筆數加總**)。回溯記錄:已於 commit `967400e` 落地。

## Acceptance

- [x] `git show 967400e:backend/app/schemas/rawdata.py | grep -q snapshot_at` 且含 `class SchemaStatSummary`
- [x] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/datasets/target/summary?schema=DS"` == 401(路由存在、需授權)
- [x] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/datasets/source/tables?schema=DS&row_min=0&row_max=1000"` == 401(參數綁定通過,非 422)
- [x] `cd backend && uv run pytest tests/test_snapshot_service.py tests/test_rds_table_meta_repo_v130.py -q` 全綠
- [x] `cd backend && ruff check app` 通過;`mypy app` 無新增錯誤
- [x] `row_count` bounded 探測封頂 1001:summary 以「總表數/有資料/空表/1000+」呈現,無筆數加總

## 必讀檔(Just-in-time)

- `03-backend/00-overview.md`
- `03-backend/01-routing.md`
- `03-backend/08-performance.md`
- `04-databases/04-sql-safety.md`
- `04-databases/10-statistics-log.md`
