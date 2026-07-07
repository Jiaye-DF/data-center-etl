---
id: task-008
title: 移除前端「排程涵蓋」頁 + v1.1 config-ETL 頁 + Sidebar 連結
status: pending
parallel: true
depends_on: [task-007]
affected_files:
  - frontend/src/app/(main)/schedules/coverage/page.tsx
  - frontend/src/components/schedules/ScheduleCoverageBrowser.tsx
  - frontend/src/lib/api/scheduleCoverageApi.ts
  - frontend/src/app/(main)/tables/page.tsx
  - frontend/src/app/(main)/tables/[uid]/page.tsx
  - frontend/src/components/tables/MappingEditor.tsx
  - frontend/src/components/tables/TableList.tsx
  - frontend/src/lib/api/etlConfigApi.ts
  - frontend/src/components/layout/Sidebar.tsx
estimated_hours: 2
---

## 目標

程式面移除前端「排程涵蓋」頁(功能已併入 task-007 排程管理頁)與 v1.1 config-ETL 的 `/tables` 頁鏈路,並自 Sidebar 移除「排程涵蓋」導覽項。依賴 task-007 先移除 `etlConfigApi` 的引用,避免刪檔後殘留 import。

## 內容

- 刪除:`app/(main)/schedules/coverage/page.tsx`、`components/schedules/ScheduleCoverageBrowser.tsx`、`lib/api/scheduleCoverageApi.ts`、`app/(main)/tables/page.tsx`、`app/(main)/tables/[uid]/page.tsx`、`components/tables/MappingEditor.tsx`、`components/tables/TableList.tsx`、`lib/api/etlConfigApi.ts`。
- `components/layout/Sidebar.tsx`:移除 `{ href: '/schedules/coverage', label: '排程涵蓋' }` 一項與其 `CoverageIcon`(若無他用)。確認 `/tables` 未在 Sidebar(v1.3.0 已不在);若有殘留一併移除。
- 刪檔後確認無其他檔 import 這些模組(coverage 頁/tables 頁/etlConfigApi)。

## Acceptance

- [ ] 上述 8 個檔已刪除(`git status` 顯示 deleted)
- [ ] `cd frontend && npm run typecheck` 零錯誤（無殘留 import 已刪模組）
- [ ] `cd frontend && npm run lint` 零警告；`npm run build` 成功
- [ ] `grep -rn "scheduleCoverageApi\|ScheduleCoverageBrowser\|etlConfigApi\|/schedules/coverage\|/tables" frontend/src` 無命中（Sidebar 與全前端零引用）

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/01-routing-and-error.md`
