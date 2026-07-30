# Verification v1.6.0(2026-07-30)

> 環境:本機 docker compose 全套(`etl_backend` / `etl_frontend` / `etl_postgres` / `etl_redis` / `etl_worker` / `etl_scheduler` 全 healthy)。分支 `dev-v1.6.0`。整合驗證一律用**本機 dev DB**(`data_center_etl`,port 5435,容器內網 `postgres:5432`)透過真實 HTTP 呼叫已啟動的 `etl_backend`(非 mock),與 `uv run pytest` 使用的自建 `data_center_etl_test` 完全隔離,無交叉污染。所有測試用 API Client(`v160-e2e-worker-h` / `v160-e2e-worker-h-B`)驗畢已**停用 + 全數密鑰汰換**(無 DELETE、無清 DB),殘留兩筆 `disabled` 狀態的機器身分紀錄屬預期(比照禁 DROP / 禁物理刪除慣例)。

## 1. 測試 / 靜態檢查全綠

- 後端完整套件:`cd backend && uv run pytest` → **415 passed**(170.26s)。
- `uv run ruff check app tests` → All checks passed。
- `uv run mypy app` → 僅既有 `app/repositories/schedule_repo.py:528`(`Result[Any]` 無 `rowcount`)一筆錯誤,非 v1.6.0 新增(對齊 v1.5.0/v1.5.1/v1.5.2 verification 既有記錄)。
- `cd frontend && npm run build` → 成功,`/api-clients` 出現在建置輸出(靜態頁),13 個路由全數編譯通過。

## 2. 對 propose 驗收標準逐項(整合驗證,docker compose 真實 HTTP)

### (1) 後台建立 Client → `POST /api/client/v1.0/token` 200,JWT `sub`/`exp`/`expires_in`

**PASS**。以管理員 session(`POST /api/v1/auth/login`)建立 Client `v160-e2e-worker-h`:

```
POST /api/v1/api-clients → 201
data.client.client_id = dc_2732b7206ce854dc8555e467
data.client_secret     = sj-cy4Ud3WbYUfl1RIYa1i9rfsWXbRHlgBiMAzQ_7KY（明文僅此一次）
```

取證:

```
POST /api/client/v1.0/token {"client_id":"dc_2732...","client_secret":"sj-cy4..."}
→ 200 {"success":true,"response_code":200,"detail":"","data":[{"access_token":"...","token_type":"Bearer","expires_in":900}]}
```

JWT 解碼(HS256 payload):

```json
{"sub":"dc_2732b7206ce854dc8555e467","iat":1785387610,"exp":1785388510,"iss":"datahub-api-gateway"}
```

`sub` = client_id、`exp-iat = 900`、`expires_in = 900`,三者一致。

### (2) 錯 secret / 不存在 client_id / 已停用 Client → 三者 401 回應 JSON 全等

**PASS**。三種情境回應 byte-for-byte 相同:

```
錯 secret        → 401 {"success":false,"response_code":401,"detail":"invalid_client","data":[]}
不存在 client_id  → 401 {"success":false,"response_code":401,"detail":"invalid_client","data":[]}
已停用 Client     → 401 {"success":false,"response_code":401,"detail":"invalid_client","data":[]}
```

（已停用情境:先 `PATCH /api/v1/api-clients/{uid}` 改 `status=disabled`,取證立即變 401,驗畢改回 `enabled` 繼續後續驗證。）

### (3) Rate Limit:雙窗口 + key 格式 + 後台調整即生效

**PASS(全部子項)**。

- **每分鐘窗**:`PATCH` 該 Client `rate_limit_per_minute=5`,清空舊 Redis key 後連續取證:第 1–5 次 `200`,**第 6 次 `429`** + `retry-after: 57`,`detail="rate_limited"`。
- **10 分鐘窗**:另設 `rate_limit_per_minute=300`(排除干擾)、`rate_limit_per_10min=10`,清空舊 key 後連續取證:第 1–10 次 `200`,**第 11 次 `429`**(`{"success":false,"response_code":429,"detail":"rate_limited","data":[]}`)。
- **Redis key 格式**:`docker exec etl_redis redis-cli KEYS "rate_limit:client:*"` 實查,命中 `rate_limit:client:dc_2732b7206ce854dc8555e467`,格式恰為 `rate_limit:client:<client_id>`,無其他前綴或後綴變形;`ZCARD` / `TTL` 確認為 ZSET 滑動窗口(TTL ≈ 587–600s)。
- **後台調高後立即生效**:第 6 次 `429` 後,`PATCH rate_limit_per_minute=50`,**下一次請求立即 `200`**(未等待窗口重置),證明「參數讀取即時、無快取延遲」對外承諾成立。

### (4) 連續失敗鎖定:5 次 401 → 429 鎖定,TTL 到期自動解鎖

**PASS**。清空 `auth_fail` / `auth_lock` key 後,連續 5 次錯 secret 皆回 `401`(每次皆計入失敗計數,回應本身不因鎖定門檻而變 429);**第 6 次請求**(門檻已達)→ `429` + `retry-after: 288`,Redis `auth_lock:client:<id>` 存在且 `TTL ≈ 286s`(對齊 task-003 定案的 300 秒)。

