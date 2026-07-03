---
id: task-010
title: 前端 Data Table 管理頁(清單 / 啟停 / mapping / Comment)
status: pending
parallel: true
depends_on: [task-004, task-009]
affected_files:
  - frontend/src/app/(main)/tables/page.tsx
  - frontend/src/app/(main)/tables/[uid]/page.tsx
  - frontend/src/lib/api/etlConfigApi.ts
  - frontend/src/components/tables/TableList.tsx
  - frontend/src/components/tables/MappingEditor.tsx
estimated_hours: 4
---

## 目標

「所有 Data Table 的 ETL 皆可於後台管理」的核心 UI:表清單頁(來源 / 目標 / 啟用狀態 / 最近執行狀態)、單表明細頁(mapping 欄位對照 + 欄位 Comment 編輯、啟用/停用切換)。

## 範圍要點

- 串 task-004 API(RTK Query injectEndpoints 建 `etlConfigApi.ts`);清單分頁。
- viewer 角色:啟停 / 編輯控件隱藏或 disabled(用 task-009 `useAuth`)。
- mapping 編輯器逐欄顯示 comment,缺 comment 欄位醒目標示;儲存失敗(400)顯示後端訊息。
- 日期時間顯示走 `utils/datetime.ts`(既有,`02-frontend/04-datetime.md`)。
- **不改** `(main)/layout.tsx`(nav 已由 009 建好)。

## Acceptance

- [ ] `cd frontend && npm run lint && npx tsc --noEmit` 全綠
- [ ] `cd frontend && npm run build` 成功
- [ ] `! git diff --name-only | grep -q "app/(main)/layout.tsx"` 成立(未動 layout)
- [ ] 手測 case(worker 截圖或文字記錄於 task 完成註記):清單顯示 seed 的表、停用切換成功、mapping 編輯儲存成功、viewer 登入看不到編輯控件

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`(reuse 必抽)
- `docs/Design-Base/02-frontend/06-rwd.md`
