---
id: task-002
title: 進度後端 — create_run 帶 total_tables + GET /runs/active
status: done
parallel: false
depends_on: [task-001, task-003]
affected_files:
  - backend/app/etl/engine.py
  - backend/app/worker/tasks.py
  - backend/app/api/v1/runs.py
  - backend/app/schemas/run.py
  - backend/app/repositories/run_repo.py
  - backend/tests/test_runs_api.py
estimated_hours: 3
model: sonnet
effort: high
---

## 目標

執行中的 run 就能讀到進度分母與逐狀態計數:建 run 當下寫入 `total_tables`;新增 `GET /api/v1/runs/active` 回「最新一筆 running run + 進度計數」,供前端進度條輪詢。

## 實作要點

1. `etl/engine.py`:`RunStore` protocol 與 `DbRunStore.create_run` 加 `total_tables: int` 參數(建 run 即寫入 `etl_runs.total_tables`;收尾 `finish_run` 覆寫最終值,語意不變);`worker/tasks.py` 的 `RunStateTracker.create_run` 同步簽名,呼叫端傳 `len(configs)`。**只加參數,勿動 001 已改的併發結構。**
2. 分子**不加新寫入**:讀端由 `etl_run_logs` 聚合。`repositories/run_repo.py` 加:取最新 `status='running'` 未刪除 run;依 run_pid 聚合 log 逐狀態計數(success/failed/skipped/running,一次 GROUP BY)。
3. `api/v1/runs.py` 加 `GET /runs/active`(**置於 `/runs/{uid}` 動態路由之前**,避免 path 被吃):無執行中 run → `data: null`;有 → run uid/trigger_type/started_at/total_tables + 計數(processed = success+failed+skipped)。回應殼 ApiResponse;schema 寫在 `schemas/run.py`。
4. 權限對齊 003 收緊後的基準:`require_admin`(003 已把 runs router 全面收緊,新端點跟隨)。
5. 測試加在 `tests/test_runs_api.py`:無 running 回 null;造一筆 running run + 部分 log 斷言計數;未帶 token 401;viewer 403。

## Acceptance

- [x] `uv run pytest tests/test_runs_api.py` 全綠(含上列新測試)
- [x] `uv run pytest` 全綠;`uv run ruff check .` 通過;`uv run mypy .` 無新增錯誤
- [ ] `docker compose up -d --build backend` 後:`curl -fsS http://localhost:8000/api/v1/runs/active` 未帶 token 回 401(`| grep 401` 或 -w 驗 status)— 待 orchestrator 手測
- [ ] 手動觸發全量同步後立即查 `/runs/active`(admin token):`total_tables > 0` 且 processed 隨執行遞增 — 待 orchestrator 手測

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
