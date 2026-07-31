---
id: task-005
title: 設定檔 / Role 管理 API(勾作業 + 授權矩陣 + 必綁防呆)
status: pending
parallel: false
depends_on: [task-004]
affected_files:
  - backend/app/api/v1/client_settings.py
  - backend/app/services/client_setting_service.py
  - backend/app/schemas/client_setting.py
  - backend/tests/test_client_settings_profiles_api.py
estimated_hours: 3.5
model: opus
effort: high
---

## 目標

角色權限設定檔與 Role 的管理端點:設定檔 CRUD + 可讀作業整批勾選 + 每作業授權矩陣整批置換(Profile → Operation → Table → Column → Read/Edit);Role CRUD 必綁 1 設定檔(禁空)。

## 實作要點

- 設定檔:GET / POST(name 唯一)/ PATCH / DELETE(被 Role 綁 409);`PUT .../profiles/{uid}/operations` 整批置換勾選(移除作業同交易清該作業授權項);`GET/PUT .../profiles/{uid}/operations/{op_uid}/items` 授權矩陣整批置換。
- 矩陣驗證:作業未先勾選 → 409;授權欄位超出作業範圍(∩ 上限)→ 422 逐筆列明;action ∈ read|edit;`*` 全欄位;同一表在不同作業可各自設定。
- Role:GET / POST(未帶 permission_profile_uid → 422)/ PATCH(可改綁,仍必有值)/ DELETE(被 Client 綁 409)。
- 加法模型:僅授予語意,無 deny 欄位;寫端點記稽核 + 失效相關快取(綁該設定檔的 Role → 其 Client 的 effective key)。

## Acceptance

- [ ] `uv run pytest tests/test_client_settings_profiles_api.py` 全綠(CRUD;勾作業置換與連動清除;矩陣置換 + 未勾作業 409 + 超範圍 422;Role 缺設定檔 422 / 刪除防呆 409;audit 事件)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] 既有測試迴歸全綠(`uv run pytest`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
