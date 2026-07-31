---
id: task-001
title: RDS `client_setting` schema + 11 張權限表 DDL + models
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/client_setting.py
  - backend/app/etl/client_setting_schema.py
  - backend/tests/test_client_setting_schema.py
estimated_hours: 3.5
model: opus
effort: medium
---

## 目標

在 RDS ETL-Hub 建立專用 schema `client_setting` 與 11 張權限表(唯一真身,供多機共讀),並提供 SQLAlchemy models 與冪等 DDL 建置模組;**不動自有 DB、不走 alembic**。

## 實作要點

- 11 張表(全含 BaseModel 欄位:`pid` BIGINT identity PK、`<table>_uid` UUID UK、`is_deleted`、`created_at/by`、`updated_at/by`;時間 naive timestamp UTC+8):
  `services`(code partial unique)/ `operations`(service_pid FK,name 系統別內唯一)/ `operation_items`(operation_pid + table_name + column_name,`*` = 全欄位)/ `permission_profiles`(name 唯一)/ `profile_operations`(profile_pid × operation_pid)/ `profile_items`(profile_pid + operation_pid + table_name + column_name + action ∈ read|edit)/ `roles`(**permission_profile_pid NOT NULL**,name 唯一)/ `client_roles`(api_client_uid × role_pid;client 未刪列 partial unique 保證 0..1)/ `exception_sets` / `exception_operations` + `exception_items`(結構同 profile_*)/ `client_exception_sets`(api_client_uid × exception_set_pid + `expires_at` NULL=不設限)。
- **跨庫關聯注意**:API Client 本體在自有 DB,RDS 端以 `api_client_uid`(UUID)冷關聯,**不建跨庫 FK**。
- DDL 建置比照 `backend/app/etl/semantic_schema.py` 前例:`CREATE SCHEMA IF NOT EXISTS client_setting` + 逐表 `CREATE TABLE IF NOT EXISTS` + 索引,冪等可重跑;連線用 `rds_database_url(RDS_TARGET_DB_ENV)` + `create_async_engine`。
- models 全表 `__table_args__ = {"schema": "client_setting"}`;唯一性 / partial unique 與 DDL 一致。

## Acceptance

- [ ] `uv run pytest tests/test_client_setting_schema.py` 全綠(真實測試 DB 模擬 RDS:建置後 information_schema 斷言 11 表齊備、BaseModel 欄位齊、roles.permission_profile_pid NOT NULL、重跑 DDL 不報錯)
- [ ] 對測試 DB 直接 `SELECT` `client_setting.services` 等表成功(模擬他機直讀)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] 自有 DB migration 目錄零變更(`git status` 佐證)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
