---
id: task-002
title: 快照服務 + Redis cache + datasets API 改讀快照
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/services/snapshot_service.py
  - backend/app/repositories/rds_table_meta_repo.py
  - backend/app/core/redis.py
  - backend/app/api/v1/datasets.py
  - backend/app/schemas/rawdata.py
  - backend/app/etl/introspect.py
  - backend/tests/test_snapshot_service.py
estimated_hours: 3.5
---

## 目標

新增快照服務:內省 RDS(重用 `etl/introspect.py`)→ upsert `rds_table_meta`;datasets 瀏覽 API 改為**讀快照**(不即時打 RDS),支援過濾 0 筆表與時間欄;熱點讀取加 Redis cache。

## 設計要點

- `core/redis.py`:async redis client(env `REDIS_URL` 或既有 taskiq redis 連線設定;缺值 fail-fast),提供 get/set/delete 與 namespaced key helper。
- `repositories/rds_table_meta_repo.py`:upsert(dataset,schema,table)、list_by_schema(分頁)、list_schemas(聚合表數)、標記 last_synced/last_transformed;軟刪除規範。
- `services/snapshot_service.py`:
  - `refresh(dataset)`:呼叫 introspect 列 schema/table/column_count/row_count → **JOIN DS 字典 `GAT_FILE` 取業務資料中文名**(`lower(GAT01)=表名` AND `GAT02='0'` 繁優先、缺退 `'2'` → `GAT03`;批量查、識別字白名單引號化、值 bind)→ upsert repo(含 `business_name`)→ 回統計;寫 `snapshot_at`。此 JOIN **僅於 refresh 對 RDS 執行一次**,結果落自有 DB。
  - `list_schemas(dataset)` / `list_tables(dataset, schema, page, page_size, hide_empty)`:**讀 repo**(含 `business_name`),Redis cache(key 含 dataset/schema/page/hide_empty);refresh 後失效對應 key。
- `api/v1/datasets.py`:
  - 既有 `GET /{dataset}/schemas`、`GET /{dataset}/tables` 改走 snapshot_service(讀快照);`tables` 加 `hide_empty: bool = True` query。
  - **移除** `GET /{dataset}/tables/{schema}/{table}/columns`(前端不再有查看欄位功能)。
  - 新增 `POST /{dataset}/snapshot/refresh`(require_admin)→ snapshot_service.refresh。
- `schemas/rawdata.py`:`TableSummary` 加 `business_name`(nullable)/ `last_synced_at` / `last_transformed_at`(nullable ISO);移除 `ColumnListResponse` 若無他用(或保留但不掛路由)。
- `etl/introspect.py`:若需擴充「一次列全 schema 全表 for snapshot」可加函式;**禁**改動既有 `list_tables` 的 bind/quote 安全寫法語意。

## Acceptance

- [ ] `uv run pytest tests/test_snapshot_service.py` 全綠(fake introspect + 真/測 DB:refresh 後 repo 有對應筆數;list_tables hide_empty 過濾 row_count=0;cache 命中第二次不打 repo — 以 spy/計數驗證)
- [ ] `curl -s -b <admin cookie> localhost:8000/api/v1/datasets/source/tables?schema=DS&hide_empty=true | jq -e '.data.items | length >= 0'`(回快照且無 0 筆表)
- [ ] `curl -s -X POST -b <admin cookie> localhost:8000/api/v1/datasets/source/snapshot/refresh | jq -e '.success == true'`,且刷新後 `rds_table_meta` DS 筆數 == 來源實際表數;`AAA_FILE` 的 `business_name` == 「帳別參數檔」(GAT 繁中)
- [ ] `list_tables` 回傳含 `business_name`:`curl ... /datasets/source/tables?schema=DS | jq -e '.data.items[0] | has("business_name")'`
- [ ] 移除 columns 端點:`curl -s -o /dev/null -w '%{http_code}' localhost:8000/api/v1/datasets/source/tables/DS/GAT_FILE/columns` 回 404
- [ ] `uv run ruff check . && uv run mypy app` green;response 殼為 ApiResponse

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/10-statistics-log.md`(Redis 用法參考)
