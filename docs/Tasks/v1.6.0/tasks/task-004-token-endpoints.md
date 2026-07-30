---
id: task-004
title: POST /api/client/v1.0/token + /refresh_token 端點業務流
status: done
worker: worker-E
parallel: false
depends_on: [task-001, task-002, task-003]
affected_files:
  - backend/app/api_client_router/versions/v1_0.py
  - backend/app/api_client_router/common/auth.py
  - backend/app/api_client_router/common/schemas.py
  - backend/tests/test_api_client_token_api.py
estimated_hours: 4
---

## 目標

組裝兩個對外端點的完整業務流(路由格式 user 明示**完整遵循**,禁改路徑):
`POST /api/client/v1.0/token`、`POST /api/client/v1.0/refresh_token`。

## 規格(Arch 模組① + user 裁定)

**共同流程(兩端點)**:
1. 讀 body(`common/schemas.py` Pydantic:`/token` 收 `client_id` + `client_secret`;`/refresh_token` 另收 `access_token`;secret 一律放 body,禁 query)。
2. **先限流**:以 client_id 查 DB 取 `rate_limit_per_minute / rate_limit_per_10min`(查無此 client → 用預設 30/200,防列舉爆破)→ 呼叫 task-003 `check_rate_limit`;超限或鎖定中 → `429` + `Retry-After` header + 統一封套。
3. `/refresh_token` 額外前置:`verify_client_jwt(access_token, verify_exp=False)` 驗舊 token **簽章有效(忽略 exp)** 且 `sub == client_id`;不過 → 記一次失敗 → `401 invalid_client`。
4. 驗證:`get_by_client_id`(排除軟刪)→ client 存在、`status='enabled'`、bcrypt 比對任一把 `active` secret(bcrypt 比對走 `asyncio.to_thread`,禁阻塞 event loop)。任一不過 → 記一次連續失敗 → `401`,`detail` 一律 `"invalid_client"`(**不區分**不存在 / 停用 / 密錯 / 舊 token 不過)。
5. 通過:清失敗計數 → `sign_client_jwt(client_id)` → `200` 統一封套,`data = [{"access_token": ..., "token_type": "Bearer", "expires_in": 900}]`。

**其他約束**:
- 不發 refresh token;`/refresh_token` 是語意刷新(與 `/token` 安全等價)。
- 兩端點皆掛在 registry 的 v1.0 版本層;成功與錯誤(401 / 429 / 422 / 500)一律統一封套,`detail` 禁洩內部設計(500 細節只進 log)。
- 端點 handler 內**除限流參數與 client 驗證外禁其他 DB 查詢**;JWT 簽發驗簽零外部依賴。

## Acceptance

- [x] `uv run pytest tests/test_api_client_token_api.py` 全綠,至少涵蓋:
  - 正常取證:200、封套四欄、`data[0]` 三鍵齊、JWT 解出 `sub`=client_id 且 `exp-iat`=900
  - 錯 secret / 不存在 client_id / `status='disabled'` / 軟刪 client → 四者回應體 byte-level 同構(僅比對 JSON 欄位值全等),皆 `401` + `invalid_client`
  - `/refresh_token`:過期 token + 正確 secret → 200 換新;篡改簽章 → 401;A 的 token + B 的 client_id/secret(sub 不符)→ 401;token 有效但 secret 錯 → 401
  - 雙 secret 並存:兩把皆可取證;retire 舊鑰後舊 secret → 401
  - 停用 client 後下一次 `/token` 即 401(不因先前成功而快取放行)
  - 限流:mock 或實測第 31 次 → 429 且 `Retry-After` header 存在;連續 5 次 401 後 → 429(鎖定)
- [x] `curl -s -X POST http://localhost:8000/api/client/v1.0/token -H "Content-Type: application/json" -d '{"client_id":"x","client_secret":"y"}' | jq -e '.success == false and .response_code == 401 and (.data | length) == 0'` 通過(docker compose 起服務後)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤;`uv run pytest` 既有全套全綠(全套迴歸由 orchestrator 統一跑)

## 完成註記(worker-E)

