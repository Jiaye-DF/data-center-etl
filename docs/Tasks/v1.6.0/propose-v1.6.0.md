# Propose v1.6.0

## 版本目標

DataHub API Gateway 的第一層——API Client 連接層(JWT 驗證)首發:外部應用系統以 Client Credentials(client_id + secret)向平台換取 15 分鐘短效 JWT,建立對外資料供應的身分驗證地基。本版對外**僅做 token 取得與刷新兩個端點**,並配套 API Client 後台管理(含前端「API Client 設定」介面,與既有使用者 / 角色體系分離)與 per-Client 限流(參數存 DB、後台可調);路由與行為完整遵循 `docs/Arch/datahub-api-gateway-arch.html` 模組①。價值對象:外部串接方(標準化、零人工的取證流程)、管理員(發證 / 停權 / 調限流一站完成)、平台自身(後續模組③④⑤ 全部踩在這層之上)。

## In Scope

- **`POST /api/client/v1.0/token`**:client_id + client_secret(放 body 不放 query)→ 驗 secret 雜湊 + Client 啟用狀態 → 簽發 15 分鐘短效 JWT(`sub`=client_id、`exp`=15min);統一封套回傳。
- **`POST /api/client/v1.0/refresh_token`**:過期 access token + client_id + client_secret 語意刷新——額外驗舊 token **簽章有效(忽略 exp)且 `sub`=client_id**(防交叉取 token),同樣驗 secret;**不發 refresh token**,回應同 `/token`。
- **`api_client_users` 資料表**(+ `api_client_secrets` 子表):遵循 BaseModel 規範(pid BIGINT 內部主鍵 + uid UUID 對外 + 軟刪除 + audit 欄位);secret **只存雜湊**、明文僅發放時顯示一次、以子表支援雙 secret 並存輪替;`status` 啟用/停用;per-Client 限流參數(每分鐘 / 每 10 分鐘)為本表欄位。**與後台既有使用者 / 角色體系完全分離**——API Client 是「機器身分」,獨立資料表與管理流,不掛入、不共用後台系統的 users / roles。
- **API Client 管理(後台 `/api/v1` + 前端管理介面,DF-SSO 管理員)**:sidebar 新增「**API Client 設定**」獨立 nav 區塊(與既有使用者 / 角色選單分開);管理頁提供建立 Client(核發 client_id + client_secret,明文一次性顯示供交付申請人)、輪替 secret、啟用/停用、Rate Limit 參數編輯。
- **Rate Limit 參數化(per Client)**:預設**每分鐘最多 30 次、每 10 分鐘最多 200 次**;參數**存入 DB**、後台管理介面可逐 Client 修改;限流計數快取 key 格式為 **`rate_limit:client:<client_id>`**(直接用請求所帶的 client_id,驗證層不查 DB)。
- **JWT 本地驗簽共用依賴**:Bearer JWT 驗簽不回源、不查 DB,供後續 `{service}` 資料端點掛用;本版先由 `/refresh_token` 驗舊 token 使用。
- **對外路由命名空間**:依 Arch 版本策略建立 `/api/client/{version}/...` 命名空間與薄版本掛載層,與後台 `/api/v1` 分離,middleware / 限流 / 稽核策略各自掛。
- **token 端點抗壓**:上述 per-Client 限流(30/分、200/10 分,DB 參數)套用於 token 端點,另加連續失敗暫時鎖定(計數與鎖定放 Redis,帶 TTL 自動解鎖);Redis 故障 **fail-open + 大聲告警**。
- **錯誤碼約定**:secret 錯 / Client 不存在 / 已停用 / 舊 token 驗證不過一律 `401 invalid_client`(不區分原因、防列舉);爆破與超限 `429` + `Retry-After`;成功與錯誤一律統一封套(`success / response_code / detail / data`),`detail` 不洩漏內部設計。

## Out of Scope

- **資料供應端點**(`GET/POST/... /api/client/v1.0/{service}/operations/...`)、權限引擎(模組③)、資料供應 API(模組④)、稽核模組(模組⑤)——本版 token 僅證明身分,尚無資料可取。
- **後台權限模型**(系統別 / 作業 / 角色權限設定檔 / Role / 特例權限)——模組② 僅先落 `api_clients` 管理,權限階層整套後續版本。
- 資料 API 端點的限流**掛載**(資料端點本版不存在;per-Client 限流參數與計數機制本版已建,後續版本直接沿用)。
- JWT 簽章金鑰輪替機制(本版單金鑰 + env 注入;輪替後續版本)。
- 不處理其他既有遺留(殭屍 run、adminer 外露、安全 headers 等,見 scan backlog)。

## 對外承諾

- `POST /api/client/v1.0/token`:憑有效 client_id + secret 回 `200` 統一封套,`data` 含 `access_token`(JWT)、`token_type="Bearer"`、`expires_in=900`;無效憑證一律 `401 invalid_client`,回應不透露是哪一項不過。
- `POST /api/client/v1.0/refresh_token`:憑過期 access token + client_id + secret 換新 token,回應結構同 `/token`;舊 token 簽章無效或 `sub` ≠ client_id → `401 invalid_client`。
- Rate Limit:同一 Client 超過**每分鐘 30 次或每 10 分鐘 200 次**(或後台調整後的值)→ `429` + `Retry-After`;後台修改參數後,下一次請求即依新值判斷。
- token 端點連續失敗 → 暫時鎖定並回 `429`(附 `Retry-After`),TTL 到期自動解鎖,無需人工。
- 簽出的 JWT:`sub`=client_id、有效期 15 分鐘、可本地驗簽(不依賴外部服務)。
- 管理介面:sidebar「API Client 設定」區塊可完成建立 / 發證 / 輪替 / 啟停 / 限流參數調整全流程;client_secret 明文僅建立與輪替當下顯示一次。
- 後台既有 `/api/v1` 行為與效能不變,既有使用者 / 角色管理不受影響;停用 Client 後下一次 `/token`、`/refresh_token` 即被拒。

