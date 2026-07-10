---
id: task-002
title: 授權鏈路改由角色表驅動(守衛 / auth me / SSO,對外值零變化)
status: pending
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/api/deps.py
  - backend/app/api/v1/auth.py
  - backend/app/api/v1/sso.py
  - backend/app/services/auth_service.py
  - backend/app/services/sso_service.py
  - backend/app/repositories/user_repo.py
  - backend/tests/test_auth.py
  - backend/tests/test_sso.py
estimated_hours: 3.5
---

## 目標

`require_role` / `require_admin`、`/auth/me` 與 SSO me 回應的 `role` 值改自關聯 `roles` 表取得;使用者建立路徑(init admin / SSO 首次登入)寫入角色關聯。對外欄位名、值格式、授權行為**完全不變**(admin 可寫、viewer 寫入類 API 403、SSO 首次登入 viewer)。

## 規格

- **角色取值收斂單一入口**(例:`User` 上的 property / 單一 helper),`deps.require_role`、`/auth/me`、SSO me、`create_access_token(role=...)` 一律經此取值;取值來源 = 關聯 `roles.code`,deprecated 字串欄位不再作為授權判斷來源
- `get_current_user` 載入 user 時**同時載入角色關聯**(eager load;async 下禁 lazy load 觸發 IO、禁 N+1 — 見 `03-backend/08-performance.md`)
- `UserRepository.create` 改為寫入角色關聯(收 `role_code` 或 Role 實體;內部查 `roles` 表對應):
  - `ensure_init_admin` → `admin`
  - `sso_service._get_or_create_user` 首次登入 → `viewer`
  - **dual-write**:建立時 deprecated `users.role` 字串同步寫同值(保持舊欄位與 `ck_users_role` 一致,直到人工移除)
- 找不到對應角色 code → fail-fast 拋 AppError(migration 未跑的環境要炸得明確,不能默默 fallback)
- 行為固定進測試:角色不嵌 JWT 授權判斷(守衛每請求自 DB 讀 user + 關聯角色)→ 指派後下一請求即生效(本 task 先固定「取值來自 DB 關聯」,指派 API 在 task-003)

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_auth.py tests/test_sso.py` 全綠,含**新增**測試:
  - viewer 呼叫任一寫入類 API(例 `POST /api/v1/sync/...`)回 403;admin 回 2xx
  - SSO 首次登入建立之使用者,關聯角色 code = `viewer`
  - `/auth/me` 回應 `role` 欄位名與值(`admin` / `viewer`)與 v1.4.0 完全一致
  - 直接改 DB 中某 user 的角色關聯後,同一 token 下一請求即以新角色判定(即時生效)
- [ ] `uv run pytest` 全綠(全套不迴歸)
- [ ] `docker compose up -d --build` 後 `curl -s -b <admin cookie> http://localhost:8000/api/v1/auth/me | jq -e '.data.role == "admin"'` 通過(viewer 同法驗 `"viewer"`)
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/08-performance.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/90-third-party-service/08-df-sso.md`