- `backend/app/api_client_router/common/schemas.py`(新增):`TokenRequest`(client_id / client_secret)、`RefreshTokenRequest`(繼承 + access_token);僅 `min_length=1`,不設上限以免「密錯 vs 格式錯」出現可辨識的 422 側通道。憑證只收 body。
- `backend/app/api_client_router/common/auth.py`:新增 `is_refreshable_token(token, client_id)` — `verify_client_jwt(verify_exp=False)` 驗簽章 + `sub` 相符,`PyJWTError` 一律回 False(不外洩失敗原因)。
- `backend/app/api_client_router/versions/v1_0.py`:兩端點填實。
  - 流程:單次 `get_by_client_id`(排除軟刪)→ `_throttle`(先 `check_auth_lock`,再 `check_rate_limit`;未知 client 用 30/200 預設)→ `/refresh_token` 額外 `is_refreshable_token` → `_authenticated`(status=enabled + bcrypt 比對任一 active 密鑰,走 `verify_password_async` 的 `asyncio.to_thread`)→ `clear_auth_failures` + `sign_client_jwt` → 200 `data=[{access_token, token_type:"Bearer", expires_in:900}]`。
  - handler 內僅該一次 DB 查詢(限流參數與驗證共用同一筆),JWT 簽發驗簽零外部依賴。
  - 401 一律 `client_error("invalid_client", 401)`:不存在 / 停用 / 軟刪 / 密錯 / 舊 token 不過的回應體完全同構;429 帶 `Retry-After`(鎖定時為鎖剩餘 TTL)。
  - `ClientEnvelopeRoute`(APIRoute 子類,`route_class`):把 `RequestValidationError` → 422、未捕獲例外 → 500 都轉成對外統一封套(`data: []`);全域 handler 回的是後台 `ApiResponse` 外殼(`data: null`),對外命名空間不可沿用。500 細節只進 `logger.exception`。
- session 注入:沿用 `app.api.deps.get_db`(`Annotated[AsyncSession, Depends(get_db)]`)。理由:專案唯一 session 生命週期實作(建立 / commit / rollback),不另造第二套;測試可用既有 `dependency_overrides` 慣例;`get_db` 為純 session 供給、不含後台認證邏輯,不破壞 `/api/client` 與 `/api/v1` 的認證與稽核分離。
- 分層例外(規範偏離,已知並刻意):`03-backend/00-overview.md`「禁 api 直 import repository」— 對外版本層直呼 `ApiClientRepository.get_by_client_id`。理由:本 task 白名單無 service 檔可加、`ApiClientService` 亦不在白名單,且驗證僅一次唯讀查詢;已於 `v1_0.py` 模組 docstring 記錄。後續若對外端點增多,建議收攏成 `api_client_router` 專屬 service(升規候選)。
- 測試 `backend/tests/test_api_client_token_api.py` 15 測全綠:成功封套 + JWT(`sub` / `exp-iat=900`);四種失敗回應 JSON 全等且皆 401 invalid_client;停用後下一次即 401;雙密鑰皆可取證、retire 後舊鑰 401;`/refresh_token` 過期 token 換新 / 篡改簽章 / A 的 token 配 B 的憑證 / token 有效但密錯;限流第 31 次 429 + `Retry-After`、per-client DB 上限生效、未知 client 仍計數;連續 5 次 401 後鎖定 429(`Retry-After`=300);成功後失敗計數歸零;query string 帶憑證 → 422 封套。Redis 走本檔 `FakeRedis`(autouse,每測獨立),bcrypt 以 rounds=4 加速。
- 真實驗證(docker compose,只 build backend):acceptance curl → `{"success":false,"response_code":401,"detail":"invalid_client","data":[]}` + HTTP 401;真 client 取證 200(JWT `sub`=client_id、`exp-iat`=900)、`/refresh_token` 200、錯密鑰 401、限流(改 5/分)第 6 次起 429 + `Retry-After` 遞減、停用 401、軟刪 401。測試 client 已軟刪清理。
- 既有 mypy 唯一錯誤 `app/repositories/schedule_repo.py:528`(未修改檔案)為既存問題(task-003 已記錄),非本 task 新增。

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
