---
id: task-003
title: 自有 DB mapping 副本表 + 同步回流與 cache 失效(A5)
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/alembic/versions/v150_add_semantic_mappings_copy.py
  - backend/app/models/semantic_mapping.py
  - backend/app/models/__init__.py
  - backend/app/repositories/semantic_mapping_repo.py
  - backend/app/worker/tasks.py
  - backend/tests/test_semantic_mapping_sync.py
estimated_hours: 4
---

## 目標

RDS `erp_metadata.semantic_mappings` 為唯一事實來源;ETL 同步 job 末端把它**單向**整表重灌回 backend 自有 DB 副本表,供 API 讀取(同 `rds_table_meta` 快照模式,不即時打 RDS)。**禁雙向同步**。

## 內容

- alembic migration:自有 DB 建 `semantic_mappings` 副本表(欄位同 RDS 版 + BaseModel 必備欄;依 `04-databases/00-overview.md`)。
- `app/models/semantic_mapping.py` + `models/__init__.py` 註冊。
- `app/repositories/semantic_mapping_repo.py`:`replace_all(rows)`(整表重灌:DELETE + bulk INSERT,單交易)、`get_confirmed_map(table_name)`(讀 confirmed 映射,供 API/view 消費)。
- `app/worker/tasks.py`:同步 job 完成階段新增步驟 — 讀 RDS `erp_metadata.semantic_mappings` 全量(小表,免增量)→ `replace_all` → 失效相關 Redis cache(沿用既有 cache 失效模式);RDS 端表不存在時 graceful 略過(log warning,不 fail job)。
- 同步方向嚴格 RDS→自有 DB;副本表不提供任何寫入 API。

## Acceptance

- [x] `cd backend && uv run alembic upgrade head` 後 `uv run alembic downgrade -1` round-trip OK,再 upgrade 回 head
- [x] `uv run pytest tests/test_semantic_mapping_sync.py` 全綠(含:整表重灌後副本=來源、來源缺表 graceful、cache 失效被呼叫)
- [x] `uv run pytest` 既有全套件不紅(250 passed)
- [x] ruff + mypy 全綠(上列 affected python 檔)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
