---
id: task-010
title: 前端 API Client 頁整合(Role 指派 + 特例綁定 + 權限檢視)
status: pending
parallel: true
depends_on: [task-007, task-008]
affected_files:
  - frontend/src/app/(main)/api-clients/page.tsx
  - frontend/src/lib/api/apiClientApi.ts
estimated_hours: 3
model: sonnet
effort: high
---

## 目標

在既有「API Client 設定」頁整合權限指派與檢視(user 裁定:頁內檢視,不另開頁):每列提供 Role 指派(0..1)、特例綁定(0..N 含效期)、與「檢視權限」面板(顯示 effective-permissions 計算結果)。

## 實作要點

- 每列操作區(垂直鈕組)追加「權限」入口 → 面板含三段:目前 Role(下拉指派 / 解除)、特例綁定清單(綁定含 expires_at 選填、過期標示、解除)、最終可見欄位(`{作業: {表: {欄位: read/edit}}}` 樹狀 / 分組呈現,空結構顯示 default-closed 提示文案)。
- endpoints 加入 `apiClientApi.ts`(指派 / 綁定 / 預覽;寫入 invalidate 預覽 tag);效期輸入沿用 `utils/datetime` 顯示慣例。
- 既有建立 / 輪替 / 啟停 / 註銷流程與 Credentials UI 不動;新增操作走 ConfirmDialog 慣例(解除指派 / 解除綁定)。

## Acceptance

- [ ] `npm run lint` + `npm run typecheck` 乾淨
- [ ] `docker compose up -d --build` 後手測:指派 Role → 檢視面板即時反映;綁過期特例不出現在最終權限、未過期出現;解除 Role 後預覽變空
- [ ] 既有 api-clients 頁功能(建立 / 輪替 / 註銷 / Credentials 檢視)迴歸正常

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
