---
id: task-006
title: 排程列表加上次執行結果 + sync 語意(移除逐表選擇)
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/schedule.py
  - backend/app/services/schedule_service.py
  - backend/app/repositories/schedule_repo.py
  - backend/app/api/v1/schedules.py
  - backend/tests/test_schedule_lastrun_api.py
estimated_hours: 3
---

## 目標

排程單一化為同步(全表增量),逐表選擇失去意義:排程 CRUD **一律 `etl_table_pid = NULL`**(建立/更新時忽略逐表)。排程列表 / 明細加**上次執行結果 + 上次執行時間**(對齊 propose ⑥對外承諾「排程列表看得出上次執行結果」),資料取自 `etl_runs`(該排程最近一次 run)。既有端點路徑不變(向下相容);**不引入 `job_type`**。

## 設計要點

- `repositories/schedule_repo.py`:加 `last_run_by_schedule_pids(pids: list[int]) -> dict[int, tuple[str, datetime | None]]`——一次查每個 `schedule_pid` 最近一筆 `etl_runs`(`pid` 最大者)回 `(status, finished_at)`;避免 N+1(對齊 `08-performance.md`)。`create(...)` 移除 / 忽略逐表(`etl_table_pid` 恆 NULL)。
- `services/schedule_service.py`(`ScheduleService`):
  - `create_schedule` / `update_schedule`:**強制 `etl_table_pid = None`**(sync 全表增量;不再解析 `etl_table_uid`)。既有 `etl_table_uid` 欄位在 request 保留但忽略(向下相容,不報錯),或於 schema 移除(見下)。
  - `list_schedules` / `get_schedule`:批次帶入上次 run 結果,填入回應 `last_run_status` / `last_run_at`。
  - `RunService` 不動。
- `schemas/schedule.py`:
  - `ScheduleResponse` 加 `last_run_status: str | None`、`last_run_at: datetime | None`;移除逐表語意的顯示依賴(`etl_table_uid` 恆 null)。
  - `ScheduleCreateRequest` / `ScheduleUpdateRequest` 的 `etl_table_uid` 保留為相容欄但標記忽略(避免破壞既有前端;前端 task-008 停止傳送)。
- `api/v1/schedules.py`:route summary 補「(同步排程:全表增量,無逐表選擇)」;不新增/移除端點。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_schedule_lastrun_api.py -q` 全綠,涵蓋:
  - `POST /schedules`(admin)即使帶 `etl_table_uid` → 建立後 `etl_table_uid == null`(逐表被忽略)
  - `GET /schedules`:某排程有對應 `etl_runs`(success/failed)→ 回應 `last_run_status` / `last_run_at` 正確;無 run → 皆 null
  - 多排程列表批次查上次 run 無 N+1(單次聚合 query;測試以 query 計數或結果正確性驗)
  - viewer 呼叫 create/patch → 403
- [ ] `curl -s -b <admin cookie> 'localhost:8000/api/v1/schedules?page=1&page_size=20' | jq -e '.data.items[0] | has("last_run_status") and has("last_run_at")'`
- [ ] `uv run ruff check . && uv run mypy app` green
- [ ] `git diff backend/app/api/v1/__init__.py` 無輸出(本 task 不動 router 註冊)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
