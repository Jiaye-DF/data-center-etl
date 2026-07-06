---
id: task-007
title: 依表檢視 coverage API(全表 × 啟用排程 × 上次結果 + 逐表排除)
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/schemas/schedule_coverage.py
  - backend/app/services/schedule_coverage_service.py
  - backend/app/repositories/schedule_coverage_repo.py
  - backend/app/api/v1/schedule_coverage.py
  - backend/app/api/v1/__init__.py
  - backend/tests/test_schedule_coverage_api.py
estimated_hours: 4
---

## 目標

新增「排程管理依表檢視」API:**以來源表為單位**呈現排程涵蓋與執行狀態(非單純讀 metadata 快照)。每張 `rds_table_meta`(source)表 JOIN「是否有啟用中排程涵蓋」×「是否被排除」×「上次同步時間」×「上次執行結果」;支援 schema 分頁與篩選(依 schema / 依納入狀態 / 依上次結果 / 找未涵蓋表),並提供**逐表排除 / 納入** toggle(admin)。全走**新檔**,不動 task-006 的 schedule service/api。

## 設計要點

- 依賴 task-001 `RdsTableMeta.sync_excluded`;讀 `rds_table_meta`(source)、`schedules`、`etl_run_logs`。
- **「全表預設納入 + 可逐表排除」語意**:排程單一化為同步(全表增量),只要**存在 ≥1 筆啟用中排程**,則**未被排除**的來源表皆「已納入」。`included = (存在啟用排程) and (not sync_excluded)`;`excluded = sync_excluded`。「涵蓋缺口」= not included(被排除 / 無啟用排程);有啟用排程且無人排除時應為 0(對齊 propose 驗收)。
- `repositories/schedule_coverage_repo.py`:
  - `list_source_tables(schema, *, offset, limit, filters) -> tuple[list[Row], int]`:分頁列 source 快照表(含 `sync_excluded`),LEFT JOIN 每表最新 `etl_run_logs`(以 `source_schema`+`source_table` 對應,取 `pid` 最大者)得 `last_result`(success/failed/skipped)與 `last_run_finished_at`;回傳含 `table_name` / `business_name` / `sync_excluded` / `last_synced_at` / `last_result`。
  - `list_schemas() -> list[tuple[str, int]]`:source 各 schema 表數(本檔獨立實作避免跨 repo 改動)。
  - `active_schedules() -> list[(cron_expr, name)]`:啟用中且未刪除排程(供「套用排程」cron 摘要與 included 判定)。
  - `set_excluded(schema, table, *, excluded: bool, actor_uid) -> None`:更新該 source 表 `rds_table_meta.sync_excluded`(未刪除範圍;`updated_by`/`updated_at`);表不存在回 404 由 service 判。
  - 篩選:`included`(all/included/uncovered)、`last_result`(all/success/failed/none)、`keyword`(table/business ILIKE,沿用 rds_table_meta_repo 跳脫寫法)。
- `services/schedule_coverage_service.py`:組裝回應;`included` 由「有啟用排程 且 未被排除」決定;`applied_cron` 取第一筆啟用排程 cron(多筆附數量);`set_exclusion(schema, table, excluded, actor_uid)` 寫排除 + 稽核。
- `schemas/schedule_coverage.py`:`CoverageTableItem`(table_name/business_name/included/excluded/applied_cron/last_synced_at/last_result)、`CoverageListResponse`(items/total/page/page_size/covered_summary{total,included,excluded,uncovered})、`CoverageSchemaListResponse`、`ExclusionRequest`(schema/table/excluded)。**下次執行由前端 `utils/cron.ts` 依 `applied_cron` 推算**,後端不算。
- `api/v1/schedule_coverage.py`:
  - `GET /schedule-coverage/schemas`(require_login)→ source schema 清單 + 表數。
  - `GET /schedule-coverage/tables?schema=&page=&page_size=&included=&last_result=&keyword=`(require_login)→ 分頁依表檢視。
  - `PATCH /schedule-coverage/exclusion`(**require_admin**,body `{schema, table, excluded}`)→ 逐表排除 / 納入。
- `api/v1/__init__.py`:`from . import ... schedule_coverage` + `router.include_router(schedule_coverage.router, prefix="/schedule-coverage", tags=["schedule-coverage"])`。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_schedule_coverage_api.py -q` 全綠,涵蓋(seed rds_table_meta source + schedules + etl_run_logs):
  - 有 1 筆啟用排程且無人排除時,`GET /schedule-coverage/tables?schema=DS` 每筆 `included==true`、`excluded==false`,`covered_summary.uncovered==0`
  - 無啟用排程時,全部 `included==false`,`uncovered==總表數`
  - `PATCH /schedule-coverage/exclusion {excluded:true}`(admin)後,該表 `excluded==true`、`included==false`、`covered_summary.excluded>=1`;`{excluded:false}` 還原為已納入
  - 某表最新 `etl_run_logs` 為 success/failed/skipped → `last_result` 對應;無 log → `null`(未跑)
  - `included=uncovered` 篩選(含被排除表)、`last_result=failed`、`keyword` 皆生效
  - `GET` viewer 可讀;`PATCH` viewer → 403
- [ ] `curl -s -X PATCH -b <admin cookie> -H 'content-type: application/json' -d '{"schema":"DS","table":"AAA_FILE","excluded":true}' localhost:8000/api/v1/schedule-coverage/exclusion | jq -e '.success == true'`
- [ ] `uv run ruff check . && uv run mypy app` green
- [ ] `git diff backend/app/services/schedule_service.py backend/app/api/v1/schedules.py backend/app/repositories/rds_table_meta_repo.py` 無輸出(coverage 走新檔,不動 task-003/006 檔)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
- `docs/Design-Base/00-overview/05-timezone.md`
