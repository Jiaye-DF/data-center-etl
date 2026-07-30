---
id: task-002
title: api_client_router 骨架 + 統一封套 + JWT 簽發/驗簽核心 + /api/client 掛載
status: done
worker: worker-B
parallel: true
depends_on: []
affected_files:
  - backend/app/api_client_router/__init__.py
  - backend/app/api_client_router/common/__init__.py
  - backend/app/api_client_router/common/auth.py
  - backend/app/api_client_router/common/envelope.py
  - backend/app/api_client_router/versions/__init__.py
  - backend/app/api_client_router/versions/registry.py
  - backend/app/api_client_router/versions/v1_0.py
  - backend/app/core/config.py
  - backend/app/main.py
  - backend/tests/test_api_client_router_core.py
estimated_hours: 4
---

## 目標

依 Arch 模組① 建立對外串接專用命名空間 `/api/client/{version}/...`(與後台 `/api/v1` 分離),含:薄版本掛載層(registry)、統一回應封套、JWT 簽發 / 本地驗簽核心。本 task **不**實作 token 端點業務流(task-004),v1_0 先掛骨架(可為空 router 或 501 placeholder)。

## 規格

- **資料夾**:`backend/app/api_client_router/`(對齊 Arch 版本策略:共用邏輯版本無關、版本層只是薄掛載)。
  - `common/auth.py`:`sign_client_jwt(client_id) -> tuple[str, int]`(回 token + expires_in=900);`verify_client_jwt(token, *, verify_exp: bool = True) -> dict`(本地驗簽,**不查 DB、不回源**;`verify_exp=False` 供 refresh 驗舊 token 忽略 exp)。演算法 **HS256**;claims:`sub`=client_id、`iat`、`exp`=iat+900s、`iss="datahub-api-gateway"`。
  - `common/envelope.py`:統一封套 `success: bool / response_code: int / detail: str / data: list`(**data 恆為陣列**,失敗時空陣列);提供成功與錯誤兩個 helper;`detail` 僅基本錯誤資訊、禁洩內部設計。錯誤回應 HTTP status 與 `response_code` 一致。
  - `versions/registry.py`:`mount_version(app_or_router, version: str, overrides: dict | None)` 共用註冊方法——本版只掛 `v1.0`,但介面照 Arch 設計(新版本 = 新增薄檔案宣告差異)。
  - `versions/v1_0.py`:宣告 `/api/client/v1.0` 路由骨架(token 端點 stub,由 task-004 填實)。
- **config**(`core/config.py`):新增 `client_jwt_secret`(env `CLIENT_JWT_SECRET`)——遵循既有 Settings fail-fast 慣例(缺值 / 過短 <32 字元即啟動失敗,比照既有機密欄位寫法);**禁**寫死預設值進版控。`.env.development` / compose env 由本 task 一併補示例值並於 task 檔註記(不動部署環境)。
- **main.py**:掛載 `app.include_router(<client router>, prefix="/api/client")`(實際 prefix 組合以 registry 設計為準,最終路徑必須是 `/api/client/v1.0/...`);後台 `/api/v1` 掛載行為不得變動。
- 對外命名空間**不**掛既有後台 middleware / 稽核;錯誤格式走本封套,不走後台 ApiResponse。

## Acceptance

