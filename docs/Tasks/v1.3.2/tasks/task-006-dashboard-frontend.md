---
id: task-006
title: 總覽儀表板前端 — dashboardApi + 改寫總覽頁(四塊 + 保留導覽卡)
status: done
parallel: true
depends_on: [task-005]
affected_files:
  - frontend/src/lib/api/dashboardApi.ts
  - frontend/src/app/(main)/page.tsx
estimated_hours: 2
---

## 目標

新增 `dashboardApi.ts`(`useDashboardOverviewQuery`);改寫 `(main)/page.tsx`:上方加四塊(同步健康 / 待處理失敗表〔可點進 run log〕/ 下一班排程〔以 `nextRunFromCron` 由啟用中相異 cron 取最近一班〕/ 資料規模+快照新鮮度),下方保留原 4 張導覽卡。回溯記錄:已於 commit `8f00507` 落地。

## Acceptance

- [x] `cd frontend && npm run typecheck` 綠(exit 0)
- [x] `cd frontend && npm run lint` 綠(eslint --max-warnings=0)
- [x] `[ -f frontend/src/lib/api/dashboardApi.ts ]` 且 `grep -q "useDashboardOverviewQuery"`
- [x] `grep -q "同步健康" frontend/src/app/(main)/page.tsx`(四塊已渲染)
- [x] `grep -q "nextRunFromCron" frontend/src/app/(main)/page.tsx`(下一班以 cron 推算)

## 必讀檔(Just-in-time)

- `02-frontend/00-overview.md`
- `02-frontend/01-routing-and-error.md`
- `02-frontend/02-api-and-state.md`
- `02-frontend/04-datetime.md`
- `02-frontend/06-rwd.md`
