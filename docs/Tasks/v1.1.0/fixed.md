# Fixed v1.1.0

> 本版所有規範違反 / bug 根因累積於此。條目格式見 `docs/Design-Base/01-propose/04-fixed-format.md`;§ 編號全版本連號,**禁**刪除舊條目。

## §1 — v1.1.0 新依賴已鎖版但 `01-versions.md` 套件清單未同步

- **時間**:2026-07-03T16:48+08:00
- **commit / PR**:task-001 commit(taskiq / taskiq-redis / pyyaml / pytest-asyncio / respx / types-pyyaml 鎖版)
- **影響檔案**:`backend/pyproject.toml`、`backend/uv.lock`、`docs/Design-Base/00-overview/01-versions.md`(未改)
- **問題**:task-001 依規新增 v1.1.0 後端依賴並全數鎖到 patch 版,但 `01-versions.md` 規定「加入時補進本表」;該檔屬 Design-Base,不在 task-001 `affected_files` 白名單,worker 依 multi-agent 硬約束不得修改,導致套件清單與 lock file 不一致
- **根因**:task 拆解時 `affected_files` 只涵蓋程式碼與 lock file,未把「新增依賴須同步 `01-versions.md` 套件清單」的規範義務納入任何 task 的影響檔案 → 規範義務與檔案白名單互斥
- **修正**:依賴照常鎖版(pyproject / uv.lock 已逐字一致);`01-versions.md` 補表留待收口(user 或收口 agent)處理。另註:pyproject 既有版本(fastapi 0.136.1 等)先前即高於該表 lock 範例,屬既存不一致,同樣待收口對表
- **規範參照**:`docs/Design-Base/00-overview/01-versions.md § 鎖定原則 / Sources of Truth`
- **後續**:收口時把 taskiq==0.12.4 / taskiq-redis==1.2.3 / pyyaml==6.0.3 / pytest-asyncio==1.4.0 / respx==0.23.1 / types-pyyaml==6.0.12.20260518 補進 `01-versions.md` 套件表,並以 lock 為準校正既存 lock 範例;reflect 候選 — 拆 task 時規範連動檔(版本表)應自動列入 affected_files

## §2 — etl_tables / etl_mappings 無多來源欄位,m2201 匯入以字串約定表示(設計取捨,非 bug)

- **時間**:2026-07-03T17:01+08:00
- **commit / PR**:task-008 commit(seed_etl_config)
- **影響檔案**:`backend/scripts/seed_etl_config.py`、`backend/app/models/etl_table.py` / `etl_mapping.py`(未改,僅受限)
- **問題**:v1.0.0 `m2201.yaml` 為多來源(GAT_FILE + GAQ_FILE → M2201),但 task-001 的 `etl_tables` 只有單一 `source_table` 欄位、`etl_mappings` 無 per-column 來源表欄位,匯入時無法無損表達「哪個目標欄來自哪個來源表」
- **根因**:task-001 schema 拆解時以「單來源表 1:1 搬移」為主要心智模型,未涵蓋 v1.0.0 既有的多來源 join 型 mapping(m2201),schema 表達力與來源資料形狀不一致
- **修正**:seed 以字串約定補救 — `etl_tables.source_table` 存逗號合併值(`"GAT_FILE,GAQ_FILE"`,依 yaml 出現順序去重);`etl_mappings.source_column` 對多來源表存 `"<來源表>.<欄名>"`(如 `"GAT_FILE.GAT_NO"`),單來源 DS 表維持裸欄名。task-006 engine / task-004 API 讀取時需依此約定解析
- **規範參照**:—(非違規;schema 表達力缺口)
- **後續**:reflect 候選 — 若後台需正式支援多來源表,考慮下版本為 `etl_mappings` 增設 `source_table` 欄位(migration 屬新增欄位,非 DROP),屆時本約定可退場

