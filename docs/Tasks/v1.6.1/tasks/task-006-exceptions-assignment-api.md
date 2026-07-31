---
id: task-006
title: 特例權限 + API Client 指派 API(可重用組 + 效期綁定)
status: pending
parallel: false
depends_on: [task-005]
affected_files:
  - backend/app/api/v1/client_settings.py
  - backend/app/services/client_setting_service.py
  - backend/app/schemas/client_setting.py
  - backend/tests/test_client_settings_exceptions_api.py
estimated_hours: 3
model: opus
effort: medium
---

## 目標

特例權限組管理(可重用,結構同設定檔)與 API Client 的 Role 指派 / 特例綁定端點;特例 `expires_at` 到期自動失效(讀取過濾,無需人工)。

## 實作要點

- 特例組:GET / POST / PATCH / DELETE(仍被未過期綁定引用 409);`PUT .../exception-sets/{uid}/operations` 與 `.../operations/{op_uid}/items` 同 task-005 矩陣語意(∩ 作業範圍同樣成立)。
- Client 指派(掛 client-settings 前綴下以 client uid 定位,或依 041 既有資源慣例由 worker 定;client 本體在自有 DB,以 `api_client_uid` 冷關聯,指派前須驗 client 存在且未軟刪):
  - Role:PUT 指派 / 改指派(冪等置換,0..1)、DELETE 解除。
  - 特例:GET 綁定清單(含 expires_at / 是否過期)、POST 綁定(`{exception_set_uid, expires_at?}`,重複綁同組 409)、DELETE 解除單筆(以綁定列 uid 定位)。
- 寫端點記稽核 + 失效該 client 的 effective 快取。

## Acceptance

- [ ] `uv run pytest tests/test_client_settings_exceptions_api.py` 全綠(特例組 CRUD + 矩陣;綁定含效期 / 重複 409 / 解除;Role 指派冪等置換 0..1 / 解除;指派不存在的 client → 404;audit 事件)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [ ] 既有測試迴歸全綠(`uv run pytest`)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/06-timezone.md`
