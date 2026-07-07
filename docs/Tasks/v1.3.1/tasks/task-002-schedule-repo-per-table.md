---
id: task-002
title: schedule_repo — 逐表讀寫 + 逐表視角查詢 + 批次啟停
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/repositories/schedule_repo.py
  - backend/tests/test_schedule_repo_v131.py
estimated_hours: 3
---

## 目標

在 `ScheduleRepository` 加「一表一排程」與「逐表視角」所需的讀寫方法(供 task-003 快照自動建排程、task-004 排程 API 使用),並把 v1.3.0 `schedule_coverage_repo` 的逐表 JOIN 查詢遷移沿用進來。**不動既有方法**。

## 內容(方法契約,照名照簽名)

- `find_by_source_table(schema: str, table: str) -> Schedule | None`:依 `(source_schema, source_table)` 未刪除範圍找。
- `upsert_for_source_table(*, schema, table, name, cron_expr, is_enabled, actor_uid) -> Schedule`:無則建(填 `source_schema`/`source_table`,`etl_table_pid=None`),有則不覆蓋既有啟停/cron(避免快照重置使用者設定;僅補缺)。
- `soft_delete_by_source_tables_absent(present: set[tuple[str, str]], actor_uid: UUID) -> int`:把 `source_table` 非 NULL 且 `(schema,table)` 不在 `present` 的排程軟刪(來源表消失)。回軟刪筆數。
- `soft_delete_legacy_all_table(actor_uid: UUID) -> int`:軟刪 v1.3.0 遺留「全表增量」排程(`source_schema IS NULL AND is_deleted = false`)。回筆數。
- `list_tables_view(*, schema, offset, limit, enabled, last_result, keyword) -> tuple[list[Row], int]`:主查 `rds_table_meta`(dataset=source、未刪除、指定 schema)LEFT JOIN `schedules`(依 source_schema/table)LEFT JOIN「每表最新 `etl_run_logs` status」子查詢(`DISTINCT ON (source_schema, source_table) ... ORDER BY ..., pid DESC`)。回每列:table_name / business_name / last_synced_at / row_count / schedule uid / cron_expr / is_enabled / description / last_run_status。filter:`enabled`(all/enabled/disabled)、`last_result`(all/success/failed/never)、`keyword`(table/business ILIKE,沿用既有 escape)。
- `list_schema_summaries() -> list[tuple[str, int, int]]`:dataset=source group by schema,回 (schema, 表數, 已啟用排程數)。
- `batch_set_enabled(*, schema: str | None, enabled: bool, only_source_tables: bool, actor_uid) -> int`:對(指定 schema 或全部)有 source_table 的排程批次設 is_enabled,回影響筆數。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_schedule_repo_v131.py -q` 全綠(測試 DB localhost:5435)
- [ ] `cd backend && uv run ruff check app/repositories/schedule_repo.py tests/test_schedule_repo_v131.py` 全綠
- [ ] 測試涵蓋:upsert 建立/不覆蓋既有啟停、缺表軟刪、軟刪 legacy 全表排程、list_tables_view 反映最新 log status 與 enabled/last_result/keyword 篩選、batch_set_enabled 影響筆數正確
- [ ] 既有方法(list_schedules / find_by_uid / create / touch / soft_delete / etl_table_uid_by_pid / schedule_ref_by_pid)未被修改(diff 僅新增)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/03-backend/07-testing.md`
