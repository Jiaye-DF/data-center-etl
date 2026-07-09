---
id: task-005
title: 進度前端 — 全域 SyncProgress sticky bar(輪詢 /runs/active)
status: pending
parallel: false
depends_on: [task-002, task-004]
affected_files:
  - frontend/src/components/sync/SyncProgress.tsx
  - frontend/src/lib/api/runApi.ts
  - frontend/src/app/(main)/layout.tsx
estimated_hours: 2.5
model: sonnet
effort: medium
---

## 目標

任何同步(手動或排程)執行中,所有已登入(admin)頁面頂部顯示 sticky 進度條:「同步中 — 已完成 n / 共 N 表」+ 成功/失敗/略過計數與百分比;無執行中不渲染、完成後自行消失。

## 實作要點

1. `lib/api/runApi.ts` 加 `getActiveRun` query(`GET /runs/active`,`pollingInterval: 5_000`,`skipPollingIfUnfocused: true`);response 型別對齊 task-002 schema(`data` 可為 null)。**僅新增 endpoint,勿動既有 triggerRun(006 處理)。**
2. 新元件 `components/sync/SyncProgress.tsx`:`data` 為 null → 回 null;有 active run → sticky 條(置頂,不遮 Header 操作),含進度條(percent = processed/total,total=0 防呆)、計數、觸發方式(對齊 `TRIGGER_TYPE_LABELS`)。完成(下一輪 poll 回 null)自然消失;失敗計數 > 0 以 danger 色標示。字級 ≥14px、RWD 不破版。
3. 掛載 `(main)/layout.tsx`(main 內容區之上);non-admin 已被 004 導向 `/no-access`,元件仍以 `isAdmin` 守門避免對 403 端點空輪詢。
4. 輪詢節制:視窗未聚焦不輪詢(RTK Query 選項);**不**做 websocket。

## Acceptance

- [ ] `npm run typecheck` 通過;`npm run lint`(--max-warnings=0)通過
- [ ] `[ -f frontend/src/components/sync/SyncProgress.tsx ]` 為真
- [ ] `docker compose up -d --build frontend` 後手測:觸發全量同步 → 數秒內任一頁面(儀表板/排程/runs)頂部出現進度條且 n/N 隨執行推進;完成後消失;無同步時重整不出現
- [ ] 同步含失敗表時,進度條呈現失敗計數(danger 色)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
