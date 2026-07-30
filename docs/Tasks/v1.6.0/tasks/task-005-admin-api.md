---
id: task-005
title: 後台管理 API /api/v1/api-clients(建立/發證/輪替/啟停/限流參數)
status: done
worker: worker-D
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

- [x] `uv run pytest tests/test_api_clients_api.py` 全綠,至少涵蓋:非 admin 403;建立回應含明文 secret 且再 GET 不再出現;列表不含 secret_hash 與 pid;PATCH 限流參數與 status 生效;rotate 第 3 把 active → 409;retire 後 active 數減一;軟刪 client 不出現在列表
- [x] `curl` 建立 → 回應 `data.client_secret` 存在;隨後 `GET /api/v1/api-clients` 回應 body 不含該明文(整合環境驗證,寫入 verification 由 task-007 收口)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`uv run pytest` 既有全套全綠(users / roles 迴歸不變 — 全套由 orchestrator 於波次結束統一跑)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`

## 完成註記(worker-D)

### 驗證命令與結果

| 驗證 | 命令 | 結果 |
| --- | --- | --- |
| 目標測試 | `uv run pytest tests/test_api_clients_api.py -q` | 14 passed |
| 鄰近迴歸 | `uv run pytest tests/test_api_clients_api.py tests/test_api_client_models_repo.py tests/test_users_api.py tests/test_api_client_router_core.py -q` | 51 passed(users API 迴歸不變) |
| lint | `uv run ruff check app tests` | All checks passed |
| 型別 | `uv run mypy app --cache-dir .mypy_cache_t005` | 僅既有 `schedule_repo.py:528` 1 error(未動該檔,非本 task 新增) |
| 整合(真 HTTP) | 本機 uvicorn:8011 對測試 DB + curl | 見下 |

curl 整合驗證(建立 → 列表 → PATCH → rotate → 409 → retire,全數符合規格):

- `POST /api/v1/api-clients` → HTTP 201,`data.client_secret` 存在,`data.client.client_id` 為 `dc_` + 24 hex,預設 30 / 200、`active_secret_count=1`
- `GET /api/v1/api-clients` → HTTP 200,body 不含該明文、不含 `secret_hash` / `pid`
- `PATCH /{uid}` → status `disabled` + 限流 7 / 70 生效,`client_id` 未變
- `POST /{uid}/rotate-secret` → 200(`active_secret_count=2`);再一次 → 409「先停用舊密鑰」
- `POST /{uid}/secrets/{secret_uid}/retire` → 200,`active_secret_count` 減為 1

> 未 rebuild docker backend(image 為 baked code,rebuild 會捲入其他 worker 進行中的程式碼);
> 改以本機 uvicorn 對**測試 DB** 起服務走真 HTTP 驗證,驗畢清除測試 DB 該批列與臨時檔。

測試涵蓋:未登入 401;member 對 5 個端點全 403;建立回明文 secret(bcrypt 可驗回、
入庫非明文)且列表不再出現;稽核 detail 不含明文;name 空字串 422;列表欄位集合精確
比對(無 `secret_hash` / `pid` / `is_deleted`);軟刪 client 不入列表且該 uid 操作 404;
PATCH status + 雙限流生效並落庫;限流 0 / 未知 status 422、未知欄位 `client_id` 被忽略;
未知 uid 404;rotate 第 2 把 OK、第 3 把 409;retire 後 active 減一且 retired 列保留、
可再發一把;最後一把 active 亦允許汰換(count 歸 0);跨 client 的 secret_uid retire → 404。

### 審計掛法(依據)

users CRUD(`user_service.assign_role`)以 `AuditService(db).log(...)` 掛同 session,故比照掛,
不新造機制:`api_client_create` / `api_client_update` / `api_client_secret_rotate` /
`api_client_secret_retire`,`target_type="api_client"`、`target_uid` 為 client `uid`。
action 命名採既有多數的底線式(對齊 `role_assigned` / `schedule_update`)。
detail 一律不含明文 secret(測試斷言)。

### 偏離規格處

1. **`_get_or_404` / `_get_secret_or_404` / active 密鑰計數落在 service**:`api_client_repo` 只有
   `get_by_client_id`,無「依 uid 取件」;該檔不在本 task `affected_files` 白名單,依既有前例
   (`audit_service.py`、`sso_service.py`、`data_query_service.py` 皆於 service 直下 ORM `select`)
   將這三處查詢暫落 service,並於檔頭註記原因。後續若開 repo 檔案權限建議上收。
2. **`POST` 建立回 201**:規格未指定狀態碼,`03-backend/01-routing.md` 明訂「201 = POST 建立資源」,
   依〈規範優先順序〉Design-Base > Tasks 採 201(FastAPI `status_code=201` 與 `response_code` 一致)。
   `rotate-secret` / `retire` 為動作型 POST → 200。
3. **`data` 不直接為建立後的 client 物件**:`01-routing.md` 禁 `data` 為 array 但要求 dict;
   為同時回明文 secret,建立回應為 `{client: {...}, client_secret: "..."}`(Acceptance 要的
   `data.client_secret` 位置不變)。
4. **PATCH `description` 無法清空**:`api_client_repo.update` 以 `None = 不變更` 語意(task-001 已如此
   定義且不得改該檔),故本層沿用;若日後需清空需改 repo 語意。
5. **`status` 以 `Literal["enabled","disabled"]` 落在 schema**(→ 非法值 422)而非 service 擋 400:
   既有 schema 層皆不 import model 常數,維持該分層慣例。

### 其他注意

- `backend/.mypy_cache_t005/` 未被 `.gitignore` 涵蓋(只有 `.mypy_cache/`),commit 前勿納入版控。
- 路由 `POST /{uid}/secrets/{secret_uid}/retire` 為三層路徑,`01-routing.md` 建議「多層最多兩層」;
  路徑由規格定案(不得自行變更),此處照規格實作,列為 reflect 可討論項。
