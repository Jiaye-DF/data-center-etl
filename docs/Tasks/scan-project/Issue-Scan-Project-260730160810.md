# Issue Scan — data-center-etl(260730160810)

> 掃描時間:2026-07-30 16:08 (UTC+8)|範圍:v1.5.2 + v1.6.0 全部新碼(`main...dev-v1.6.0`,commit eddf101→5cccade 共 21 筆;68 檔 +9,053/-16)+ 前次遺留存續確認|方法:四區域(後端 API Client 層/前端/v1.5.2 ETL/ENV·GIT·DEP·docs)並行掃描彙整
> v1.5.2 / v1.6.0 均無 fixed.md;task-009(可逆加密)與 task-010(單一密鑰制)為 user 裁定,掃描尊重裁定本身、僅報實作面問題。

## 0. 與前次差異(前次:Issue-Scan-Project-260721145815.md)

前次 🔴0 🟠4 🟡14 🔵14 ⚪3 → 本次 🔴0 🟠5 🟡20 🔵13 ⚪3。

- ✅ 已修 14 項:**AD-119~126、AD-129~131**(前次收口窗口修畢;本次確認新頁無 AD-125/126/131 同型重現)、**AD-132**(SAVEPOINT 防護在位,且成為本次 AD-146 的修法範本)、**R-ENV-002**(4 個 `.env*.example` 已入版控,兩把 v1.6.0 新金鑰 4 檔全覆蓋)、**R-DEP-003**(backend pyproject 全嚴格 pin + frontend package.json 零浮動,雙側實證)
- 🆕 新增 21 項:R-ENV-001 邊界案 ×1 + R-ENV-004 ×2 + AD-133~AD-150(🟠3 🟡16 🔵2)— 全部來自 v1.5.2/v1.6.0 新碼,無 Critical
- ⏸ 仍在:🟠2(R-SEC-002、R-SEC-003)、🟡4(AD-101、AD-102、AD-103、R-TEST-001)、🔵11(AD-104~108、R-DEP-005/002、R-ENV-004 舊案 ×2、R-LOG-006、CI 群 — 所在檔案未動,沿用前次結論)
- 🔄 變化 2 項:**R-AI-001 記錄**(內網資訊面再擴大:`aws-to-local-infra-arch.html` 含 VPC/地端 CIDR 規劃,無帳密,維持不成案存查)、**測試 env 硬覆寫 pattern**(`test_semantic_autofill.py:29-35` 第 **5** 版佐證,reflect 候選權重再+1)
- 裁定關閉維持:AD-127/128(HTML 入版控,user 裁定)

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 嚴重度統計 | 🔴 0 🟠 5(3 🆕 + 2 ⏸)🟡 20(16 🆕 + 4 ⏸)🔵 13(2 🆕 + 11 ⏸)⚪ 3 |
| 結論 | v1.6.0 新碼在權限(6 管理端點全 require_admin + 403 全覆蓋)、注入面、封套同構、bcrypt 非同步化、audit 五事件、軟刪過濾上全數乾淨,測試品質高(真 PG + 決定性 FakeRedis);新發現集中三群:**(a) 對外契約正確性**(AD-134 Retry-After livelock、AD-138 文件雙鑰殘留、AD-133 前端交付死鑰)、**(b) 併發與範圍圈定**(AD-135 雙 active、AD-136 未知 client_id、AD-145 autofill 全庫、AD-146 ADD COLUMN race — 與 reflect 候選「並行與背景狀態安全」同族)、**(c) 部署 env 完整性**(staging/production 缺兩把新金鑰、example 內含真值 Fernet key)。🟠 三條建議部署前修,其餘不擋合併 |

## 2. 專案摘要

- 目標:ERP Oracle → DMS → RDS PG 資料中心 ETL;v1.5.2 = schema drift 自動 ADD COLUMN + 語意映射自動補 confirmed 列;v1.6.0 = API Client 連接層首發(`/api/client/v1.0/token`+`refresh_token`、api_client_users/secrets 表、ZSET 雙窗口限流、5 次失敗鎖、後台管理 API + 前端「API Client 設定」頁、secret Fernet 可逆加密 + reveal)
- 技術棧:Next.js 16 + TS strict / FastAPI + SQLAlchemy 2 async / PostgreSQL — 與 CLAUDE.md 鎖定棧一致;唯一新增依賴 `cryptography==49.0.0`(嚴格 pin、uv.lock 同步、PyCA 官方,原 pyjwt[crypto] 轉依賴顯式化)
- Task 進度:v1.5.2 4/4 done、v1.6.0 10/10 done;後端 423 passed、前端 typecheck/lint/build 綠(前端零測試 R-TEST-001 ⏸);verification-v1.6.0.md 停在 task-007 時點(見 AD-148)
- Git:21 commit 全數符合 `(AI) <類型>: <描述>` 規範;無不當追蹤檔;`.env` 全家歷史零 commit 紀錄