## §3 — passlib 1.7.4 與鎖定的 bcrypt 5.0.0 不相容,密碼雜湊改 bcrypt 直呼

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-002 commit(本地帳密登入)
- **影響檔案**:`backend/app/core/security.py`、`backend/pyproject.toml` / `backend/uv.lock`(未改,僅受限)
- **問題**:`tests/test_auth.py` 首次跑登入即紅 — passlib 1.7.4 的 bcrypt backend 載入自檢(wrap-bug 偵測)對 bcrypt>=4.1 拋 `ValueError: password cannot be longer than 72 bytes`,任何 `CryptContext(schemes=["bcrypt"]).hash()` 都會炸
- **根因**:passlib 1.7.4(2020 年後未維護)假設 bcrypt 舊版「超長密碼靜默截斷」行為;task-001 鎖版時 `passlib[bcrypt]` extra 未鎖 bcrypt 版本,uv 解析到 bcrypt 5.0.0(已改為超長直接 raise),兩者組合在任何 hash 呼叫時必炸;而 pyproject / uv.lock 僅 task-001 可動,task-002 無法改鎖版
- **修正**:`core/security.py` 改直接呼叫 `bcrypt` 套件(`hashpw` / `checkpw` / `gensalt`,統一先截斷 72 bytes 對齊舊版行為),`asyncio.to_thread` 包裝維持不變;演算法仍為 bcrypt,僅移除 passlib 包裝層(task-002 commit)
- **規範參照**:`docs/Design-Base/04-databases/03-passwords-and-pii.md § 密碼必 passlib[bcrypt] 或 argon2`(該規則於本情境被推翻:鎖定版本組合下 passlib 不可用)、`docs/Design-Base/03-backend/00-overview.md § 鎖定技術棧(passlib[bcrypt])`
- **後續**:reflect 候選 — 規範改「bcrypt(直呼)或 argon2」或改鎖 `bcrypt<4.1`;收口時若調整依賴(如移除 passlib 或鎖 bcrypt 版本)由 user / 收口 agent 決定

## §4 — INIT_ADMIN_* 必填 env 的連動義務(.env*.example 同步、既有測試 env 注入)未被白名單覆蓋

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-002 commit(本地帳密登入)
- **影響檔案**:`backend/app/core/config.py`、`.env.development.example` / `.env.staging.example` / `.env.production.example`(未改,僅受限)、`backend/tests/test_models_v110.py`(未改,僅受限)
- **問題**:task-002 依規把 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` 設為 Settings 必填欄(缺 env 即 fail-fast、禁預設帳密)後:(1) `.env*.example` 依 `02-secrets.md` 須同步補欄位,但三個 example 檔不在 task-002 `affected_files`;(2) 任何 import `app.core.db` 的入口都需要該 env → `tests/test_models_v110.py` **單獨執行**會在 collection 期 ValidationError(整套 suite 執行正常,因 `test_auth.py` 先注入 env)
- **根因**:同 §1 的白名單互斥模式 — 拆 task 時「新增必填 secret env」的規範連動檔(`.env*.example` 全層、既有測試的 env 前置注入)未列入 affected_files;且 `app/core/db.py` 於 import 期即實例化 Settings,使 env 需求擴散到所有測試入口
- **修正**:本機以 gitignored `backend/.env` / 根 `.env` 補 `INIT_ADMIN_*` dev 值,單獨執行 `test_models_v110.py` 已恢復綠;`.env*.example` 補欄位留待收口或 task-012(其 affected_files 含 `.env.example`)處理
- **規範參照**:`docs/Design-Base/00-overview/02-secrets.md § .env*.example 規則(新增 secret 欄位 → 同步全層 example)`
- **後續**:收口時把 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD`(placeholder 值)補進三個 `.env.*.example`;CI 若單檔跑 `test_models_v110.py` 需先注入 env;reflect 候選 — 新增必填 env 的 task 應自動把 `.env*.example` 列入 affected_files

