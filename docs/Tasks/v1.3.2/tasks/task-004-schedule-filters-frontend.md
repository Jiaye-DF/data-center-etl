---
id: task-004
title: 排程前端 — 業務名欄改名 + 資料總筆數/排程時段篩選 + Segmented 抽共用
status: done
parallel: true
depends_on: [task-002]
affected_files:
  - frontend/src/components/schedules/ScheduleTableBrowser.tsx
  - frontend/src/lib/api/scheduleApi.ts
  - frontend/src/components/common/Segmented.tsx
estimated_hours: 3
---

## 目標

排程頁欄位標題「業務名」→「業務資料表名稱」(對齊 source/target 頁);進階篩選加「資料總筆數」(膠囊)與「排程時段」(HH:MM 起訖)兩列,批次啟停 payload 帶新篩選;膠囊選擇器抽為共用 `Segmented` 元件。回溯記錄:已於 commit `967400e` 落地。

## Acceptance

- [x] `cd frontend && npm run typecheck` 綠(exit 0)
- [x] `cd frontend && npm run lint` 綠(eslint --max-warnings=0)
- [x] `grep -q "業務資料表名稱" frontend/src/components/schedules/ScheduleTableBrowser.tsx`(欄位改名)
- [x] `grep -q "排程時段" frontend/src/components/schedules/ScheduleTableBrowser.tsx`(時段篩選存在)
- [x] `grep -Eq "rows|timeFrom|timeTo" frontend/src/lib/api/scheduleApi.ts`(新參數串接)
- [x] `[ -f frontend/src/components/common/Segmented.tsx ]`(共用元件存在)

## 必讀檔(Just-in-time)

- `02-frontend/00-overview.md`
- `02-frontend/02-api-and-state.md`
- `02-frontend/05-components.md`
- `02-frontend/06-rwd.md`
