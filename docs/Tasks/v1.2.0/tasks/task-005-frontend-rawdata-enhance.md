---
id: task-005
title: 前端 原始資料管理補強(移除查看欄位/schema 說明/過濾/時間欄/同步鈕)
status: done
parallel: true
depends_on: [task-002, task-004]
affected_files:
  - frontend/src/components/datasets/DatasetBrowser.tsx
  - frontend/src/app/(main)/raw-data/page.tsx
  - frontend/src/app/(main)/etl-data/page.tsx
  - frontend/src/lib/api/datasetApi.ts
  - frontend/src/lib/api/syncApi.ts
  - frontend/src/constants/schemaDescriptions.ts
estimated_hours: 3
---

## 目標

補強 `DatasetBrowser`:①移除逐表「查看欄位」功能 ②schema 選項附**說明文字**(非裸 tag)③預設**過濾 0 筆表**(可切換顯示)④清單加 **業務資料名稱(中文)/ RDS 同步時間 / ETL 轉換時間** 欄 ⑤加**同步按鈕**(逐表 + 全量),呼叫 sync API。資料一律讀後端快照(業務資料名稱亦來自快照落地值,非即時 JOIN)。

## 設計要點

- `constants/schemaDescriptions.ts`:schema → 說明文字對照(DS = ERP 資料字典、M2201 = 業務資料…;未知 schema 給預設說明)。
- `datasetApi.ts`:`TableSummary` 加 `business_name` / `last_synced_at` / `last_transformed_at`;`listDatasetTables` 加 `hideEmpty` 參數(預設 true);**移除** `useListDatasetColumnsQuery`;加「重整快照」mutation。
- `syncApi.ts`:`syncTable({schema,table})`、`syncAll()` mutations(POST `/sync/table`、`/sync/all`)。
- `DatasetBrowser.tsx`:
  - schema 分頁籤下方或 tab 附說明文字(tooltip 或副標)。
  - 表格移除「欄位結構」欄與展開列;新增「業務資料名稱」(中文,空值顯示 —)、「RDS 同步時間」「ETL 轉換時間」欄(用 `utils/datetime.ts` 顯示,空值顯示 —)與逐表「同步」鈕(df-btn-primary-soft)。
  - 頁首加「全量同步」鈕(admin)+「重整快照」鈕 +「顯示 0 筆表」切換(預設隱藏)。
  - 時間顯示走 `02-frontend/04-datetime.md`;RWD / 觸控目標對齊 `06-rwd.md`。
- viewer 角色隱藏同步 / 重整鈕(對齊既有 useAuth isAdmin)。

## Acceptance

- [x] `cd frontend && npm run typecheck && npm run lint` green(strict,禁 any)
- [x] `npm run build` 成功;`/raw-data`、`/etl-data` 路由產出
- [x] 頁面實測(docker compose 起):原始資料管理無「查看欄位」按鈕;schema 有說明文字;預設不顯示 0 筆表,切換後可見;清單有業務資料名稱(中文)+ 兩個時間欄與同步鈕
- [x] 點單表「同步」→ 呼叫 `/api/v1/sync/table`(Network 可證);viewer 登入時同步鈕不顯示
- [x] 時間欄以 `utils/datetime.ts` 格式化(非直接 toString)

## 必讀檔(Just-in-time)

- `docs/Design-Base/02-frontend/00-overview.md`
- `docs/Design-Base/02-frontend/02-api-and-state.md`
- `docs/Design-Base/02-frontend/04-datetime.md`
- `docs/Design-Base/02-frontend/05-components.md`
- `docs/Design-Base/02-frontend/06-rwd.md`
