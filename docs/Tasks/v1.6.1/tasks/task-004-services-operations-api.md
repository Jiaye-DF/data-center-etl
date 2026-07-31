---
id: task-004
title: 系統別 / 作業管理 API(CRUD + 範圍 items + semantic 驗證)
status: done
parallel: false
depends_on: [task-002, task-003]
affected_files:
  - backend/app/api/v1/client_settings.py
  - backend/app/api/v1/__init__.py
  - backend/app/services/client_setting_service.py
  - backend/app/schemas/client_setting.py
  - backend/tests/test_client_settings_services_api.py
estimated_hours: 3.5
model: opus
effort: medium
---

## 目標

後台 `/api/v1/client-settings` 前綴下的系統別與作業管理端點(admin 專用,統一封套),含作業「表 × 欄位範圍」整批置換與 semantic confirmed 驗證;寫端點皆記稽核並失效快取。

## 實作要點

- 端點:系統別 GET 清單 / POST 建立(code 唯一 409)/ PATCH(code 禁改)/ DELETE 軟刪(仍有作業 409);作業 GET(依 service 過濾)/ POST(name 系統別內唯一)/ PATCH(禁改歸屬)/ DELETE(被設定檔或特例引用 409);`GET/PUT .../operations/{uid}/items` 範圍整批置換。
- items 驗證:表 / 欄位須存在於 semantic_mappings confirmed(`*` 全欄位僅驗表);非法逐筆列明回 422。
- 寫入順序:先 RDS 成功 → 記 audit(自有 DB)→ 失效相關快取;list 讀取走 task-003 快取。
- 本 task 一次完成 `client_settings.py` router 於 `api/v1/__init__.py` 的註冊(005 / 006 不再動 `__init__.py`)。

## Acceptance

- [ ] `uv run pytest tests/test_client_settings_services_api.py` 全綠(非 admin 403;CRUD 正流程;code 唯一 409;刪除防呆 409;items 置換 + 非 confirmed 422;audit 有事件;寫後 list 讀到新值)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] 既有測試迴歸全綠(`uv run pytest`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
