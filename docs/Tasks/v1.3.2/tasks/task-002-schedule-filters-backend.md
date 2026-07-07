---
id: task-002
title: 排程進階篩選後端 — 資料總筆數 + 排程時段 + 批次啟停一致
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/schemas/schedule.py
  - backend/app/services/schedule_service.py
  - backend/app/api/v1/schedules.py
  - backend/app/repositories/schedule_repo.py
estimated_hours: 4
---

## 目標

排程逐表列表加「資料總筆數」(rows: all/nonempty/empty)與「排程時段」(time_from/time_to,HH:MM;以 `split_part(cron_expr)`+`CASE` 換算 minute-of-day,非每日純數字 cron 排除)篩選;「僅啟用/停用符合篩選排程」批次操作同步吃新篩選,與列表命中集合一致。**未引入 cron 解析套件**。回溯記錄:已於 commit `967400e` 落地。

## Acceptance

- [x] `curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/v1/schedules?schema=DS&rows=nonempty&time_from=14:00&time_to=15:00"` == 401(參數綁定通過)
- [x] `git show 967400e:backend/app/schemas/schedule.py | grep -Eq "filter_rows|filter_time_from|filter_time_to"`(批次篩選欄齊)
- [x] `cd backend && uv run pytest tests/test_schedule_repo_v131.py tests/test_schedule_api_v131.py -q` 全綠
- [x] `cd backend && ruff check app` 通過;`mypy app` 無新增錯誤
- [x] 時段以 minute-of-day 比較,非數字/週期 cron 以 `CASE` 回 NULL 排除(不進 int cast)

## 必讀檔(Just-in-time)

- `03-backend/00-overview.md`
- `03-backend/01-routing.md`
- `04-databases/04-sql-safety.md`
- `00-overview/05-timezone.md`
- `04-databases/06-timezone.md`
