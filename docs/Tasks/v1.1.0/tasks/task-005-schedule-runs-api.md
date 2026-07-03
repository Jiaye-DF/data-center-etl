---
id: task-005
title: 排程 / 執行紀錄與詳細 log / 手動觸發 API
status: done
parallel: false
depends_on: [task-004, task-007]
affected_files:
  - backend/app/api/v1/schedules.py
  - backend/app/api/v1/runs.py
  - backend/app/api/v1/__init__.py
  - backend/app/schemas/schedule.py
  - backend/app/schemas/run.py
  - backend/app/services/schedule_service.py
  - backend/app/repositories/schedule_repo.py
  - backend/app/repositories/run_repo.py
  - backend/tests/test_schedule_api.py
  - backend/tests/test_runs_api.py
estimated_hours: 4
---

## 目標

提供排程管理(CRUD + 啟停)、執行紀錄查詢(run 清單 + 單 run 之**逐表詳細 log**)、手動觸發一次執行(enqueue 至 taskiq,task 定義屬 task-007)之 API。

## 範圍要點

- schedules:cron 式定義 + 啟停;時間欄位/顯示一律 UTC+8(`05-timezone.md`)。
- runs 查詢:run 清單(狀態/觸發方式/起訖,分頁)、單 run 逐表 log(表名/筆數/耗時/狀態/錯誤明細),支援依狀態過濾。
- 手動觸發:呼叫 task-007 的 taskiq task `.kiq(...)` enqueue,回傳 run uid;測試以 mock broker(InMemoryBroker)驗證 enqueue,不需真 redis。
- 寫入類 API 掛 `require_admin`;查詢掛 `require_login`。
- **互鎖註記**:`api/v1/__init__.py` 序列化在 task-004 之後(`parallel: false`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_schedule_api.py tests/test_runs_api.py -q` 全綠,涵蓋:排程 CRUD/啟停、run 清單分頁、單 run 逐表 log 欄位齊全(筆數/耗時/狀態/錯誤)、手動觸發 enqueue 成功、viewer 寫入 403
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md` + `01-routing.md` + `02-auth.md`
- `docs/Design-Base/00-overview/05-timezone.md` + `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`(log 查詢分頁/索引)
- `docs/Design-Base/03-backend/07-testing.md`
