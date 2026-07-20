---
id: task-001
title: RDS erp_metadata schema + semantic_mappings 表冪等建置(A1)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/semantic_schema.py
  - backend/tests/test_semantic_schema.py
estimated_hours: 2
---

## 目標

在**目標 RDS**建立獨立 schema `erp_metadata` 與單一表 `semantic_mappings`,作為欄位語意層唯一事實來源。冪等:存在則略過,**禁 DROP**。

## 內容

- 新增 `backend/app/etl/semantic_schema.py`:提供 `ensure_semantic_schema(conn)`,以 `CREATE SCHEMA IF NOT EXISTS erp_metadata` + `CREATE TABLE IF NOT EXISTS erp_metadata.semantic_mappings` 建置。
- 表結構(propose A1,一字不差):`table_name text NOT NULL`、`column_name text NOT NULL DEFAULT ''`(`''`=表層級映射)、`english_name text NOT NULL`、`zh_name text`、`status text NOT NULL DEFAULT 'draft'`(draft/confirmed,加 CHECK)、`updated_by text`、`updated_at timestamptz NOT NULL DEFAULT now()`、`PRIMARY KEY (table_name, column_name)`。
- 連線沿用 `app/etl/reader.rds_database_url`(目標 RDS 端;與 mirror 引擎同模式);識別字白名單常值,不接受使用者輸入。
- **注意**:目標 RDS 的 DDL **不走 alembic**(alembic 只管 backend 自有 DB);本表由此模組冪等建置,對齊 mirror 引擎「存在則略過」原則。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_semantic_schema.py` 全綠(含:重複呼叫 ensure 兩次不 raise、CHECK 拒絕非 draft/confirmed)
- [ ] `grep -n "DROP" app/etl/semantic_schema.py` 零命中
- [ ] `uv run ruff check app/etl/semantic_schema.py` + `uv run mypy app/etl/semantic_schema.py` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
