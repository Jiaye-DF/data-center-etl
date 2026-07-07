---
id: task-009
title: 前端登入頁(雙軌)+ 後台佈局殼 + auth guard
status: done
parallel: true
depends_on: [task-002, task-003]
affected_files:
  - frontend/src/app/login/page.tsx
  - frontend/src/middleware.ts
  - frontend/src/app/(main)/layout.tsx
  - frontend/src/app/(main)/page.tsx
  - frontend/src/lib/api/authApi.ts
  - frontend/src/lib/auth/useAuth.ts
  - frontend/src/app/error.tsx
  - frontend/src/app/global-error.tsx
estimated_hours: 4
---

## 目標

建立後台的登入與外殼:登入頁(本地帳密表單 + DF-SSO 登入按鈕雙軌)、auth guard(未登入導向 /login)、`(main)` 佈局殼含側邊導覽(**一次建好** tables / schedules / runs 三個 nav 項,010/011 不再改 layout)。

## 範圍要點

- 認證走 httpOnly cookie(`02-frontend/03-env-and-auth.md`),前端不落 token 於 localStorage;SSO 按鈕導向 backend SSO 端點(task-003)。
- API 集中 RTK Query(`baseApi.ts` 既有,injectEndpoints 建 `authApi.ts`)。
- 角色感知:`useAuth` 暴露 role,viewer 隱藏寫入類 UI(細部頁面控制由 010/011 實作,本 task 提供 hook)。
- 路由錯誤邊界補齊(`error.tsx` / `global-error.tsx`,`01-routing-and-error.md`)。
- **互鎖註記**:`(main)/layout.tsx` 只屬本 task;010/011 各自新增 route 目錄,不回頭改 layout。

## Acceptance

- [x] `cd frontend && npm run lint && npx tsc --noEmit` 全綠(TS strict、禁 any)
- [x] `cd frontend && npm run build` 成功
- [x] `grep -q "tables" frontend/src/app/\(main\)/layout.tsx && grep -q "schedules" frontend/src/app/\(main\)/layout.tsx && grep -q "runs" frontend/src/app/\(main\)/layout.tsx` 成立(三 nav 項一次建好)
- [x] `! grep -rn "localStorage" frontend/src/lib/auth/` 成立(token 不落 localStorage)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`(永遠讀)
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/03-env-and-auth.md` + `docs/Design-Base/90-third-party-service/08-df-sso.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
