---
id: task-011
title: 前端排程管理 + 執行紀錄 / 逐表詳細 log 頁
status: pending
parallel: true
depends_on: [task-005, task-009]
affected_files:
  - frontend/src/app/(main)/schedules/page.tsx
  - frontend/src/app/(main)/runs/page.tsx
  - frontend/src/app/(main)/runs/[uid]/page.tsx
  - frontend/src/lib/api/scheduleApi.ts
  - frontend/src/lib/api/runApi.ts
  - frontend/src/components/runs/RunLogTable.tsx
estimated_hours: 4
---

## 目標

排程管理頁(CRUD + 啟停 + 手動觸發按鈕)與執行紀錄頁:run 清單(狀態 / 觸發方式 / 起訖)、單 run 明細頁顯示**逐表詳細 log**(表名 / 讀寫筆數 / 耗時 / 狀態 / 錯誤明細含 stack trace 展開)。

## 範圍要點

- 串 task-005 API;run 清單與 log 支援狀態過濾與分頁。
- 手動觸發後即時反映新 run(RTK Query invalidate)。
- 錯誤明細(stack trace)預設收合、點擊展開;失敗表列醒目標示。
- viewer 角色:排程寫入與手動觸發控件隱藏或 disabled。
- 時間顯示 UTC+8 走 `utils/datetime.ts`;**不改** `(main)/layout.tsx`。

## Acceptance

- [ ] `cd frontend && npm run lint && npx tsc --noEmit` 全綠
- [ ] `cd frontend && npm run build` 成功
- [ ] `! git diff --name-only | grep -q "app/(main)/layout.tsx"` 成立(未動 layout)
- [ ] 手測 case(記錄於 task 完成註記):建排程、啟停、手動觸發出現新 run、run 明細逐表 log 欄位齊全、失敗 run 可展開 stack trace

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md` + `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/02-frontend/05-components.md`
