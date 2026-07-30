---
id: task-005
title: 後台管理 API /api/v1/api-clients(建立/發證/輪替/啟停/限流參數)
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/api/v1/api_clients.py
  - backend/app/api/v1/__init__.py
  - backend/app/services/api_client_service.py
  - backend/app/schemas/api_client.py
  - backend/tests/test_api_clients_api.py
estimated_hours: 4
---

## 目標

後台管理員(既有 DF-SSO / 本地登入體系,admin 角色)管理 API Client 的 CRUD API:建立(核發 client_id + 一次性明文 secret)、輪替 secret、啟用/停用、限流參數編輯。**與既有 users / roles 完全分離**——本 task 不動 `users.py` / `roles.py` / 既有權限模型。

## 規格

- 路由(全部 admin-only,權限 Depends 比照 `api/v1/users.py` 既有寫法;回應走既有後台 ApiResponse 殼,**不是**對外統一封套):
  - `GET /api/v1/api-clients`:列表(排除軟刪;含 `uid / client_id / name / description / status / rate_limit_per_minute / rate_limit_per_10min / created_at`、active secret 數;**永不回傳 secret_hash**)。
  - `POST /api/v1/api-clients`:建立——`name` 必填、`description` 選填;伺服器產 `client_id`(格式 `dc_` + 24 字元 hex 隨機)與 secret(`secrets.token_urlsafe(32)`);回應**僅此一次**含明文 `client_secret`;secret 入庫只存 bcrypt 雜湊。
  - `PATCH /api/v1/api-clients/{uid}`:改 `name / description / status / rate_limit_per_minute / rate_limit_per_10min`(限流值驗證 ≥ 1;`client_id` 不可改)。
  - `POST /api/v1/api-clients/{uid}/rotate-secret`:發新 active secret(回應僅此一次含明文);若已有 2 把 active → `409`(先汰舊才能再發)。
  - `POST /api/v1/api-clients/{uid}/secrets/{secret_uid}/retire`:汰換指定 secret(改 `status='retired'`,軟性、不刪列);最後一把 active 亦允許汰換(該 client 將無法取證,屬管理員自主行為)。
  - 對外一律用 `uid`,**禁曝 pid**。
- 停用(`status='disabled'`)後 token 端點即拒發(由 task-004 的查驗保證,本 task 僅負責狀態寫入)。
- 審計:操作走既有 audit log 機制(比照 users CRUD 有掛就掛,沒有共用機制則不新造)。

## Acceptance

- [ ] `uv run pytest tests/test_api_clients_api.py` 全綠,至少涵蓋:非 admin 403;建立回應含明文 secret 且再 GET 不再出現;列表不含 secret_hash 與 pid;PATCH 限流參數與 status 生效;rotate 第 3 把 active → 409;retire 後 active 數減一;軟刪 client 不出現在列表
- [ ] `curl` 建立 → 回應 `data.client_secret` 存在;隨後 `GET /api/v1/api-clients` 回應 body 不含該明文(整合環境驗證,寫入 verification 由 task-007 收口)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`uv run pytest` 既有全套全綠(users / roles 迴歸不變)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
