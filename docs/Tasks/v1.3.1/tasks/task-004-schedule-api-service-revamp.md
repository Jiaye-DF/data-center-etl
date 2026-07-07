---
id: task-004
title: 排程/執行 API+service 重構(逐表列表 + 改 cron·啟停·描述 + 批次啟停;移除 create/delete 與 config-ETL 手動觸發)
status: pending
parallel: true
depends_on: [task-002]
affected_files:
  - backend/app/schemas/schedule.py
  - backend/app/services/schedule_service.py
  - backend/app/api/v1/schedules.py
  - backend/app/api/v1/runs.py
  - backend/tests/test_schedule_api_v131.py
  - backend/tests/test_runs_api.py
estimated_hours: 4
---

## 目標

把 `/schedules` 由「排程條目 CRUD」重構為「逐表視角 + 生命週期跟隨快照」:列表逐表(JOIN meta × 最新 run log)、更新收斂為改 cron/啟停/描述(不可改綁定表)、加批次啟停端點、**移除手動新增/刪除排程端點**;並移除 v1.1 config-ETL 手動觸發(`RunService.trigger_manual` + `api/v1/runs.py` 觸發端點),保留 runs 清單/明細/logs。

## 內容

- `schemas/schedule.py`:新增逐表視角 response（`table_name` / `business_name` / `schedule_uid` / `cron_expr` / `is_enabled` / `description` / `last_synced_at` / `last_run_status` / `next_run` 由前端推算故此欄可不回)、schema 分頁摘要 response、批次啟停 request（`enabled: bool` + 選填 `schema`）。移除 create/delete 相關 schema。
- `services/schedule_service.py`:
  - `ScheduleService`:`list_tables_view` / `list_schema_summaries`(呼叫 task-002 repo)、`update_schedule`(僅 cron/啟停/描述,禁改綁定表)、`set_enabled`、`batch_set_enabled`;**移除** `create_schedule` / `delete_schedule` / 逐表 etl_table_uid 解析。
  - `RunService`:**移除** `trigger_manual`（config-ETL 手動觸發,依賴 `run_etl`);保留 `list_runs` / `get_run` / `list_run_logs`。
- `api/v1/schedules.py`:端點改為 `GET ""`(逐表列表,query:schema/page/page_size/enabled/last_result/keyword)、`GET "/schemas"`、`PATCH "/{uid}"`(cron/啟停/描述)、`POST "/{uid}/enable"`、`POST "/{uid}/disable"`、`POST "/batch-enabled"`(批次,admin);**移除** `POST ""`(create)、`DELETE "/{uid}"`。
- `api/v1/runs.py`:**移除**手動觸發端點（`POST /runs` 之類呼叫 `RunService.trigger_manual` 者）;保留 runs 清單/明細/logs 端點。
- 測試更新既有 `test_runs_api.py`(移除觸發端點相關 case);新 `test_schedule_api_v131.py` 覆蓋新端點。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_schedule_api_v131.py tests/test_runs_api.py -q` 全綠(測試 DB localhost:5435)
- [ ] `cd backend && uv run ruff check app/schemas/schedule.py app/services/schedule_service.py app/api/v1/schedules.py app/api/v1/runs.py tests/test_schedule_api_v131.py tests/test_runs_api.py` 全綠
- [ ] `curl` / pytest 驗:`POST /api/v1/schedules`(create)與 `DELETE /api/v1/schedules/{uid}` 回 404 或 405（端點不存在）
- [ ] `GET /api/v1/schedules?schema=DS` 回 ApiResponse 外殼且 `data.items[]` 含 `table_name` / `is_enabled` / `last_run_status`
- [ ] `POST /api/v1/schedules/batch-enabled`（admin,body `{enabled:true}`）回影響筆數;viewer 呼叫回 403
- [ ] `grep -rn "trigger_manual\|run_etl" app/services/schedule_service.py app/api/v1/runs.py` 無命中

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