自動解鎖驗證採**縮短 TTL 佐證**(對齊 v1.5.x 慣例,300 秒等待改用 `redis-cli EXPIRE` 模擬 TTL 到期,驗證的是同一段 `check_auth_lock` 讀 TTL 判斷邏輯,非另開後門):`EXPIRE auth_lock:client:<id> 3` → `TTL=2` → 等待 4 秒 → `EXISTS` 回 `0`(key 已過期消失)→ 以正確 secret 取證 → **`200`**,確認鎖定到期後自動解鎖、無需人工介入。

### (5) `/refresh_token` 四情境

**PASS(4/4)**。另建第二個 Client `v160-e2e-worker-h-B`(`dc_69e937d67cdee00ec83de7a5`)供 `sub` 不符情境使用;「過期 token」以 host 端用 `.env` 內 `CLIENT_JWT_SECRET`(僅本機開發預設值,非正式機密)手動簽出一枚 `exp` 已過去的合法簽章 token(claims 與 `sign_client_jwt` 完全同構:`sub`/`iat`/`exp`/`iss`),等效於自然過期但免等 15 分鐘:

```
情境1(過期 token + 正確 secret A)           → 200,換發新 token
情境2(篡改簽章 — 竄改 token 最後 2 字元)      → 401 invalid_client
情境3(A 的 token + B 的 client_id/secret)    → 401 invalid_client（sub 不符）
情境4(token 有效但 secret 錯)                → 401 invalid_client
```

四者皆與 `/token` 端點一致採 `401 invalid_client`,不透露不過原因。

### (6) secret 輪替:雙鑰並存 + 汰舊後 401

**PASS**。Client A 執行 `POST /{uid}/rotate-secret` 取得第二把 active 密鑰:

```
輪替前:active_secret_count=1
輪替後:active_secret_count=2,新明文 secret 僅此一次回傳
```

- 並存期:舊密鑰 `sj-cy4...` 與新密鑰 `J1MPf...` **皆可** `POST /token` 取得 `200`。
- `GET /{uid}/secrets` 取回兩把 `uid`,對舊密鑰 `uid` 執行 `POST /secrets/{secret_uid}/retire` → `active_secret_count` 降回 1。
- 汰舊後:舊密鑰 `sj-cy4...` 取證 → **`401 invalid_client`**;新密鑰 `J1MPf...` 仍 `200`。

### (7) 統一封套結構驗證

**PASS**。上述所有 `/api/client/v1.0/*` 回應(`200` / `401` / `429`)實測皆四欄齊全 `success / response_code / detail / data`,`data` 恆為陣列(成功含 1 筆物件、失敗為 `[]`);`detail` 一律為 `""`(成功)、`"invalid_client"`、`"rate_limited"` 三種簡短字串,未見任何內部堆疊 / SQL / 檔案路徑等內部設計資訊外洩。

### (8) 前端手測(task-006 清單)彙整 + 既有 `/api/v1` 迴歸

- **既有迴歸**:`uv run pytest` 全套 **415 passed**(含既有 `test_users_api.py` / `test_auth.py` 等,`/api/client` 命名空間分離未影響既有測試);另以真實 HTTP 抽測:`GET /api/v1/users`(200,列表正常)、`GET /api/v1/roles`(200,`admin`/`member` 兩筆)、前端 `/users` 頁(`HTTP 200`)、前端 `/api-clients` 頁(`HTTP 200`)。
- **前端手測**:task-006 完成註記已列出 5 項純 UI 呈現待人工複測(sidebar 獨立區塊可見性、一次性面板實際渲染、複製按鈕、編輯/停用 dialog 互動、輪替按鈕禁用狀態呈現),當時已用「直接呼叫後端 API 比對前端程式碼發出的 request/response 形狀」做等效驗證。本次 007 收口**未新增瀏覽器自動化工具**(環境限制與 worker-F 記錄一致),故此 5 項**維持待人工複測**狀態,列入本文件「殘留事項」,不算過也不算不過,如實標記「環境受限待補」。

## 3. 驗證期間 run log 檢查

`docker compose logs backend --since 20m` 抽查(grep `\[ERROR\]|CRITICAL`):**無命中**,驗證期間(含 6 次以上刻意觸發的 401/429 錯誤路徑)無新增 ERROR / CRITICAL 級訊息,fail-open 分支未被觸發(未做 Redis 斷線測試,該分支已由 task-003 單元測試覆蓋,見 task-003 完成註記)。

## 4. 驗證後清理

- 測試用兩個 API Client(`v160-e2e-worker-h` / `v160-e2e-worker-h-B`)驗畢**已停用**(`status=disabled`)且**全數密鑰已汰換**(`status=retired`),限流參數已改回預設 `30/200`;全程無 `DELETE`、無清 DB、無 `DROP`,殘留紀錄本身即為「停用」示範。
- `docker exec etl_redis redis-cli KEYS "rate_limit:client:*"` / `auth_fail:*` / `auth_lock:*` 測試期間產生之 key 皆為短 TTL(600s / 900s / 300s 或已手動 `EXPIRE` 到期),不需額外清理。
- 收口後重跑 `cd backend && uv run pytest -q` 確認全套仍 **415 passed**(整合驗證走 dev DB、未觸碰 test DB,無交叉污染)。

