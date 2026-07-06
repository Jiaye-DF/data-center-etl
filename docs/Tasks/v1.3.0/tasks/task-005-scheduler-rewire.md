---
id: task-005
title: 排程接線修正(scheduler.py 排程一律派 mirror_sync 增量)
status: pending
parallel: true
depends_on: [task-004]
affected_files:
  - backend/app/worker/scheduler.py
  - backend/tests/test_scheduler_v130.py
estimated_hours: 2
---

## 目標

修正 v1.2 遺留缺口:`scheduler.py` 目前一律派工舊 `run_etl`(逐表 config ETL)。本版**排程單一化**——所有啟用排程一律派 `mirror_sync(incremental=True, trigger_type="schedule")`(夜間增量、全部來源表)。`run_etl` 保留為手動 fallback,`scheduler` **不再派它**。

## 設計要點

- 依賴 task-004:`mirror_sync` 已接受 `incremental` 與 `trigger_type`。
- `build_scheduled_tasks`:對每筆啟用排程產出:
  - `task_name="mirror_sync"`,kwargs `{"incremental": True, "trigger_type": "schedule"}`(全表增量;`schema`/`table`/`tables` 皆省略 = 全量偵測)。
  - `schedule_id=f"schedule-{schedule.pid}"`、`cron=schedule.cron_expr`、`cron_offset=CRON_OFFSET_TAIPEI`(UTC+8)沿用。
  - **不**傳 `schedule_pid`/`etl_table_pid`(`mirror_sync` 不接受這些參數;sync 為全表增量,逐表無意義)。
- 移除對 `RUN_ETL_TASK_NAME` 的派工;加 `MIRROR_SYNC_TASK_NAME = "mirror_sync"`。`run_etl` 定義保留(手動 fallback 仍可經既有手動觸發路徑呼叫),但 scheduler 不引用。
- `import app.worker.tasks` 確保 `mirror_sync` 註冊;`DbScheduleSource.get_schedules`(取 enabled + 未刪除)不變。
- 停用 / 已刪除排程一律不派工(沿用既有跳過)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_scheduler_v130.py -q` 全綠(以假 `Schedule` 物件呼叫 `build_scheduled_tasks`,純函式不連 DB):
  - 啟用排程 → 產出 `task_name == "mirror_sync"`、kwargs `incremental=True` 且 `trigger_type="schedule"`、**不含** `etl_table_pid`/`schedule_pid`
  - cron / cron_offset(UTC+8)沿用來源排程;`schedule_id == f"schedule-{pid}"`
  - 停用 / 已刪除排程 → 不產出 task
  - 產出中無任何 `task_name == "run_etl"`(排程不再派 run_etl)
- [ ] `uv run python -c "from app.worker.scheduler import build_scheduled_tasks, MIRROR_SYNC_TASK_NAME; print(MIRROR_SYNC_TASK_NAME)"` 印出 `mirror_sync`
- [ ] `uv run ruff check . && uv run mypy app` green

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/00-overview/05-timezone.md`
