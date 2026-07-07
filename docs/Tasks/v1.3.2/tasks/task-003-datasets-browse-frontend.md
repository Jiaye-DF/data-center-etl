---
id: task-003
title: 資料瀏覽前端 — 快照分欄 + 筆數區間篩選 + 統計摘要區塊
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - frontend/src/components/datasets/DatasetBrowser.tsx
  - frontend/src/lib/api/datasetApi.ts
estimated_hours: 3
---

## 目標

`DatasetBrowser` 依 `dataset` 分欄:target 顯示單一「快照時間」,source 維持「RDS 同步時間 / ETL 轉換時間」;進階篩選加「筆數區間」(rowMin/rowMax,標註 0–1000 上限);當前 schema 上方加「統計摘要」區塊(總表數/有資料/空表/1000+)。回溯記錄:已於 commit `967400e` 落地。

## Acceptance

- [x] `cd frontend && npm run typecheck` 綠(exit 0)
- [x] `cd frontend && npm run lint` 綠(eslint --max-warnings=0)
- [x] `grep -q "SchemaSummaryBar" frontend/src/components/datasets/DatasetBrowser.tsx`(統計摘要區塊存在)
- [x] `grep -Eq "rowMin|rowMax" frontend/src/lib/api/datasetApi.ts`(筆數區間參數串接)
- [x] `grep -q "snapshot_at" frontend/src/lib/api/datasetApi.ts`(快照時間型別)

## 必讀檔(Just-in-time)

- `02-frontend/00-overview.md`
- `02-frontend/02-api-and-state.md`
- `02-frontend/04-datetime.md`
- `02-frontend/05-components.md`
- `02-frontend/06-rwd.md`
