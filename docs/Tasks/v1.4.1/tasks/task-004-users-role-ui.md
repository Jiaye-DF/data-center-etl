---
id: task-004
title: 前端 — 使用者與角色管理檢視(admin only)+ API 串接
status: done
parallel: false
depends_on: [task-003]
affected_files:
  - frontend/src/lib/api/userApi.ts
  - frontend/src/app/(main)/users/page.tsx
  - frontend/src/components/users/UserRoleTable.tsx
  - frontend/src/components/layout/Sidebar.tsx
estimated_hours: 3.5
---

## 目標

admin 可在系統內查看使用者清單並指派角色:**單一**新檢視「使用者與角色」併入既有頁面體系(對齊「別過度拆成新頁」原則,不為此開多個新頁),viewer 看不到入口且直開被導走。

## 規格

- `userApi.ts`:RTK Query 集中(`baseApi` injectEndpoints,對齊既有 `runApi.ts` / `scheduleApi.ts` 慣例)— `GET /roles`、`GET /users`、`PATCH /users/{uid}/role`(指派後 invalidate 使用者清單 tag)
- `(main)/users/page.tsx`:使用者清單頁(admin only)
  - 欄位:帳號 / 顯示名稱 / 登入來源(SSO / 本地,以 badge 呈現)/ 角色
  - 角色欄提供下拉指派(選項來自 `GET /roles`),變更前以既有 `ConfirmDialog` 確認,成功後清單即時刷新
  - **自己那一列的角色下拉停用**並附提示(防呆對齊後端 403,不讓使用者踩到才知道)
  - 錯誤處理沿用既有 API 錯誤呈現慣例;分頁沿用 `Pagination` 共用元件
- `Sidebar.tsx`:新增「使用者與角色」入口,**僅 admin 顯示**(沿用 v1.4.0 RBAC 導覽隱藏模式)
- 路由守衛:viewer 直開 `/users` → 導向既有 `no-access`(沿用 `(main)/layout.tsx` 既有守衛機制;若既有機制已按 role 全域涵蓋則不需改 layout,**禁**另造守衛)
- 禁 `any`;字級 / 觸控目標 / RWD 對齊 `02-frontend/06-rwd.md`

## Acceptance

- [ ] `cd frontend && npm run typecheck && npm run lint && npm run build` 全綠
- [ ] `grep -rn "any" frontend/src/lib/api/userApi.ts frontend/src/components/users/ | grep -v "// eslint"` 無型別 `any` 命中(手動覆核 grep 結果)
- [ ] 手測(`docker compose up -d --build` 後):
  - admin 登入 → Sidebar 見「使用者與角色」→ 清單顯示帳號 / 顯示名稱 / 登入來源 / 角色
  - 將某 viewer 指派為 admin,重新整理後該使用者權限即時反映(以該帳號操作寫入功能驗證);再降回 viewer 恢復唯讀
  - admin 自己那列的角色下拉為停用狀態
  - viewer 登入 → Sidebar 無入口;直開 `/users` 被導至 no-access

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
