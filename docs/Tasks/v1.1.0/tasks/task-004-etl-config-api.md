---
id: task-004
title: ETL 設定管理 API(表清單 / 啟停 / mapping / Comment)
status: done
parallel: false
depends_on: [task-001, task-003]
affected_files:
  - backend/app/api/v1/etl_tables.py
  - backend/app/api/v1/__init__.py
  - backend/app/schemas/etl_config.py
  - backend/app/services/etl_config_service.py
  - backend/app/repositories/etl_config_repo.py
  - backend/tests/test_etl_config_api.py
estimated_hours: 3
---

## 目標

提供「以資料表為中心」的 ETL 設定管理 API:納管表清單(來源 / 目標 / 啟用狀態 / 最近執行狀態)、逐表啟用停用、mapping 與欄位 Comment 的檢視與編輯。設定的 source of truth 在自有 DB(worker 執行時讀取,見 task-006)。

## 範圍要點

- endpoints:表清單(分頁)、單表明細(含 mapping)、啟用/停用、mapping 更新(欄位對照 + comment);全部掛 `require_login`,寫入類掛 `require_admin`。
- mapping 更新需驗證:每個目標欄位**必有** comment(缺值 400,不可靜默通過)—— 對齊 propose「每欄位必帶 Comment」承諾。
- Repository 遵循軟刪除命名(`02-soft-delete.md`);對外一律 uid(`01-identifiers.md`)。
- **互鎖註記**:`api/v1/__init__.py` 序列化在 task-003 之後(`parallel: false`)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_etl_config_api.py -q` 全綠,涵蓋:CRUD、停用後清單狀態正確、mapping 缺 comment 回 400、viewer 寫入 403
- [x] response 殼為 ApiResponse(測試斷言)
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md` + `01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`(權限 Depends)
- `docs/Design-Base/04-databases/00-overview.md` + `02-soft-delete.md` + `01-identifiers.md`
- `docs/Design-Base/03-backend/07-testing.md`