## §5 — now_tw() 未能落在規範指定的 `app/utils/datetime.py`,暫置 `app/etl/engine.py`

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-006 commit(ETL 執行核心)
- **影響檔案**:`backend/app/etl/engine.py`、`backend/app/utils/datetime.py`(未建,僅受限)
- **問題**:`05-timezone.md` 規定時間取得統一寫 `app/utils/datetime.py` 並 export `now_tw()` / `to_tw(dt)`,各層 import 同一處、禁各 service 自寫;task-006 需要 now_tw 但 `app/utils/*` 不在 affected_files 白名單,依 multi-agent 硬約束不得新建
- **根因**:task 拆解時未把「首個需要時間函式的 task 應建立 `app/utils/datetime.py`」的規範連動檔納入任何 task 的 affected_files(與 §1 / §4 同型:規範義務與檔案白名單互斥)
- **修正**:`now_tw()` 暫實作於 `backend/app/etl/engine.py` 並由 `app.etl` re-export,行為完全對齊規範(aware,Asia/Taipei);後續 task(005 / 007)需要時間函式時 import `app.etl.now_tw`,勿另寫
- **規範參照**:`docs/Design-Base/00-overview/05-timezone.md § 後端 datetime 實踐`
- **後續**:收口時把 now_tw 搬至 `app/utils/datetime.py` 並改各處 import(或由首個 affected_files 含該路徑的 task 順手搬);reflect 候選 — 拆 task 時共用 util 檔應指派唯一 owner task

## §6 — 本機 Windows 無 tzdata,`ZoneInfo("Asia/Taipei")` 直接 raise,fallback 固定 +8

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-006 commit(ETL 執行核心)
- **影響檔案**:`backend/app/etl/engine.py`、`backend/pyproject.toml`(未改,僅受限)
- **問題**:`05-timezone.md` 範式為 `datetime.now(ZoneInfo("Asia/Taipei"))`,但 Windows 無系統 IANA tz 資料庫且 `tzdata` 套件未列依賴,實跑即 `ZoneInfoNotFoundError`,測試在本機必紅
- **根因**:依賴鎖版(task-001)未涵蓋 `tzdata`(Linux container 有系統 tzdata 所以未被發現;跨平台差異未納入鎖版考量),而 task-006 依規不得動 `pyproject.toml`
- **修正**:`engine.py` 以 try/except fallback:`ZoneInfo("Asia/Taipei")` 失敗時改 `timezone(timedelta(hours=8), "Asia/Taipei")`;台灣無 DST,行為等價,容器內(有 tzdata)仍走 ZoneInfo 正軌
- **規範參照**:`docs/Design-Base/00-overview/05-timezone.md § 後端 datetime 實踐`
- **後續**:收口時評估把 `tzdata==2025.*` 補進 pyproject(僅 task-001 / 收口可動),屆時 fallback 可保留為防禦;task-012 Dockerfile 須依規安裝系統 tzdata + `TZ=Asia/Taipei`

## §7 — task-003 白名單與規範連動檔互斥:client 子目錄 / schema 位置 / lifespan 建立均無法照規範落檔

