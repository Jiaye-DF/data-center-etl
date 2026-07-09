---
id: task-004
title: RBAC 前端 — member 無權限頁 + 路由守衛 + 導覽隱藏
status: done
parallel: true
depends_on: []
affected_files:
  - frontend/src/app/(main)/layout.tsx
  - frontend/src/app/(main)/no-access/page.tsx
  - frontend/src/components/layout/Sidebar.tsx
estimated_hours: 2
model: sonnet
effort: medium
---

## 目標

非 admin(member/viewer)登入後不再看到任何 ETL 後台頁面:一律導向新頁 `/no-access`,該頁說明無權限緣由與洽詢管道;側邊導覽對非 admin 隱藏。admin 體驗完全不變。

## 實作要點

1. 新頁 `app/(main)/no-access/page.tsx`:置中卡片版面(對齊既有 df-card 視覺),文案繁中,大意 —— 標題「無存取權限」;內文:您目前的帳號為一般成員(member),無權限查看資料中心的資料層設定、同步排程與 ETL 後台資訊;如業務上需要存取,請洽資訊團隊(系統負責團隊)申請權限。附登出按鈕(用 `useAuth().logout`)。字級遵守 ≥14px 地板。
2. `(main)/layout.tsx` 守衛(既有 auth guard 之後):`isAdmin === false` 且 pathname ≠ `/no-access` → `router.replace('/no-access')`;admin 誤入 `/no-access` → `router.replace('/')`。判斷須等 `isLoading` 結束,避免閃爍(可沿用現有 loading 擋板)。
3. `Sidebar.tsx`:非 admin 不渲染導覽項(或整個 sidebar 不渲染,取視覺較不破版者);Header 保留(要能登出)。
4. 僅 UI 守衛,API 403 由 task-003 把關(縱深防禦);**不**新增角色值、**不**做權限管理 UI。

## Acceptance

- [ ] `npm run typecheck` 通過;`npm run lint`(--max-warnings=0)通過
- [ ] `[ -f frontend/src/app/(main)/no-access/page.tsx ]` 為真
- [ ] `docker compose up -d --build frontend` 後手測:viewer 登入 → 任一路徑(`/`、`/runs`、`/sources`)皆落在 `/no-access` 且無側邊導覽;文案含「洽」與「權限」字樣;admin 登入行為與現行完全相同
- [ ] viewer 於 `/no-access` 可登出並回登入頁

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/03-env-and-auth.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
