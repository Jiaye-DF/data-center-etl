---
id: task-001
title: DB — schedules 加 source_schema / source_table + partial unique index + migration
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/models/schedule.py
  - backend/alembic/versions/v5_add_v131_schedule_per_table.py
  - backend/tests/test_models_v131.py
estimated_hours: 2
---

## 目標

把 `schedules` 由「v1.1 逐表 config / v1.3.0 全表」改為 v1.3.1「一表一排程」模型:加 `source_schema` / `source_table` 綁定來源表,加 partial unique index;`etl_table_pid` 標記 deprecated(保留欄位,禁 DROP COLUMN)。

## 內容

- `models/schedule.py`:
  - 新增 `source_schema: Mapped[str | None]`(String(100), nullable=True, comment 說明對應 `rds_table_meta` 來源表 schema)。
  - 新增 `source_table: Mapped[str | None]`(String(200), nullable=True)。
  - `etl_table_pid` 欄 comment 追加「(deprecated:v1.3.1 起不使用,保留欄位待人工移除)」。
  - `__table_args__` 加 partial unique index `uq_schedules_source_table`:`(source_schema, source_table) WHERE is_deleted = false`(對齊既有 `uq_schedules_name` partial index 寫法)。
- `alembic/versions/v5_add_v131_schedule_per_table.py`(`revision="v5"`, `down_revision="v4"`):
  - `upgrade`:`_has_column` guard 後 `add_column` 兩欄(nullable);`create_index` partial unique(`if_not_exists`)。可重入。
  - `downgrade`:**前進式,禁 DROP COLUMN**;僅 `drop_index` 本次新增之 index(guard 存在性),欄位保留並註明依 CLAUDE.md。
- `tests/test_models_v131.py`(純 metadata,參照 `tests/test_models_v120.py` 檔頭 env 注入):斷言兩新欄存在且 nullable、partial unique index `uq_schedules_source_table` 存在且 `postgresql_where` 非 None 且 columns 為 `{source_schema, source_table}`。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_models_v131.py -q` 全綠
- [ ] `cd backend && uv run ruff check app/models/schedule.py alembic/versions/v5_add_v131_schedule_per_table.py tests/test_models_v131.py` 全綠
- [ ] `cd backend && uv run alembic history` 顯示 `v4 -> v5 (head)`(單一 head)
- [ ] migration 檔內 `grep -iE "drop_column|drop table" alembic/versions/v5_add_v131_schedule_per_table.py` 無命中(零 DROP COLUMN/TABLE)
- [ ] `etl_table_pid` 欄仍存在於 model(未移除)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