- **時間**:2026-07-03T17:55+08:00
- **commit / PR**:task-003 commit(DF-SSO 後端整合)
- **影響檔案**:`backend/app/clients/df_sso.py`、`backend/app/api/v1/sso.py`、`backend/app/schemas/`(未動,僅受限)、`backend/app/main.py`(未動,僅受限)、`backend/app/repositories/user_repo.py`(未動,僅受限)
- **問題**:task-003 落檔時三處無法對齊 Design-Base:(1) `90-third-party-service/00-overview.md` 規定第三方 client 走 `app/clients/<service>/` 子目錄(client/schemas/errors/README 分檔),但 task 檔範圍要點與 affected_files 均明示單檔 `app/clients/df_sso.py`;(2) SSO 回應 schema 依慣例應落 `app/schemas/`,但該目錄無任何檔案在白名單 → `SsoMeResponse` 等暫定義於 `api/v1/sso.py`;(3) `01-client-design.md` 規定 httpx client 於 FastAPI lifespan 建立 + dispose,但 `main.py` 不在白名單 → 改為 `get_df_sso_client()` 惰性單例(連線池仍共用,無每 request 開新 client)。另 `user_repo.py` 不在白名單,`get_by_sso_subject` 查詢暫落 `sso_service.py`
- **根因**:與 §1 / §4 / §5 同型 — 拆 task 時 affected_files 只列「功能主檔」,未把規範要求的結構連動檔(client 子目錄四檔、schemas 檔、main.py lifespan、repo 擴充)納入白名單;且規範優先序(Design-Base > Tasks)與 multi-agent 白名單硬約束在此互斥,worker 依約束取白名單
- **修正**:單檔 client 內部仍按規範分區(錯誤類 / schema / client / 單例),行為契約(timeout ≤8s / no-store / 錯誤轉 AppError / 連線池單例)全數對齊;偏離處均在程式碼註解標記並指向本條
- **規範參照**:`docs/Design-Base/90-third-party-service/00-overview.md § 集中位置`、`01-client-design.md § httpx.AsyncClient(lifespan 建立)`
- **後續**:收口時可將 `df_sso.py` 升格為 `clients/df_sso/` 子目錄、schema 移 `app/schemas/sso.py`、client 建立/釋放掛進 lifespan(`aclose` 已備);reflect 候選 — 拆 task 時第三方串接應自動把 client 子目錄與 main.py lifespan 列入 affected_files

## §8 — DF-SSO 契約 #1 未全面落地:通用守衛(deps.get_current_user)不辨 provider,back-channel 撤銷為 process-local

- **時間**:2026-07-03T17:55+08:00
- **commit / PR**:task-003 commit(DF-SSO 後端整合)
- **影響檔案**:`backend/app/api/deps.py`(未動,僅受限)、`backend/app/api/v1/auth.py`(未動,僅受限)、`backend/app/services/sso_service.py`
- **問題**:模式 B 契約要求守衛依 JWT `provider` 分流(`sso` → 每次回源中央,`local` → 本地驗證)。本 task 的 `/api/v1/sso/me` 已完整落地(即時回源、中央 401 刪 cookie、不可達 502 不刪);但 task-002 建立的通用守衛 `deps.get_current_user`(供 require_admin / 後續 004/005 API 使用)只驗本地 JWT + 查 users 表,SSO 來源 token 走這些端點時不會回源中央 — 中央 session 被撤銷後,SSO 使用者對一般 API 的存取要到 JWT 過期(≤86400s)或前端下次打 `/sso/me` 才失效。另 back-channel logout 的撤銷註記(`sso_service._sso_revoked_at`)為 process-local dict:多 worker / 重啟即遺失,且 `deps.py` 不在白名單無法讓通用守衛讀取
- **根因**:拆解時把「雙軌守衛分流」隱含歸給 task-003,但守衛檔 `api/deps.py` 只列在 task-002 的 affected_files(002 實作時尚無 provider 概念);且本版無共享 session store(redis 屬 task-007/012),契約「清 session 即失效」缺少跨 process 載體
- **修正**:本 task 範圍內以「SSO 端點即時回源 + JWT 效期對齊 cookie 86400s + process-local 撤銷註記」落地;偏離處於 `sso_service.py` 註解標記
- **規範參照**:`docs/Design-Base/90-third-party-service/08-df-sso.md § 4 條硬性契約 #1 / 兩種整合模式(模式 B)`
- **後續**:task-004/005 掛權限或收口時,`deps.get_current_user` 應補 provider 分流(`provider=="sso"` → 回源中央或查共享撤銷表);task-007/012 redis 就緒後,撤銷註記可遷至 redis 使多 worker 一致;reflect 候選 — 雙軌登入專案應指定「守衛分流」的唯一 owner task
