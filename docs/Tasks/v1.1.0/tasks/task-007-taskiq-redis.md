---
id: task-007
title: taskiq + redis 排程服務(broker / worker task / scheduler)
status: pending
parallel: true
depends_on: [task-006]
affected_files:
  - backend/app/worker/__init__.py
  - backend/app/worker/broker.py
  - backend/app/worker/tasks.py
  - backend/app/worker/scheduler.py
  - backend/tests/test_worker.py
estimated_hours: 3
---

## 目標

建立 taskiq + redis 的排程執行層:broker(redis,URL 走 env)、worker task `run_etl`(呼叫 task-006 engine 並確保 run 狀態落 DB)、scheduler(讀自有 DB `schedules` 啟用中排程,到點派工)。經 user 明示採用 taskiq / redis(不在鎖定棧,已於 propose 註記)。

## 範圍要點

- `broker.py`:redis URL 由 env(`REDIS_URL`)注入,缺值 fail-fast;測試環境自動退 InMemoryBroker。
- `tasks.py`:`run_etl(run 觸發參數)`,建立 `etl_runs` 紀錄 → 呼叫 engine → 任何例外都要把 run 標 failed + log 錯誤明細(不可留 running 殭屍狀態)。
- `scheduler.py`:taskiq scheduler 以 DB 排程為來源(自訂 schedule source 讀 `schedules` 表),cron 解讀採 **UTC+8**(`05-timezone.md`);停用排程不派工。
- worker / scheduler 各自可獨立啟動(供 task-012 容器 command 使用),啟動指令寫進模組 docstring。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_worker.py -q` 全綠(InMemoryBroker),涵蓋:enqueue → run 建立且完成後狀態正確、engine 拋例外 run 標 failed、停用排程不產生派工
- [ ] `! grep -nE "redis://[^$'\"]*['\"]" backend/app/worker/` 成立(無硬編 redis URL)
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md` + `03-async-and-tx.md`
- `docs/Design-Base/03-backend/04-config.md` + `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/00-overview/05-timezone.md`(cron 時區)
- `docs/Design-Base/00-overview/01-versions.md`(依賴版本由 task-001 已鎖,不動 pyproject)