## 3. 詳細發現(依嚴重度;⏸ 遺留項僅列 ID,細節見前次報告)

### 🟠 High(5 項:2 ⏸ + 3 🆕)

- [R-SEC-002] SSO login rate limit(`backend/app/api/v1/auth.py`,grep 零命中,v1.6.0 新限流模組刻意不掛後台端點)— ⏸ 自 2026-07-06
- [R-SEC-003] 安全 headers(`backend/app/main.py` 本版 diff 僅掛對外 router,無 headers middleware)— ⏸ 自 2026-07-06

#### 🆕 [AD-133] 輪替後 Secret 欄殘留舊密鑰明文,可被複製交付(前端)
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:80-152, 182`
- 內容:`SecretRevealControl` 明文存元件 state,但元件未依 `secret.uid` 加 key。admin 先「顯示」再「輪替」→ rotate 後 SECRETS tag 失效重取、`latestActive` 換代,React 沿用同一元件實例,`plainSecret` 仍是**已失效的舊鑰明文**;Secret 欄顯示與「複製」按鈕給出的都是 401 死鑰,admin 極可能把死鑰交付使用者(單鑰制下舊鑰立即失效,痛感直接)。
- 修正:`page.tsx:182` 改 `<SecretRevealControl key={latestActive.uid} ...>`,密鑰換代即重掛回遮罩態。
- 首次發現:2026-07-30

#### 🆕 [AD-134] Retry-After 契約失真:被拒請求也計入 ZSET,守規矩的 client 會永久 429(livelock)
- 檔案:`backend/app/api_client_router/common/rate_limit.py:104`(zadd 先於判定)、`84-93`(retry 估算)
- 內容:`check_rate_limit` 一進來就 `zadd`,超限被拒的請求也被記錄;`_window_retry_after` 只估「窗內最舊一筆離窗」時間。可證明的 livelock:上限 L=2,t=0,1 成功、t=2 被拒(已記錄),依 Retry-After 於 t=60 重試 → 窗內 4>2 再拒再記,此後 Retry-After 恆 1s、窗內恆 4>2 — 嚴格遵守 Retry-After 的機器 client 永久 429,除非自行退避 >60s。多窗口同時超限時取 `min(estimates)` 同族問題。對接方照規格實作 retry 迴圈就會卡死。
- 修正:二擇一 — (a) `rate_limit.py:104` 先 `zcount` 判定、只在放行時 zadd;或 (b) 保留懲罰語意但 `_window_retry_after` 改取第 `count - limit` 舊的 entry 離窗時間、多窗口取 `max`。並補「等滿 Retry-After 重試必放行」測試(現有 `test_window_slides_and_recovers` 等 61s 全清,測不到此洞)。
- 首次發現:2026-07-30

#### 🆕 [R-ENV-001 邊界案] .env.development.example 內含真值 Fernet 金鑰,且與本機 dev 實檔同一把
- 檔案:`.env.development.example:11`(入版控)、本機 `.env:29`(同值)
- 內容:`CLIENT_SECRET_ENCRYPTION_KEY` 為可用真 Fernet 金鑰(非 changeme 佔位 — Fernet 格式無法用佔位字串,會 fail-fast),即開發 DB `secret_encrypted` 欄的實際解密金鑰已入版控。緩解:註解明標 development-only、dev 測試資料已於 task-010 清空,實際暴露趨近零 — 依「dev 公開預設值不算」精神判 🟠 而非 🔴。
- 修正:example 改空值 + 保留產生指令註解(與 production example 作法一致),dev 實檔各自 `Fernet.generate_key()`;若刻意保留開箱即跑,於規範記錄「dev 共用預設金鑰白名單」避免重複觸發(見第 7 章)。
- 首次發現:2026-07-30

### 🟡 Medium(20 項:4 ⏸ + 16 🆕)

#### 🆕 [AD-135] 單一密鑰制無 DB 約束,併發 rotate 可產生 2 把 active
- 檔案:`backend/app/repositories/api_client_repo.py:135-151`、`backend/app/models/api_client_secret.py:49-52`
- 內容:`add_secret` 為 read-then-write(先 list active 再逐把 retire 後插入),READ COMMITTED 下兩併發交易各自讀到同一把舊 active → commit 後 2 把 active 並存,違反 task-010「active 恆 1」核心裁定;`_authenticated` 逐把驗,兩把都能換 token。表上無任何約束擋,測試僅覆蓋序列情境。
- 修正:migration v10 建 partial unique index `(api_client_user_pid) WHERE status='active' AND is_deleted=false` + 同步 `__table_args__`,競態方吃 IntegrityError 轉 409;或 `add_secret` 開頭 `SELECT ... FOR UPDATE` 序列化。
- 首次發現:2026-07-30

#### 🆕 [AD-136] token 端點 DB 查詢先於鎖定/限流檢查;未知 client_id 繞過 per-client 限流且無上限灑 Redis key
- 檔案:`backend/app/api_client_router/versions/v1_0.py:141-142, 158-159`、`common/rate_limit.py:100-110`
- 內容:兩端點「先查 DB → 再 _throttle」;`check_auth_lock` 不需 DB,鎖定中的洪水仍每發打一次 DB。限流 key 以未驗證的請求值 `client_id` 命名:每發換隨機 id → per-client 限流虛設(無 IP/全域維度),且每個垃圾 id 產生 ZSET(TTL 600s)+ 失敗計數 key(TTL 900s),可短時膨脹 Redis。公開對外端點,部署後首當其衝;與 backlog「rate limit」遺留 High 同族。
- 修正:`v1_0.py:141` 前先 `check_auth_lock`,鎖定中直接 429 不碰 DB(`_throttle` 拆前置/後置);全域/每 IP 維度限流列部署前補強清單(可與反向代理層一起決議)。
- 首次發現:2026-07-30

#### 🆕 [AD-137] CLIENT_SECRET_ENCRYPTION_KEY 只驗長度,非法 Fernet key 通過啟動,炸點延後到第一次建立/檢視(500)
- 檔案:`backend/app/core/config.py:33`、`backend/app/core/security.py:39-41`
- 內容:44 字元任意字串可通過 Settings 驗證正常啟動,直到 admin 首次建立/reveal 時 `Fernet(key)` 拋 ValueError → 500;與同行註解宣示的 fail-fast 不一致。部署 staging/production 補這顆 env(已知殘留)時貼錯 → 啟動綠燈、功能紅燈。
- 修正:`config.py` 加 `field_validator`,驗證時 `Fernet(value.encode("ascii"))` 建一次,失敗即 ValidationError(訊息不含 key 內容)。
- 首次發現:2026-07-30

#### 🆕 [AD-138] 單鑰制定案後,OpenAPI 摘要/schema 描述/model docstring 仍殘留雙鑰語意
- 檔案:`backend/app/api/v1/api_clients.py:103`、`backend/app/schemas/api_client.py:18`、`backend/app/models/api_client_secret.py:12`、`backend/alembic/versions/v8_add_api_client_users.py:183-184`
- 內容:rotate 端點 summary 仍寫「已有 2 把 active → 409」(直接出現在 /api/docs)、`active_secret_count` 描述仍寫「上限 2」、model docstring 與 v8 表 comment 仍寫「雙鑰輪替」— 程式行為正確、文件說謊,誤導對接與維護。
- 修正:`api_clients.py:103` 改「輪替:核發新 active 並自動撤銷舊鑰(單一密鑰制)」、`schemas/api_client.py:18` 改「恆為 0 或 1」、docstring 改單鑰語意;v8 為已套用 revision 不回改(R-DB-012),表 comment 留待下次 migration 順帶 `COMMENT ON`。
- 首次發現:2026-07-30

#### 🆕 [AD-139] create/rotate 回應的明文 secret 長駐 RTK store,違反 task-009「明文不進 RTK cache」invariant
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:710-712, 722-739, 768-779`(對照 `:92` reveal 讀完即 reset)
- 內容:reveal 路徑有守(mutation + 讀完 reset),但 create/rotate 的回應同樣含 `client_secret` 明文,mutation state 留在 redux store 直到頁面卸載(可序列化 state,Redux DevTools 可傾印)— 同一威脅模型下的漏網。
- 修正:兩個 mutation hook 解構 `reset`,`handleCreateSubmit`/`handleConfirmRotate` 讀取 result 後立即 reset,比照 reveal 做法。
- 首次發現:2026-07-30