## 風險與相依

- 技術風險:JWT 簽章金鑰洩漏 = 可自簽任意 token——金鑰走既有 secrets 規範(env 注入 + fail-fast,禁入版控);演算法與雜湊方案(HS/RS、bcrypt/argon2)屬 task 層決策。
- 技術風險:Redis fail-open 決策(限流失效時放行)——內網場景限流定位為防失控、非防攻擊,以告警補償;若被推翻改 fail-closed,token 供應將依賴 Redis 存活,需在 task 註記。
- 技術風險:`/refresh_token` 與 `/token` 安全等價(同樣驗 secret),價值在語意與稽核鏈——串接方文件須講清楚,避免誤解為免 secret 刷新。
- 技術風險:限流參數存 DB,每請求讀取的成本與生效即時性需取捨(直查 vs 短 TTL 快取)——屬 task 層決策,但「後台修改後下一次請求即生效」為對外承諾,不得犧牲。
- 架構相依:路由格式、錯誤碼、封套、資料表設計全部以 `docs/Arch/datahub-api-gateway-arch.html` 模組① 為準;偏離須回寫 Arch 文件。
- 第三方依賴:無新增(Redis / PostgreSQL 沿用既有)。
- 跨團隊阻塞:無。

## 驗收標準

- 後端 `cd backend && uv run pytest` 全綠;`uv run ruff check app tests` + `uv run mypy app` 無新增錯誤。
- 整合驗證(本地 docker compose):
  - 後台建立 Client(取得 client_id + 一次性 secret)→ `POST /api/client/v1.0/token` 回 200,JWT 解開 `sub`=client_id、`exp`≈15 分鐘、`expires_in=900`。
  - 錯誤 secret / 不存在的 client_id / 已停用 Client → 一律 `401 invalid_client`,回應體無法區分三者。
  - Rate Limit:同一 Client 一分鐘內第 31 次請求 → `429` + `Retry-After`;10 分鐘窗第 201 次 → `429`;Redis 內計數 key 符合 `rate_limit:client:<client_id>` 格式;後台把該 Client 額度調高後,下一次請求即依新值放行。
  - 連續失敗達門檻 → `429` + `Retry-After`;等待 TTL 後自動解鎖可再取證。
  - `/refresh_token` 四情境:過期 token + 正確 secret → 200 換新;舊 token 簽章無效 → 401;`sub` ≠ client_id(拿 A 的 token 配 B 的 secret)→ 401;secret 錯 → 401。
  - secret 輪替:發新 secret 後新舊並存期兩把皆可取 token,汰舊後舊 secret 401。
- 統一封套結構驗證:成功與錯誤回應皆含 `success / response_code / detail / data` 四欄,`detail` 無內部設計資訊。
- 手測(前端):sidebar 出現「API Client 設定」獨立區塊(不混入既有使用者 / 角色選單)→ 建立 Client 顯示一次性 secret → 編輯限流參數存檔 → 停用後取證被拒。
- 後台 `/api/v1` 既有測試迴歸全綠(命名空間分離不影響現有功能);既有使用者 / 角色管理頁行為不變。

## 決策記錄

- 2026-07-30:本版範圍**僅 `/token` 與 `/refresh_token` 兩端點**為 user 裁定(「先針對 token 和 refresh_token 即可」);資料端點與權限模型後續版本。
- 2026-07-30:路由格式與模組行為**完整遵循 Arch API Gateway 架構**為 user 明示要求。
- 2026-07-30:Rate Limit 參數為 **user 裁定**——預設每分鐘 30 次、每 10 分鐘 200 次,參數存 DB、後台管理介面可修改;快取 key 固定 **`rate_limit:client:<client_id>`**(user 裁定直接以 client_id 為 key)。此 key 命名取代 Arch 文件原寫的 `rl:` 前綴慣例,**Arch 文件待同步更新**。
- 2026-07-30:**前端管理介面入本版**為 user 裁定(推翻初稿的 Out of Scope)——每個申請方需人工核發 client_id + client_secret,故需可新增 API Client 的管理頁;sidebar 立「API Client 設定」獨立 nav 區塊。
- 2026-07-30:**API Client 與後台系統既有使用者 / 角色完全分離**為 user 裁定——機器身分獨立成表與管理流,不共用後台 users / roles。
- 2026-07-30:表設計經 user 確認——主表名 **`api_client_users`** 為 user 裁定(取代 Arch ERD 的 `api_clients`,**Arch 文件待同步更新**);secret 拆 `api_client_secrets` 子表(雙鑰輪替)、限流參數放主表欄位(`rate_limit_per_minute` 預設 30 / `rate_limit_per_10min` 預設 200)。
- 程序註記:本 propose 由 AI 依 2026-07-30 對話整理(比照 v1.3.1 / v1.5.1 / v1.5.2 慣例),user 複核後生效。
