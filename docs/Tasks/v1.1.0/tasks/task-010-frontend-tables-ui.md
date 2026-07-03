---
id: task-010
title: 前端 Data Table 管理頁(清單 / 啟停 / mapping / Comment)
status: done
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

## 完成註記(worker: claude-D,2026-07-03)

- **實作**:`etlConfigApi.ts`(RTK Query injectEndpoints:list / detail / enable / disable / replaceMappings,tag `EtlTable` 失效重取;export `extractApiErrorDetail` 供三處共用)、`TableList.tsx`(清單 + 啟停 + 分頁,viewer 隱藏操作欄)、`MappingEditor.tsx`(逐欄編輯 + 缺 Comment 紅框醒目標示 + 400 顯示後端訊息,viewer 全 disabled)、`tables/page.tsx` / `tables/[uid]/page.tsx`。未動 `(main)/layout.tsx`。
- **Acceptance 實跑**:`npm run lint` ✅ / `npx tsc --noEmit` ✅ / `npm run build` ✅ / layout.tsx 未動 ✅。
- **手測(文字記錄;本地 dev:frontend :3000 + backend uvicorn :8001 + etl_postgres,seed 4 表 23 mappings;Playwright headless 實操 UI,截圖存 session scratchpad 01–06\*.png):**
  1. 清單顯示 seed 的表 ✅ — 4 列(DS.GAT_FILE / GAQ_FILE / GAM_FILE / GAT_FILE,GAQ_FILE→M2201),含目標表 / 欄位數 / 啟用 badge /「尚未執行」。
  2. 停用切換成功 ✅ — admin 點 GAM_FILE「停用」→ badge 變停用、按鈕變啟用(refetch 後),DB `is_enabled=false`;再切回啟用復原。
  3. mapping 編輯儲存成功 ✅ — 明細頁改 GAM_ID comment 後儲存,顯示「mapping 已儲存」且 refetch 帶回新值;另驗缺 Comment 儲存 → 紅框「缺 Comment(必填)」+ 後端 400 訊息「目標欄位 GAM_ID 缺少 comment(每欄位必帶 Comment)」;測後資料已復原。
  4. viewer 登入看不到編輯控件 ✅ — 以 `viewer-test`(手測用,直插 DB 之 viewer 帳號,留存於本地 dev DB)登入:清單無「操作」欄與啟停鈕、明細無「停用此表 / 新增欄位 / 儲存 mapping」鈕、輸入框全 disabled;API 層 viewer POST disable 實測 403。
- **備註**:手測用瀏覽器自動化(claude-in-chrome)因多瀏覽器需人工選擇無法在無人值守流程使用,改以 Playwright(npx,未動專案依賴)完成;ApiEnvelope 共用抽檔受白名單限制,見 `fixed.md §16`。