#### 🆕 [AD-140] Secret 欄 N+1:每列各發一支 secrets 清單請求,單頁 20 列 = 21 請求
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:162`(`LatestSecretCell` 內 `useListApiClientSecretsQuery`)
- 內容:每 row 一支 `GET /api-clients/{uid}/secrets` 只為取最新 active 的 uid + revealable;開頁 21 支、每次 rotate 再雙失效重取。疊在「輪詢×每請求回源 SSO 驗證 → 429 → 502」實錘病史上的 fan-out 放大器;列表回應已有 `active_secret_count` 卻缺 secret uid,資訊差一步。
- 修正(擇一):後端 list 每項附 `active_secret_uid` + `revealable`(較乾淨);或改惰性 — 點「顯示」才 fetch。
- 首次發現:2026-07-30

#### 🆕 [AD-141] 複製按鈕無失敗處理;http 非 localhost 環境點擊直接 TypeError
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:53-58`
- 內容:`void navigator.clipboard.writeText(...)` 無 `.catch`;非 secure context(內網 IP http 直連)下 `navigator.clipboard` 為 undefined,點擊即同步例外,「複製」整顆壞掉且無提示 — 本頁核心動作就是複製密鑰。
- 修正:guard `navigator.clipboard === undefined` + `.catch`,失敗時按鈕文字切「複製失敗,請手動選取」1.5s。
- 首次發現:2026-07-30

