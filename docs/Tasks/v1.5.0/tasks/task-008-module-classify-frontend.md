---
id: task-008
title: B2 前端 — 資料集頁模組分類/篩選 UI
status: pending
parallel: false
depends_on: [task-007]
affected_files:
  - frontend/src/lib/api/datasetApi.ts
  - frontend/src/components/datasets/DatasetBrowser.tsx
estimated_hours: 2
---

## 目標

資料集瀏覽(DatasetBrowser)可按 ERP 模組代碼分類/篩選資料表 — 併入既有頁面體系,**不**另開 page/route(對齊「別過度拆成新頁」原則)。

## 內容

- `datasetApi.ts`:`list_tables` 請求加 `module` 參數;回應型別加 `module_code`(TS strict,禁 any)。
- `DatasetBrowser.tsx`:表清單加模組篩選控制(下拉或 chip,選項由當前清單的 distinct `module_code` 聚合,含「全部」);表格列顯示模組代碼欄。無 `module_code`(null)歸入「未分類」。
- 篩選狀態與既有搜尋/篩選並存,不破壞現有互動;RWD 對齊 `02-frontend/06-rwd.md`。

## Acceptance

- [ ] `cd frontend && npm run lint` + `npm run typecheck`(或 `tsc --noEmit`)全綠
- [ ] `npm run build` 成功
- [ ] docker compose 手測:資料集頁選任一模組 → 表清單僅剩該模組;切回「全部」復原;null 模組表出現在「未分類」

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
