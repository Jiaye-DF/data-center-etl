---
id: task-006
title: 前端「API Client 設定」sidebar 區塊 + 管理頁
status: pending
parallel: true
depends_on: [task-005]
affected_files:
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
estimated_hours: 4
---

## 目標

sidebar 新增「**API Client 設定**」獨立 nav 區塊(user 裁定:與既有使用者 / 角色選單**分開**,不得併入同一群組),下掛 API Client 管理頁,串 task-005 的 `/api/v1/api-clients`。

## 規格

- **Sidebar**:新增獨立區塊(自成一組,位置在既有系統管理 / 使用者選單之外),nav 項「API Client 設定」→ `/api-clients`;admin-only 顯示(比照既有 users 頁的角色 gating 寫法)。
- **管理頁 `app/(main)/api-clients/page.tsx`**(單頁完成,**不**拆多個子頁——對齊「別過度拆成新頁」原則):
  - 列表:name / client_id(可複製)/ status(啟用中 · 已停用)/ 每分鐘上限 / 每 10 分鐘上限 / active secret 數 / 建立時間(走既有 `utils/datetime` 顯示慣例)。
  - 建立 dialog:輸入 name / description → 成功後顯示 **client_id + client_secret 一次性面板**(強調「關閉後不再顯示」,附複製按鈕;關閉需二次確認)。
  - 輪替 secret dialog:同樣一次性顯示新 secret;已有 2 把 active 時按鈕禁用並提示先汰舊。
  - secret 清單(每 client 展開或 dialog):顯示各把建立時間 / 狀態,提供「汰換」操作(二次確認)。
  - 編輯:name / description / 限流兩參數(數字欄位,min 1)/ 啟用停用 toggle(停用需二次確認,文案講明「該系統將立即無法取得 token」)。
- **API 層 `lib/api/apiClientApi.ts`**:RTK Query,比照既有 `userApi.ts` 寫法掛 `baseApi` tag(list 失效重取);**TypeScript strict、禁 any**。
- ID 顯示規範:介面只出現 `uid` / `client_id`,不顯示 pid(對齊前端 ID 隱藏規範)。

## Acceptance

- [ ] `cd frontend && npm run lint` + `npx tsc --noEmit` 無新增錯誤
- [ ] `npm run build` 成功
- [ ] 手測清單(docker compose 起前後端;結果記入 task 完成註記,截圖非必要):
  - sidebar 出現「API Client 設定」獨立區塊,非 admin 登入不可見
  - 建立 Client → 一次性 secret 面板顯示、複製可用;重新整理後列表無明文 secret
  - 編輯限流參數存檔 → 列表值更新;停用 toggle 後(搭配 task-004 完成的環境)`POST /api/client/v1.0/token` 回 401
  - 輪替至 2 把 active 後輪替鈕禁用;汰換一把後恢復可用
  - 既有使用者 / 角色頁行為不變(sidebar 原有項目位置不動)
- [ ] 既有頁面 route 無回歸(`npm run build` 全頁面編譯通過即視為機械驗證)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