#### 🆕 [AD-142] 停用二次確認開啟時按 Esc,整個編輯 dialog 連同表單值一起關閉
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:422-429` + `components/common/ConfirmDialog.tsx:27-34`
- 內容:`confirmingDisable` 開啟時 window 同時掛兩個 Escape listener,按 Esc 想關小確認窗,EditClientDialog 的 handler 也觸發 `onCancel()` → 編輯表單(含剛改好的值)整個消失。IssuedSecretPanel 同型結構(L202-208)因兩個 setState 對沖恰好無事。
- 修正:`page.tsx:424-426` 改 `if (event.key === 'Escape' && !confirmingDisable) onCancel()`,`confirmingDisable` 加入依賴。
- 首次發現:2026-07-30

#### 🆕 [AD-143] 流量上限輸入清空即強制跳 1(改值卡手),且無上限校驗
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:440-453`
- 內容:onChange 即刻 clamp(空字串 → 0 → 1),把 60 改 120 需全選覆蓋否則變 1120/112;此欄是後台調參即生效入口,改錯直接影響限流。另無上限,可送任意大數(等於解除限流)。全專案僅此頁用此 pattern。
- 修正:state 改存 string、clamp 移到提交時(空/<1 擋提交顯欄位錯誤);依後端 schema 加 max。
- 首次發現:2026-07-30

#### 🆕 [AD-144] autofill 落庫的 zh_name 不是「字典中文名」,是 COMMENT 組字串(GAQ04/05 說明、GAE 畫面標籤混入)
- 檔案:`backend/app/etl/semantic_autofill.py:224`、`backend/app/etl/dictionary.py:144-153, 188-204`
- 內容:propose 明定 `zh_name` = DS 字典中文名(缺則空),實作重用為 COMMENT 設計的 `fetch_column_comments`:GAQ04/05 有值時以「；」串接(如 `帳別編號；"Y":是`)、GAQ 查無退 GAE 畫面標籤。自動 confirmed 列的 zh_name 可能是長組字串,直接進儀表板與對外 JSON 的 zh_name — propose 講明「意義由 zh_name 承載」,承載體被污染。
- 修正:`dictionary.py` 加純 GAQ03 查詢(或 `include_extras: bool` 參數,autofill 傳 False),`semantic_autofill.py:224` 改用純名版;GAE fallback 是否保留請 user 裁定。
- 首次發現:2026-07-30

#### 🆕 [AD-145] autofill 掃描面 = 目標 RDS 全庫,任何落地的表都會被自動 confirmed 對外
- 檔案:`backend/app/etl/semantic_autofill.py:54-66, 173-188`
- 內容:內省目標 RDS 所有非排除 schema 的 base table,不限本輪鏡像來源表 — 手動/其他工具建在目標庫的暫存表、實驗表,下輪同步即補 confirmed 全欄映射 → 自動生成對外 view、進 JSON。超出 propose「來源新欄位」敘事;實證就在自家測試(`test_seed_semantic_mappings.py:85-92` 註解自述 AF_TEST/VG_TEST 等遺留 schema 被一併補列污染斷言)。
- 修正:`worker/tasks.py` 掛接處把本輪 `targets` 表清單傳入 `autofill_semantic_mappings` 過濾;至少把本輪補列表名 log 出來供人審。
- 首次發現:2026-07-30

