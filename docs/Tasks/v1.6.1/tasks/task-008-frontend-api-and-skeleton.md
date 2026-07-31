---
id: task-008
title: 前端 API 層 + 權限管理頁骨架(併入 API Client nav 區塊)
status: done
parallel: false
depends_on: [task-004, task-005, task-006]
affected_files:
  - frontend/src/lib/api/clientSettingApi.ts
  - frontend/src/components/layout/Sidebar.tsx
  - frontend/src/app/(main)/client-settings/page.tsx
estimated_hours: 3
model: sonnet
effort: high
---

## 目標

建立前端資料層與頁面骨架:`clientSettingApi.ts`(RTK Query 全資源 endpoints + tag 失效)、sidebar 於既有「API Client 設定」nav 區塊底下新增「組織權限管理」頁連結(user 裁定:不另立 nav 區塊),頁面骨架以分頁籤承載系統別 / 作業、設定檔、Role、特例四區。

## 實作要點

- endpoints 對齊 004–006 定案路徑與 schema;list 類 providesTags、寫入 invalidatesTags(含 effective 預覽 tag)。
- 頁面骨架:tab 切換 + 各區空狀態(含「無 confirmed 語意映射」提示語意);樣式沿用既有 df-* 設計系統與 api-clients 頁慣例(先讀該頁再動手)。
- 本 task 只出骨架與資料層,矩陣等複雜 UI 留給 task-009(避免同檔並行,009 依賴本 task)。

## Acceptance

- [ ] `npm run lint` + `npm run typecheck` 乾淨
- [ ] `docker compose up -d --build` 後 sidebar「API Client 設定」區塊出現新頁連結,四分頁籤可切換、各 tab 顯示清單(空資料有空狀態)
- [ ] RTK cache:任一寫入後對應清單自動 refetch(瀏覽器 network 佐證)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
