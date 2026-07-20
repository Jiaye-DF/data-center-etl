---
id: task-004
title: 資料查詢 JSON API + confirmed 英文 key 轉換(A3)
status: pending
parallel: false
depends_on: [task-003]
affected_files:
  - backend/app/api/v1/datasets.py
  - backend/app/services/data_query_service.py
  - backend/app/schemas/data_query.py
  - backend/tests/test_data_query_api.py
estimated_hours: 4
---

## 目標

提供資料列查詢 JSON API,回傳 key 依 confirmed mapping 轉為英文(`gen01`→`employee_number`);未 confirmed 欄位**不出現在回傳**(不外流草稿名/魔術名)。

> 拆解判讀:現行 datasets API 僅 schema/表層瀏覽,無資料列端點;對外承諾「指定表的 JSON API 回傳英文 key」需以本 task 新增端點承載(併入既有 datasets 路由,不另開 page/模組 — 對齊「別過度拆成新頁」原則)。

## 內容

- `api/v1/datasets.py` 新增 `GET /api/v1/datasets/{dataset}/tables/{schema_name}/{table_name}/rows`:
  - query 參數 `limit`(預設 50,上限 500)、`offset`;需登入(沿用既有 auth Depends)。
  - 該表**無任何 confirmed 欄位** → 404(`ApiResponse` 錯誤殼,訊息註明「尚未複核」);有 confirmed → 只 SELECT confirmed 欄位,回傳 key 用 `english_name`。
- `services/data_query_service.py`:讀 task-003 副本 repo 的 `get_confirmed_map`;對 RDS 目標庫組查詢 — **識別字經白名單驗證後引號化,值一律 bind params**(`04-sql-safety.md`);表/欄名必須存在於副本 mapping,否則 404(防注入面)。
- `schemas/data_query.py`:回應模型(`rows: list[dict[str, Any]]` + `total_returned` + `columns` 元資訊:english_name/zh_name)。
- 回應走 `ApiResponse` 外殼(`03-backend/01-routing.md`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_data_query_api.py` 全綠(含:confirmed 表回英文 key、未 confirmed 欄不出現、全 draft 表 404、limit 上限、未登入 401)
- [ ] `uv run pytest` 既有全套件不紅
- [ ] ruff + mypy 全綠
- [ ] docker compose 手測:`curl -s -b <cookie> http://localhost:<port>/api/v1/datasets/source/tables/M2201/GEN_FILE/rows | jq -e '.data.rows[0] | has("gen01") | not'`(樣本表 confirmed 後執行;與 task-009 銜接)

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