#### 🆕 [AD-146] drift ADD COLUMN 無併發防護,同表雙 run 撞欄位時整表交易 abort(AD-132 同型)
- 檔案:`backend/app/etl/mirror.py:276-283`
- 內容:存在檢查與 ALTER 非原子;手動同步與排程重疊(AD-102 仍未做)時,慢者撞 `duplicate column` → 整表 ALTER+TRUNCATE+INSERT rollback、該表與 run 誤標 failed(下輪自癒,痛點是誤報)。與已修 CREATE SCHEMA race(mirror.py:248-255 SAVEPOINT)同型但無等價防護。
- 修正:`mirror.py:280` 改 `ADD COLUMN IF NOT EXISTS`(一行解);或比照 AD-132 `begin_nested()` 吞 DuplicateColumnError。
- 首次發現:2026-07-30

#### 🆕 [AD-147] autofill 的兩個 engine 建立在 try 之外:失敗連副本重灌一起跳過(違反自述契約)+ engine 洩漏
- 檔案:`backend/app/worker/tasks.py:576-581`
- 內容:兩個 `create_async_engine` 位於內層 try(582)之前、`except Exception`(610,註明「autofill 失敗不擋副本重灌」)範圍外;第二個建立失敗時第一個 engine 永不 dispose,且例外直落最外層 → `refresh_semantic_copy_and_views` 整段被跳過,與註解契約矛盾。現有測試只 patch autofill 本體,蓋不到。
- 修正:兩行移入 582 的 try 內(先初始化 None,finally 判 None 再 dispose)。
- 首次發現:2026-07-30

#### 🆕 [AD-148] verification-v1.6.0.md 停在 task-007 時點,與 tasks 清單「10/10」三處矛盾
- 檔案:`docs/Tasks/v1.6.0/verification-v1.6.0.md` vs `docs/Tasks/v1.6.0/tasks-v1.6.0.md:3`
- 內容:(a) verification 結論「8 個 task 全數完成」vs 清單「10/10」;(b) verification 記 415 passed,task-010 後為 423;(c) 殘留 #1 仍寫雙鑰語意(已被 task-010 推翻)、殘留 #2 只記 `CLIENT_JWT_SECRET` 漏了 `CLIENT_SECRET_ENCRYPTION_KEY` — 照清單部署仍 fail-fast。
- 修正:verification 補「task-008~010 增量收口」節,同步改 task 數/測試數/殘留清單單鑰語意 + 補第二把金鑰。
- 首次發現:2026-07-30

#### 🆕 [R-ENV-004] .env.staging / .env.production 實檔缺 v1.6.0 兩把新必填金鑰(啟動必 fail-fast)
- 檔案:`.env.staging`、`.env.production`(grep `CLIENT_JWT_SECRET|CLIENT_SECRET_ENCRYPTION_KEY` 零命中)
- 內容:兩把皆必填 fail-fast(min32 / Fernet 44 字元),部署本版必掛;且 verification 殘留清單只記了第一把(見 AD-148)。
- 修正:部署前兩檔各補兩把(`openssl rand -base64 32` + `Fernet.generate_key()`,禁跨層沿用)。
- 首次發現:2026-07-30

#### 🆕 [R-ENV-004] 本機 .env 相對 .env.example 缺 14 個 key
- 檔案:`.env` vs `.env.example`
- 內容:缺 `COMPOSE_PROJECT_NAME/COOKIE_DOMAIN/DB_MAX_OVERFLOW/DB_POOL_SIZE/FRONTEND_URL/NEXT_PUBLIC_*×3/REDIS_URL/SSO_*×3/SYNC_CONCURRENCY/UVICORN_WORKERS`;compose environment 覆蓋 + `:-` 空預設故本機能跑,新人對照會困惑。輕微非阻斷。
- 修正:`.env` 補齊(可空值)或 example 標註「compose 環境由 docker-compose 注入,可省略」。
- 首次發現:2026-07-30

