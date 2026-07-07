---
id: task-005
title: 總覽儀表板後端 — 聚合端點 /dashboard/overview + repo 聚合方法
status: done
parallel: false
depends_on: [task-001, task-002]
affected_files:
  - backend/app/schemas/dashboard.py
  - backend/app/services/dashboard_service.py
  - backend/app/api/v1/dashboard.py
  - backend/app/api/v1/__init__.py
  - backend/app/repositories/run_repo.py
  - backend/app/repositories/rds_table_meta_repo.py
  - backend/app/repositories/schedule_repo.py
estimated_hours: 3
---

## 目標

單一聚合端點 `GET /dashboard/overview` 回四塊:同步健康(最新 run + 近 20 次成功/失敗)、待處理失敗表(最新 run 失敗逐表,可點進 log)、排程概況(啟用數/總表數 + 啟用中相異 cron)、資料規模+快照新鮮度(source/target)。全讀自有 DB,**不打 RDS**。repo 加 `RunRepository.latest_run/recent_run_stats`、`ScheduleRepository.enabled_cron_exprs`、`RdsTableMetaRepository.dataset_scale`。回溯記錄:已於 commit `8f00507` 落地。

> **序列化理由**:本 task 於 `rds_table_meta_repo.py`(task-001 owns)、`schedule_repo.py`(task-002 owns)追加方法 → `parallel: false` + `depends_on: [001,002]`,避免同檔並行衝突。

## Acceptance

- [x] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/dashboard/overview"` == 401(路由存在、需授權)
- [x] `git show 8f00507:backend/app/api/v1/__init__.py | grep -q "dashboard.router"`(router 已註冊)
- [x] `cd backend && uv run pytest -q` 全綠(205 passed)
- [x] `cd backend && ruff check app` 通過;`mypy app` 無新增錯誤
- [x] service 僅讀 `etl_runs`/`etl_run_logs`/`schedules`/`rds_table_meta`,無 RDS 連線

## 必讀檔(Just-in-time)

- `03-backend/00-overview.md`
- `03-backend/01-routing.md`
- `03-backend/03-async-and-tx.md`
- `03-backend/08-performance.md`
- `04-databases/09-indexes-and-perf.md`