## 5. Arch 文件回寫(`docs/Arch/datahub-api-gateway-arch.html`)

僅兩類決策同步,diff 共 5 個 hunk(皆歸屬下列兩類,其餘內容零異動):

1. **表名 `api_clients` → `api_client_users`**(4 處:模組②方塊圖標籤 1 處 + ERD 兩條關聯線 + ERD 實體區塊標頭),並將 ERD 內 `secret_hash` 欄位說明由「secret 只存雜湊」改為「已拆至 `api_client_secrets` 子表(雙鑰輪替),本表不再直存」。
2. **限流 key**:「沿用既有 ETL Redis 加 `rl:` 前綴隔離」改為「key 格式 `rate_limit:client:<client_id>`」,並補上「參數存 DB(預設 30/分、200/10 分),後台可逐 Client 調整」一句。

驗證:`grep -n "api_clients\b"` 與 `grep -n "rl:"` 對該檔皆**零命中**,確認殘留字樣清除乾淨且未觸及其他內容。

## 6. 逐項判定總表

| propose 驗收標準 | 判定 |
| --- | --- |
| 後端 pytest 全綠 + ruff/mypy 無新增錯誤 | **過** |
| 建立 Client → `/token` 200,JWT `sub`/`exp`/`expires_in` 正確 | **過** |
| 錯 secret / 不存在 client_id / 已停用 → 三者 401 同構 | **過** |
| Rate Limit 雙窗口(31次/201次)+ key 格式 + 後台調整即生效 | **過** |
| 連續失敗鎖定 429 + TTL 自動解鎖 | **過**(TTL 到期以縮短 TTL 佐證,方法見上) |
| `/refresh_token` 四情境 | **過** |
| secret 輪替並存 + 汰舊後 401 | **過** |
| 統一封套四欄 + `detail` 不洩內部設計 | **過** |
| 前端手測(task-006 清單) | **環境受限待補**(純 UI 呈現項,已有 API 層等效驗證,詳見殘留事項) |
| 既有 `/api/v1` 迴歸(pytest 全套 + users/roles 抽測) | **過** |
| Arch 文件回寫兩處決策 | **過** |
| `cd frontend && npm run build` 成功 | **過** |

無「不過」項,故無需開 `fixed.md`。

## 殘留事項

1. **前端 UI 純視覺互動項待人工複測**(繼承 task-006 完成註記清單):sidebar「API Client 設定」獨立區塊可見性、建立/輪替一次性 secret 面板實際渲染與複製按鈕、編輯/停用 dialog 二次確認互動、輪替至 2 把 active 後按鈕禁用狀態呈現。背後業務邏輯已由 task-006 / task-008 / 本次 007 以真實 API 呼叫等效驗證。
2. **部署前必辦**:`.env.staging` / `.env.production` 尚未有 `CLIENT_JWT_SECRET`,部署前須各自生成 32+ 字元強隨機值(`openssl rand -base64 32`),**禁沿用 `JWT_SECRET_KEY`**,否則測試站 / 正式站啟動會 fail-fast(worker-B task-002 完成註記記錄)。
3. **PATCH `description` 無法清空**:`api_client_repo.update` 沿用 `None = 不變更` 語意(task-001 定義、task-005/006 已知繼承),若日後需清空欄位需改 repo 語意,非本版缺陷。
4. **既有 mypy 錯誤** `app/repositories/schedule_repo.py:528`(非本版新增,對齊 v1.5.x 既有記錄)。
5. **Reflect 候選(跨 task 累積,待集中決議)**:
   - 對外版本層(`v1_0.py`)直呼 `ApiClientRepository`,偏離「api 層禁直 import repository」規範(worker-E task-004 記錄,已於 module docstring 註記);建議後續收攏成 `api_client_router` 專屬 service。
   - `POST /{uid}/secrets/{secret_uid}/retire` 為三層路徑,`01-routing.md` 建議「多層最多兩層」(worker-D task-005 記錄),路徑本身由規格定案不得自行變更。
   - `ClientEnvelopeRoute`(統一封套的 `APIRoute` 子類)目前定義於 `versions/v1_0.py`,語意上更接近共用元件,建議後續版本挪至 `common/`(worker-E task-004 隱含記錄於程式結構,本次收口一併提出)。
   - 前端 secret 清單原本「僅本工作階段追蹤」的設計缺口已由 task-008 補後端 `GET .../secrets` 端點徹底解決,此項不再是待辦(僅存檔記錄供對照)。

## 結論

v1.6.0(DataHub API Gateway 模組① — API Client 連接層)8 個 task 全數完成並通過本次 e2e 收口驗證,propose 驗收標準逐條過關(1 項純 UI 呈現受環境限制待人工複測,不影響功能判定),Arch 文件兩處決策已同步回寫。可進入下一版本規劃。