#### ⏸ 遺留 4 項(見前次報告):AD-101(殭屍 run 治本 — worker/ 全目錄無收殮/watchdog 碼,確認未做)、AD-102(同表併發防疊 — 未做,且 AD-146 在此 race 下新增一種失敗模式,宜同案處理)、AD-103(production compose 仍帶 adminer,`docker-compose-production.yml:218-221`,compose 檔零 diff)、R-TEST-001(前端零測試 — v1.6.0 新增約 1,100 行含密鑰生命週期高後果邏輯,AD-133 正是測試最能接住的類型)

### 🔵 Low(13 項:11 ⏸ + 2 🆕)

#### 🆕 [AD-149] 表格內按鈕以裸 text-sm 蓋掉 md:text-base,桌機 14px 低於 02-frontend 明文地板(與 user 終版裁定衝突,請裁定收編或修)
- 檔案:`frontend/src/app/(main)/api-clients/page.tsx:64, 128, 138, 639, 647`(按鈕)、`659, 668`(Client ID/Secret 行內標籤 text-xs)
- 內容:utilities layer 的裸 `text-sm` 在所有斷點覆蓋 `.df-btn*` 的 `md:text-base` → 桌機五種表格內按鈕實際 14px,低於「桌機表格內容最低 text-base」地板;L659/668 標籤 12px 屬邊界。**衝突註記**:task-010 + 2026-07-30 膠囊鈕縮小均為 user 明示裁定,此條列事實供裁定 — 若收編為終版,依 CLAUDE.md 應在規範/裁定紀錄註明字級例外,而非留掃描每次觸發。
- 修正(若裁定要修):五處 `text-sm` 改 `text-sm md:text-base`;標籤 `text-xs` 改 `text-sm`。
- 首次發現:2026-07-30

#### 🆕 [AD-150] semantic_mappings english_name 無唯一約束:查重讀後寫 TOCTOU + admin update 無查重,重複時該表 view 停更
- 檔案:`backend/app/etl/semantic_autofill.py:120-154`、`backend/app/services/semantic_admin_service.py:134-136`
- 內容:`ON CONFLICT` 只保 PK;english 查重靠記憶體快照,與人工改名併發存在 TOCTOU;admin update 本就無 english 查重 — 同表重複 english 使 view CREATE 撞 duplicate column,僅留 warning、view 停更。低機率。
- 修正:RDS 真身補 `UNIQUE (table_name, english_name)`(先清重)+ admin update 加查重。
- 首次發現:2026-07-30

#### ⏸ 遺留 11 項(AD-104~108、R-DEP-005/002、R-ENV-004 舊案 ×2、R-LOG-006、CI 群,見前次報告)

### ⚪ Info(3 項)

- 🔄 [R-AI-001 記錄擴充] 內網資訊面:`docs/Arch/aws-to-local-infra-arch.html`(576-639、734-737 等)含 VPC/地端 CIDR 規劃(`10.0.0.0/16`、`10.200.0.0/16` 等),無帳密無 token,依前例不成案存查;repo 對外前須清洗名單再+1 檔。四份 Arch 文件其餘 pattern 全掃(password/secret/token/jdbc/eyJ/sk-/AKIA/email)無真值命中
- 🔄 [reflect 佐證] 測試 module-level `os.environ` 硬覆寫 pattern 第 **5** 版佐證(`backend/tests/test_semantic_autofill.py:29-35`,非 setdefault)— 歷史 reflect 候選「共用測試 DB 使用約定」權重再+1,本版不開 AD
- ⏸ [07-testing] 測試建 schema 用 `create_all` 非 alembic(自 2026-07-06)

## 4. 修正優先序

### 立刻(部署前)
1. 🟡 R-ENV-004 staging/production 補兩把金鑰(部署 blocker,順手修 AD-148 verification 殘留清單)
2. 🟠 AD-133 SecretRevealControl 加 key(一行級,交付死鑰直接傷人)
3. 🟠 AD-134 Retry-After 契約(對外首發前修,契約一旦被對接就難改)+ 🟡 AD-136 lock 前置(同檔順路)
4. 🟠 R-ENV-001 example 真值金鑰改空值+產生指令(或規範記錄白名單)
5. 遺留維持:R-SEC-002/003 + AD-103 adminer(前次「立刻」清單維持)

