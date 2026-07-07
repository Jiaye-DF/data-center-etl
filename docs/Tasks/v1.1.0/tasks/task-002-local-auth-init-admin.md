---
id: task-002
title: 本地帳密登入 + init_admin(env)+ 角色權限 Depends
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/api/v1/auth.py
  - backend/app/api/v1/__init__.py
  - backend/app/schemas/auth.py
  - backend/app/services/auth_service.py
  - backend/app/repositories/user_repo.py
  - backend/app/core/config.py
  - backend/app/core/security.py
  - backend/app/api/deps.py
  - backend/app/main.py
  - backend/tests/test_auth.py
estimated_hours: 4
---

## 目標

實作本地帳號密碼登入(JWT httpOnly cookie)、init_admin 初始管理員(帳密由**環境變數**注入、首次啟動自動建立、缺 env 即 fail-fast)、角色權限依賴(`require_admin` / `require_login`,admin 可寫、viewer 唯讀)。本 task 建立 `api/v1/__init__.py` 的 router 匯集模式,供 003–005 依序掛入。

## 範圍要點

- 登入/登出/me endpoint;密碼驗證 bcrypt + `asyncio.to_thread`(`04-databases/03-passwords-and-pii.md`)。
- `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` 進 Settings 必填欄;缺值啟動 fail-fast(對齊 `03-backend/04-config.md`),**禁**預設帳密;lifespan 內冪等建立(已存在不重建、不覆寫密碼)。
- 權限依賴集中 `app/api/deps.py`:viewer 呼叫寫入類 API 一律 403。
- response 一律 ApiResponse 殼(`03-backend/01-routing.md`);log 禁出現密碼(`02-secrets.md`)。
- **互鎖註記**:本 task 是 `api/v1/__init__.py` / `config.py` / `main.py` 的第一手;003/004/005 依賴鏈序列化後才可再動。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_auth.py -q` 全綠(登入成功/密碼錯 401/viewer 打 admin-only 假端點 403/me)
- [x] 測試涵蓋:缺 `INIT_ADMIN_*` env 時 Settings 驗證失敗(fail-fast);init_admin 冪等(重複啟動不重建)
- [x] `! grep -nE "INIT_ADMIN_PASSWORD\s*[:=]\s*['\"]" backend/app` 成立(無硬編預設密碼)
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`(永遠讀)
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/04-config.md` + `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
- `docs/Design-Base/03-backend/07-testing.md`
