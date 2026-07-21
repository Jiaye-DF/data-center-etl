---
id: task-004
title: 語意映射管理後端 API(列表 / 編輯 / 轉態)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/api/v1/semantic_mappings.py
  - backend/app/services/semantic_admin_service.py
  - backend/app/schemas/semantic_mapping.py
  - backend/app/api/v1/__init__.py
  - backend/tests/test_semantic_mappings_api.py
estimated_hours: 4
---

## 目標

提供語意映射管理的後端 API(admin-only),直接讀寫 RDS `erp_metadata.semantic_mappings`(唯一事實來源;propose A5 禁雙向同步 → 編輯**不**寫自有 DB 副本,副本仍靠同步重灌)。

## 內容

- 新 router `semantic_mappings.py`,掛 `/semantic-mappings`(`api/v1/__init__.py` 註冊),全端點 `require_admin`:
  - `GET /semantic-mappings`:分頁列表;query:`table`(表名精準/前綴)、`status`(all/draft/confirmed)、`keyword`(欄名/英文名/中文名子字串)、`page`/`page_size`。
  - `GET /semantic-mappings/tables`:distinct 表名清單(含各表 draft/confirmed 計數,供前端下拉)。
  - `PATCH /semantic-mappings`:body 帶 `table_name`+`column_name` 複合鍵 + 可改欄位(`english_name`/`zh_name`/`status`);`updated_at` 寫 naive UTC+8(對齊 RDS 時間型別通則)。
  - `POST /semantic-mappings/confirm-table`:整表轉 confirmed(對齊 seed 腳本 `--confirm-table` 語意)。
- RDS 連線沿用 `rds_database_url(RDS_TARGET_DB_ENV)` 獨立 engine(不走自有 DB session);SQL 一律 bind params;識別字走既有 `quote_ident` 白名單。
- english_name 寫入前正規化驗證(非空、`^[a-z][a-z0-9_]*$`),不合法回 422。
- 「同步 view」觸發端點**不在本 task**(task-005)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_semantic_mappings_api.py` 全綠(含:列表分頁/篩選、PATCH 更新與 422 驗證、confirm-table 轉態、member 403)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [x] response 殼為 ApiResponse(`03-backend/01-routing.md`)
- [x] `grep -n "semantic-mappings" backend/app/api/v1/__init__.py` 有註冊列

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/00-overview/05-timezone.md`