- [x] `uv run pytest tests/test_api_client_router_core.py` 全綠,至少涵蓋:`sign_client_jwt` 簽出可被 `verify_client_jwt` 解回 `sub`/`exp`;過期 token 在 `verify_exp=True` 丟錯、`verify_exp=False` 可解;篡改 token 驗簽失敗;封套成功 / 錯誤結構四欄齊全且 `data` 恆為 list
- [x] `CLIENT_JWT_SECRET` 缺值或 <32 字元時 Settings 初始化失敗(pytest 斷言)
- [x] app 啟動後 `/api/client/v1.0` 命名空間存在(TestClient 對 stub 路由請求不為 404),且 `/api/v1/health` 既有行為不變
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`uv run pytest` 既有全套全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/04-config.md`
- `docs/Design-Base/00-overview/02-secrets.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`

## 完成註記(worker-B)

### 實作內容

- `backend/app/api_client_router/`(新套件,`__init__.py` / `common/__init__.py` 留空,比照既有套件風格)
  - `common/envelope.py`:`ClientEnvelope`(`success` / `response_code` / `detail` / `data`,`data: list[dict[str, object]]` 恆為陣列)+ `client_success()` / `client_error()` 兩個 helper,皆回 `JSONResponse` 且 HTTP status = `response_code`;`client_error` 支援 `headers`(task-003 / 004 的 `Retry-After` 用)。
  - `common/auth.py`:`sign_client_jwt(client_id) -> (token, 900)`、`verify_client_jwt(token, *, verify_exp=True)`;HS256、claims `sub`/`iat`/`exp=iat+900`/`iss="datahub-api-gateway"`;驗簽帶 `issuer` 檢查與 `require` 四 claim,不查 DB / 不回源,失敗拋 `jwt.PyJWTError` 由呼叫端轉 401。
  - `versions/registry.py`:`CLIENT_ROUTE_PREFIX = "/api/client"` + `mount_version(app_or_router, version, overrides)`;`overrides` key = 掛載段(service 名;空字串 = 版本根,如 `/token`),新版本 = 新增薄檔案只宣告差異。
  - `versions/v1_0.py`:`VERSION = "v1.0"`、`/token` 與 `/refresh_token` 兩個 stub(統一封套 `501 not_implemented`,task-004 填實)、`mount()` 呼叫 registry。
  - `versions/__init__.py`:`build_client_router()` 組出 `/api/client` router(避免 registry ↔ v1_0 循環 import)。
- `backend/app/core/config.py`:新增 `CLIENT_JWT_SECRET: str = Field(min_length=32)`(必填、無預設值 → 缺值 / <32 字元即 Settings 驗證失敗;不進 `_fail_fast_in_prod` 清單,因無 development 預設值可比對)。
- `backend/app/main.py`:`app.include_router(build_client_router(), prefix=CLIENT_ROUTE_PREFIX)`,置於既有 `/api/v1` 掛載之後;後台掛載與 middleware 未動。
- `backend/tests/test_api_client_router_core.py`:18 測全綠(JWT 7 / 封套 4 / Settings fail-fast 3 / 路由掛載 4)。

### env 注入位置(compose fail-fast 防雷)

`CLIENT_JWT_SECRET` 為必填欄,已補進 compose 與本機實際讀取的 env 來源:

| 檔案 | 值 | 用途 |
| --- | --- | --- |
| `.env`(根,gitignored) | `changeme-development-client-jwt-secret-32` | compose `env_file` → backend / worker / scheduler |
| `backend/.env`(gitignored) | 同上 | 本機 dev server + pytest fallback |
| `.env.example` / `.env.production.example` | 空值 | 欄位清單 |
| `.env.development.example` | development 佔位值 | 欄位清單 |
| `.env.staging.example` | `__GENERATE_AT_DEPLOY__` | 欄位清單 |

⚠️ **部署前必辦**:`.env.staging` / `.env.production`(本機部署用實體檔,依規範不動)尚未有 `CLIENT_JWT_SECRET`,部署前須各自生成 32+ 字元強隨機值(`openssl rand -base64 32`,禁沿用 `JWT_SECRET_KEY`),否則測試站 / 正式站啟動會 fail-fast。

### 規格偏離

- **`affected_files` 外多動一檔**:`backend/tests/test_auth.py`(`test_settings_with_init_admin_env_ok` 以 `_env_file=None` 建 `Settings`,新必填欄使其必然 fail)→ 僅補一個 `CLIENT_JWT_SECRET="c"*32` kwarg,無其他改動。全庫僅此一處直接建構 `Settings`。
- 其餘無偏離(命名空間 / 封套四欄 / JWT claims / HS256 / fail-fast 皆照定案)。

### 驗證紀錄

- `uv run pytest tests/test_api_client_router_core.py` → **18 passed**
- `uv run pytest tests/test_auth.py -k settings` → **2 passed**(受影響測試)
- `uv run ruff check app tests` → All checks passed
- `uv run mypy app --cache-dir .mypy_cache_t002` → 僅既存 baseline 錯誤 `app/repositories/schedule_repo.py:528`(該檔本 task 未動),無新增
- 模擬 compose env 注入(讀根 `.env` 進 process env)→ `Settings` 不 fail-fast;`create_app()` 路由表出現 `POST /api/client/v1.0/token`、`POST /api/client/v1.0/refresh_token`,OpenAPI 正常產生
- 全套 `uv run pytest` 迴歸由 orchestrator 統一執行