### 本週(v1.6.0 收口建議)
6. 🟡 AD-135 partial unique index(migration v10)+ AD-137 Fernet field_validator + AD-138 文件單鑰化(後端一批)
7. 🟡 AD-139 create/rotate reset + AD-141 clipboard guard + AD-142 Esc 分流(前端一批,皆小改)
8. 🟡 AD-144 zh_name 純名 + AD-145 autofill 圈定 targets + AD-146 IF NOT EXISTS + AD-147 engine 入 try(v1.5.2 ETL 一批)

### 有空
9. 🟡 AD-140 N+1(需動 list schema,可與後續版本一起)、AD-143 數字輸入、R-ENV-004 本機 .env 對齊
10. 🔵 AD-149(先請 user 裁定收編或修)、AD-150 english 唯一約束;遺留群(前端測試/CI/env example 舊案等)

## 5. 已跳過類別 / 規則與脈絡衝突註記

- 前端 i18n(R-FE-004)、inline 繁中 literal:單語系裁定沿用,不硬套
- 測試以真實本地 PG(非 mock SQL):既定慣例,不硬套 R-TEST-004;`test_semantic_mapping_sync` 的 `CREATE DATABASE` 為隔離手段非 DROP 類
- **task-009 可逆加密為 user 明示裁定**:Fernet 存明文可解密不報 R-DB-003(驗證路徑仍純 bcrypt、reveal admin-only+audit、log/audit 全程無明文有測試);僅報實作面(AD-137/139)
- R-BE-011(data 須 {items,total})不適用對外封套:propose 明定對外 `data` 恆陣列,後台正常 {items,total},兩層各自合規
- v8 migration downgrade 含 `drop_table`:僅撤銷本 revision 自建表、檔內明註 round-trip 必要例外,尊重既有裁定
- commit 訊息「423 測全綠」的 423 為**測試數量**(415→423),非 HTTP 423;鎖定回 429 + Retry-After 為 task-003 定案,內部自洽
- 未知版本路徑(`/api/client/v9.9/*`)與 405 回 FastAPI 預設體非封套:一致性瑕疵、無洩漏無功能後果,不報
- timing 側信道(存在的 client 才跑 bcrypt):client_id 為 dc_+24hex(96 bits 熵)列舉不可行,不報
- 已知 4 項 reflect 候選(對外層直呼 repo、retire 層數、ClientEnvelopeRoute 位置、PATCH description 不可清空):現況與記錄一致無實害升級,交 reflect 決議不重報
- 停用中 client 仍可輪替/檢視密鑰:無害(client 取不到 token),偏好級不報
- GIT/DEP:21 commit 全合規;唯一新增依賴嚴格 pin,無浮動、無 typosquat

## 6. AD-xxx(規則外發現)

本次新增 AD-133~AD-150(見第 3 章)。已巡視無發現的面向:

- **權限**:後台 6 管理端點全 require_admin + member 403 全覆蓋(含 secrets/reveal);對外 token/refresh 無守衛屬設計本意;前端 (main) 三層守衛涵蓋 /api-clients,Sidebar 非 admin 不渲染
- **注入面**:API Client 層全 SQLAlchemy 參數化;drift ADD COLUMN 識別字 quote_ident 白名單 + type_sql 常值組成;autofill 值全 bind
- **對外錯誤同構**:401 全情境 `invalid_client` 逐 byte 同構(防列舉,有測試);封套兜 422/未捕獲例外;detail 無 SQL/traceback/內部表名
- **秘密處理**:驗證路徑純 bcrypt(to_thread);log/audit 全程無明文(測試 assert);response 無 pid/hash;v9 舊列 NULL → revealable=false + 409;金鑰更換解密失敗同 409 不外拋密碼學細節
- **transaction**:create/rotate 同 session 單 commit;ALTER+TRUNCATE+INSERT 同交易;autofill 單 engine.begin
- **JWT**:HS256 + min32 fail-fast、issuer + require 全欄、algorithms 鎖定拒混淆;rotate 後在途 JWT 15min 內仍有效為 docstring 明載取捨且本版無資料端點消費,無現時實害
- **限流其餘面**:key 格式/TTL 續期/窗口滑動/fail-open 三路兜底+degraded 旗標行為正確且決定性測試覆蓋;鎖定計數 race 結果冪等
- **v1.5.2 冪等/自癒**:PK ON CONFLICT + 確定性規劃多 worker 一致;ADD COLUMN 已 commit 而 autofill 失敗下輪全量內省自癒;autofill 於 apply lock 臨界區內順序有測試錨定(AD-120 相容);時間型別 drift 新欄 naive UTC+8 ✓
- **前端紀律**:零 any、零原生 alert/confirm、無 localStorage token、三態齊(含 LatestSecretCell)、in-flight disable 全覆蓋(含連點輪替鎖全表)、invalidatesTags 完整、dialog key 重掛無殘值、列元件 memo;AD-125/126/131 同型未重現
- **時序語意**:單鑰制「關閉面板後仍可於清單重新檢視」文案與行為一致
- **測試品質**:真 PG + FakeRedis 可推時鐘,斷言到回應體逐欄/DB 落庫/audit 內容/封套逐 key;缺口即 AD-134(Retry-After 遵守後重試)與 AD-135(併發)所述

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **`04-databases/03-passwords-and-pii.md`「不可逆雜湊」原則已被 task-009 裁定開例外**(機器憑證可逆加密+reveal),規範檔未補適用範圍註記 — 升規候選,交本輪 reflect
2. **R-ENV-001 判準對「無法用佔位字串的金鑰格式」(Fernet)無 dev 公開預設值處理方式** — example 要嘛帶真值(本次 🟠)要嘛留空破壞開箱即跑,規範應擇一定案
3. **02-frontend 字級地板與 user 連續兩版的表格按鈕裁定衝突**(AD-130 → AD-149)— 地板是否對「表格內操作按鈕/輔助標籤」開例外,待裁定後回寫規範
4. **收口後追加 task 無「verification 檔須回寫」規則**(AD-148 實證:task-008~010 證據只在 commit message 與 task 檔)— 建議 `01-propose` 補一條
5. **對外 API 契約正確性(機器可讀欄位如 Retry-After、OpenAPI 描述與行為一致)無檢查面向**(AD-134/138 實證)— scan-project 心法巡視面向候選,v1.6.0 為對外首發,單版本暫記

