---
id: task-006
title: 前端 排程友善 UI(下拉/時間選擇取代 cron 5 欄,預設全跑)
status: pending
parallel: true
depends_on: []
affected_files:
  - frontend/src/app/(main)/schedules/page.tsx
  - frontend/src/components/schedules/CronFriendlyPicker.tsx
  - frontend/src/utils/cron.ts
  - frontend/src/lib/api/scheduleApi.ts
estimated_hours: 3
---

## 目標

排程建立 / 編輯改用**友善 UI**:下拉選頻率(每日 / 每週 / 每月)+ 時間選擇(時:分,週幾 / 幾號),取代原始 cron 5 欄位輸入(使用者看不懂「分 時 日 月 週」)。排程**預設涵蓋全部表**(執行範圍預設「全部啟用表」)。內部仍以 cron 字串存後端(既有 API 不變)。

## 設計要點

- `utils/cron.ts`:友善設定 ↔ cron 字串雙向轉換。
  - 支援型別:每日 `分 時 * * *`、每週 `分 時 * * 週`、每月 `分 時 日 * *`。
  - `toCron(friendly)` / `fromCron(cronExpr)`(既有排程編輯時解析回填;無法解析的自訂 cron 保留「進階(原始 cron)」退路)。
  - 時間一律 UTC+8 語意(對齊既有排程,`00-overview/05-timezone.md`)。
- `components/schedules/CronFriendlyPicker.tsx`:頻率下拉 + 對應時間 / 週幾 / 日期選擇器;輸出 cron 字串 + 顯示人類可讀摘要(如「每天 03:30」)。可切「進階」露原始 cron 欄。
- `schedules/page.tsx`:`ScheduleForm` 的 cron 欄改用 `CronFriendlyPicker`;執行範圍預設「全部啟用表」(既有 select 預設值)。編輯既有排程時以 `fromCron` 回填,不能解析則落「進階」。
- `scheduleApi.ts`:契約不變(仍送 `cron_expr`);若無需改動可不動,但列入 affected 以防微調。

## Acceptance

- [ ] `cd frontend && npm run typecheck && npm run lint` green(strict,禁 any)
- [ ] `npm run build` 成功
- [ ] `utils/cron.ts` 具單元可驗性:`toCron({freq:'daily',hour:3,minute:30})` === `'30 3 * * *'`;`fromCron('30 3 * * *')` 還原對應 friendly(以 vitest/jest 或於 build 前 tsx 斷言;若無測試框架則於 PR 描述附 REPL 驗證)
- [ ] 頁面實測:新增排程不需輸入 cron 字串即可建立(選每天 + 03:30)→ 送出後端 `cron_expr='30 3 * * *'`;執行範圍預設全部啟用表
- [ ] 編輯既有 `30 3 * * *` 排程時 UI 正確回填為「每天 03:30」;自訂 cron(如 `*/5 * * * *`)落「進階」原始欄不報錯

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
- `docs/Design-Base/00-overview/05-timezone.md`