## 8. 掃描後修正落地(收口修正窗口,2026-07-30)

- **已修 15 項**(user 指示「先進行修正 bug」,三 area 並行修畢):🟠 AD-133(SecretRevealControl 加 key)、AD-134(限流改「放行才計數」+ 半開窗口邊界 + 多窗口取 max + Retry-After 回歸鎖測試)、R-ENV-001(example 真值金鑰移除改空值);🟡 AD-135(migration **v10** partial unique index `uq_api_client_secrets_single_active` + 防禦性收斂 + service 409)、AD-136(`_throttle` 拆前置 lock / 後置 rate,鎖定中不打 DB)、AD-137(Fernet field_validator fail-fast)、AD-138(rotate summary / active_secret_count / docstring 單鑰化,表 comment 併 v10)、AD-139(create/rotate 讀後 reset)、AD-141(複製三態 + secure context guard)、AD-142(Esc 分流)、AD-143(限流欄改字串 state、提交時驗證)、AD-144(zh_name 純名 `include_extras=False`,GAE fallback 保留)、AD-145(`scope_tables` 圈定本輪 to_sync + 補列清單 log)、AD-146(`ADD COLUMN IF NOT EXISTS`)、AD-147(engine 移入 try + finally dispose)、AD-148(verification 第 7/8 節回寫)。
- **驗證**:後端全套 **429 passed**(+6 新測)、ruff / mypy 全綠;前端 tsc / eslint / build 三綠;alembic v9→v10 於 dev DB 實跑,索引與表 comment 實查在位;docker compose 全容器重建 healthy。
- **附帶修正**:`schedule_repo.py:528` 既有 mypy baseline 錯以 `getattr(result, "rowcount", 0)` 收斂(執行期行為不變)— 跨版本 verification 記錄的「既有 mypy 錯誤」項自此清零。
- **未修(記錄原因)**:R-ENV-004 staging/production 補兩金鑰(寫入真實 env 檔被權限分類器擋下,已交 user 指令自跑;本機 dev Fernet 金鑰輪替同)、AD-140(N+1,需動 list 契約,建議下版與資料端點一起)、AD-149(待 user 裁定收編或修)、AD-150 與本機 .env 對齊(有空級)、遺留群(R-SEC-002/003、AD-101/102/103,維持部署前決策)。

---

> 本次 🔴 0 🟠 5 🟡 20 🔵 13 ⚪ 3;v1.5.2/v1.6.0 新碼零 Critical,新增 🟠3 🟡16 🔵2 — 其中 15 項已於收口窗口修畢(見第 8 章)。部署本版前仍須:staging/production 兩把金鑰(user 自跑)+ 遺留 R-SEC-002/003 + AD-103 決策。
