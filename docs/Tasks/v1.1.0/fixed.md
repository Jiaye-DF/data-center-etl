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

> 收口(2026-07-06):已完成 — `01-versions.md` 套件表補齊六依賴 + tzdata==2026.2 / python-multipart / pip-audit,既存範例以 pyproject / uv.lock 為準校正,並補「Sources of Truth 為 pyproject / uv.lock」註記。

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

> 收口(2026-07-06):已完成 — 三個 `.env.*.example` 補 `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD`(development 給 dev 預設值;staging / production 留空並註記必填、禁預設帳密)。

## §5 — now_tw() 未能落在規範指定的 `app/utils/datetime.py`,暫置 `app/etl/engine.py`

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-006 commit(ETL 執行核心)
- **影響檔案**:`backend/app/etl/engine.py`、`backend/app/utils/datetime.py`(未建,僅受限)
- **問題**:`05-timezone.md` 規定時間取得統一寫 `app/utils/datetime.py` 並 export `now_tw()` / `to_tw(dt)`,各層 import 同一處、禁各 service 自寫;task-006 需要 now_tw 但 `app/utils/*` 不在 affected_files 白名單,依 multi-agent 硬約束不得新建
- **根因**:task 拆解時未把「首個需要時間函式的 task 應建立 `app/utils/datetime.py`」的規範連動檔納入任何 task 的 affected_files(與 §1 / §4 同型:規範義務與檔案白名單互斥)
- **修正**:`now_tw()` 暫實作於 `backend/app/etl/engine.py` 並由 `app.etl` re-export,行為完全對齊規範(aware,Asia/Taipei);後續 task(005 / 007)需要時間函式時 import `app.etl.now_tw`,勿另寫
- **規範參照**:`docs/Design-Base/00-overview/05-timezone.md § 後端 datetime 實踐`
- **後續**:收口時把 now_tw 搬至 `app/utils/datetime.py` 並改各處 import(或由首個 affected_files 含該路徑的 task 順手搬);reflect 候選 — 拆 task 時共用 util 檔應指派唯一 owner task

> 收口(2026-07-06):已完成 — 新建 `app/utils/datetime.py`(`now_tw` / `to_tw` / `db_now`),engine.py / etl_config_repo.py / schedule_repo.py 三處重複實作收斂改 import 同一處;`app.etl` 保留 re-export 相容舊 import。

## §6 — 本機 Windows 無 tzdata,`ZoneInfo("Asia/Taipei")` 直接 raise,fallback 固定 +8

- **時間**:2026-07-03T17:40+08:00
- **commit / PR**:task-006 commit(ETL 執行核心)
- **影響檔案**:`backend/app/etl/engine.py`、`backend/pyproject.toml`(未改,僅受限)
- **問題**:`05-timezone.md` 範式為 `datetime.now(ZoneInfo("Asia/Taipei"))`,但 Windows 無系統 IANA tz 資料庫且 `tzdata` 套件未列依賴,實跑即 `ZoneInfoNotFoundError`,測試在本機必紅
- **根因**:依賴鎖版(task-001)未涵蓋 `tzdata`(Linux container 有系統 tzdata 所以未被發現;跨平台差異未納入鎖版考量),而 task-006 依規不得動 `pyproject.toml`
- **修正**:`engine.py` 以 try/except fallback:`ZoneInfo("Asia/Taipei")` 失敗時改 `timezone(timedelta(hours=8), "Asia/Taipei")`;台灣無 DST,行為等價,容器內(有 tzdata)仍走 ZoneInfo 正軌
- **規範參照**:`docs/Design-Base/00-overview/05-timezone.md § 後端 datetime 實踐`
- **後續**:收口時評估把 `tzdata==2025.*` 補進 pyproject(僅 task-001 / 收口可動),屆時 fallback 可保留為防禦;task-012 Dockerfile 須依規安裝系統 tzdata + `TZ=Asia/Taipei`

> 收口(2026-07-06):已完成 — pyproject 鎖 `tzdata==2026.2`(uv.lock 同步;IANA 版本序已至 2026.x,原估 2025.* 過時),ZoneInfo fallback 保留為防禦。

## §7 — task-003 白名單與規範連動檔互斥:client 子目錄 / schema 位置 / lifespan 建立均無法照規範落檔

- **時間**:2026-07-03T17:55+08:00
- **commit / PR**:task-003 commit(DF-SSO 後端整合)
- **影響檔案**:`backend/app/clients/df_sso.py`、`backend/app/api/v1/sso.py`、`backend/app/schemas/`(未動,僅受限)、`backend/app/main.py`(未動,僅受限)、`backend/app/repositories/user_repo.py`(未動,僅受限)
- **問題**:task-003 落檔時三處無法對齊 Design-Base:(1) `90-third-party-service/00-overview.md` 規定第三方 client 走 `app/clients/<service>/` 子目錄(client/schemas/errors/README 分檔),但 task 檔範圍要點與 affected_files 均明示單檔 `app/clients/df_sso.py`;(2) SSO 回應 schema 依慣例應落 `app/schemas/`,但該目錄無任何檔案在白名單 → `SsoMeResponse` 等暫定義於 `api/v1/sso.py`;(3) `01-client-design.md` 規定 httpx client 於 FastAPI lifespan 建立 + dispose,但 `main.py` 不在白名單 → 改為 `get_df_sso_client()` 惰性單例(連線池仍共用,無每 request 開新 client)。另 `user_repo.py` 不在白名單,`get_by_sso_subject` 查詢暫落 `sso_service.py`
- **根因**:與 §1 / §4 / §5 同型 — 拆 task 時 affected_files 只列「功能主檔」,未把規範要求的結構連動檔(client 子目錄四檔、schemas 檔、main.py lifespan、repo 擴充)納入白名單;且規範優先序(Design-Base > Tasks)與 multi-agent 白名單硬約束在此互斥,worker 依約束取白名單
- **修正**:單檔 client 內部仍按規範分區(錯誤類 / schema / client / 單例),行為契約(timeout ≤8s / no-store / 錯誤轉 AppError / 連線池單例)全數對齊;偏離處均在程式碼註解標記並指向本條
- **規範參照**:`docs/Design-Base/90-third-party-service/00-overview.md § 集中位置`、`01-client-design.md § httpx.AsyncClient(lifespan 建立)`
- **後續**:收口時可將 `df_sso.py` 升格為 `clients/df_sso/` 子目錄、schema 移 `app/schemas/sso.py`、client 建立/釋放掛進 lifespan(`aclose` 已備);reflect 候選 — 拆 task 時第三方串接應自動把 client 子目錄與 main.py lifespan 列入 affected_files

> 收口(2026-07-06):未搬移(非必修)— 單檔 client 行為契約已對齊規範,升格 `clients/df_sso/` 子目錄 / schema 移檔 / lifespan 掛載列下版本候選。

## §8 — DF-SSO 契約 #1 未全面落地:通用守衛(deps.get_current_user)不辨 provider,back-channel 撤銷為 process-local

- **時間**:2026-07-03T17:55+08:00
- **commit / PR**:task-003 commit(DF-SSO 後端整合)
- **影響檔案**:`backend/app/api/deps.py`(未動,僅受限)、`backend/app/api/v1/auth.py`(未動,僅受限)、`backend/app/services/sso_service.py`
- **問題**:模式 B 契約要求守衛依 JWT `provider` 分流(`sso` → 每次回源中央,`local` → 本地驗證)。本 task 的 `/api/v1/sso/me` 已完整落地(即時回源、中央 401 刪 cookie、不可達 502 不刪);但 task-002 建立的通用守衛 `deps.get_current_user`(供 require_admin / 後續 004/005 API 使用)只驗本地 JWT + 查 users 表,SSO 來源 token 走這些端點時不會回源中央 — 中央 session 被撤銷後,SSO 使用者對一般 API 的存取要到 JWT 過期(≤86400s)或前端下次打 `/sso/me` 才失效。另 back-channel logout 的撤銷註記(`sso_service._sso_revoked_at`)為 process-local dict:多 worker / 重啟即遺失,且 `deps.py` 不在白名單無法讓通用守衛讀取
- **根因**:拆解時把「雙軌守衛分流」隱含歸給 task-003,但守衛檔 `api/deps.py` 只列在 task-002 的 affected_files(002 實作時尚無 provider 概念);且本版無共享 session store(redis 屬 task-007/012),契約「清 session 即失效」缺少跨 process 載體
- **修正**:本 task 範圍內以「SSO 端點即時回源 + JWT 效期對齊 cookie 86400s + process-local 撤銷註記」落地;偏離處於 `sso_service.py` 註解標記
- **規範參照**:`docs/Design-Base/90-third-party-service/08-df-sso.md § 4 條硬性契約 #1 / 兩種整合模式(模式 B)`
- **後續**:task-004/005 掛權限或收口時,`deps.get_current_user` 應補 provider 分流(`provider=="sso"` → 回源中央或查共享撤銷表);task-007/012 redis 就緒後,撤銷註記可遷至 redis 使多 worker 一致;reflect 候選 — 雙軌登入專案應指定「守衛分流」的唯一 owner task

> 收口(2026-07-06):已完成 — `deps.get_current_user` 補 provider 分流(`sso` → 撤銷註記檢查 + 每次回源中央;中央 401 → 401、不可達 → 502 不視為登出),`tests/test_sso.py` 增 5 個分流測試。撤銷註記仍為 process-local(單 API 容器下 back-channel 已生效);遷共享 store(redis)列下版本候選。

## §9 — Dockerfile 版本鎖定線被推翻:python 3.14.1-slim / uv 0.11.20(規範表為 3.14.0 / 0.5.18)

- **時間**:2026-07-03T18:40+08:00
- **commit / PR**:task-012 commit(Docker 化)
- **影響檔案**:`backend/Dockerfile`、`docs/Design-Base/00-overview/01-versions.md`(未改,僅受限)、`docs/Design-Base/06-Coolify-CD/02-dockerfile-backend.md`(未改,僅受限)
- **問題**:`02-dockerfile-backend.md` 模板鎖 `python:3.14.0-slim` + `ghcr.io/astral-sh/uv:0.5.18`,但 task-001 產出的 `pyproject.toml` 鎖 `requires-python == 3.14.1.*`、`uv.lock` 為 revision 3 格式(需 uv >= 0.8 才能解析);照規範版本 build 必失敗(python 版本不符 requires-python + uv 0.5.18 讀不了 lock)
- **根因**:與 §1 同型 — `01-versions.md` / Dockerfile 模板的版本表未隨 task-001 實際鎖定線同步,且該兩檔屬 Design-Base 不在任何 task 白名單;Sources of Truth(pyproject / uv.lock)與規範表分歧時,build 只能跟 lock 走
- **修正**:`backend/Dockerfile` 鎖 `python:3.14.1-slim`(對齊 requires-python)與 `ghcr.io/astral-sh/uv:0.11.20`(對齊本機產 lock 的 uv 版本,鎖到 patch、禁 latest);其餘(multi-stage / 非 root / tzdata+curl / TZ / HEALTHCHECK / 精準 COPY)完全按模板
- **規範參照**:`docs/Design-Base/06-Coolify-CD/02-dockerfile-backend.md § 規則(Python image tag / uv image tag)`、`docs/Design-Base/00-overview/01-versions.md § 鎖定線`
- **後續**:收口時把 `01-versions.md`(Python 3.14.1 / uv 0.11.x)與 `02-dockerfile-backend.md` 模板版本改為以 pyproject / uv.lock 為準;reflect 候選 — 規範版本表改引用 Sources of Truth 而非硬編版號

> 收口(2026-07-06):已完成 — 兩檔版本同步實際值(python 3.14.1-slim / uv 0.11.20)並補「image tag 對齊 Sources of Truth」規則。

## §10 — `(main)/page.tsx` 與既有根 `app/page.tsx` 同路由衝突,根 page 須刪除但不在白名單

- **時間**:2026-07-03T21:30+08:00
- **commit / PR**:task-009 commit(前端登入頁 + 後台佈局殼)
- **影響檔案**:`frontend/src/app/page.tsx`(刪除)、`frontend/src/app/(main)/page.tsx`
- **問題**:task-009 affected_files 指定新增 `app/(main)/page.tsx`(route group 解析為 `/`),但骨架既有 `app/page.tsx` 同樣解析為 `/`,兩者並存 Next.js build 直接失敗(parallel pages resolve to the same path);根 page 的刪除未列入任何 task 的 affected_files
- **根因**:拆解時以「新增檔案」視角列白名單,未盤點 route group 與既有骨架頁面的路由重疊 — `(main)` 是 URL 不可見的分組,`(main)/page.tsx` 必然頂替根 `/`
- **修正**:刪除 `frontend/src/app/page.tsx`(骨架佔位頁,無業務內容),`/` 由 `(main)/page.tsx`(總覽)接手;build 全綠(task-009 commit)
- **規範參照**:—(非違規;拆解白名單缺口,與 §1/§4/§5/§7 同型)
- **後續**:reflect 候選 — 拆 task 時新增 route group 頁面應同步盤點被頂替的既有頁面並列入 affected_files

## §11 — 前端 i18n 規範(UI 文字一律 i18n key)於本版被推翻:骨架無 i18n 基建且禁增依賴

- **時間**:2026-07-03T21:30+08:00
- **commit / PR**:task-009 commit
- **影響檔案**:`frontend/src/app/login/page.tsx`、`frontend/src/app/(main)/layout.tsx`、`frontend/src/app/(main)/page.tsx`、`frontend/src/app/error.tsx`
- **問題**:`02-frontend/00-overview.md` 規定「UI 文字一律 i18n key;字典依模組分檔」,但 frontend 骨架無任何 i18n 基建(無字典目錄、package.json 無 i18n 套件),而依賴鎖版僅 task-001 可動(且 001 只管 backend)、字典檔亦不在 task-009 白名單
- **根因**:v1.1.0 拆解未包含 i18n 基建 task;規範義務(i18n)與 multi-agent 白名單 / 禁增依賴硬約束互斥(與 §1 同型),且本後台目前僅 zh-TW 單語系
- **修正**:task-009 前端 UI 文字以繁中字串常數落檔(集中於元件頂部 const,非散落 JSX),未引入 i18n key;`global-error` 硬編碼本屬規範允許例外
- **規範參照**:`docs/Design-Base/02-frontend/00-overview.md § i18n(永遠遵守)`(本版情境被推翻)
- **後續**:010/011 沿用同做法保持一致;若未來需多語系,另開 task 建 i18n 基建並回收字串;reflect 候選 — i18n 規範補「單語系內部工具可豁免」條款或拆解時強制配 i18n 基建 task

## §12 — SSO 按鈕所需 `NEXT_PUBLIC_SSO_URL` / `NEXT_PUBLIC_SSO_APP_ID` 的 env 登記檔不在白名單

- **時間**:2026-07-03T21:30+08:00
- **commit / PR**:task-009 commit
- **影響檔案**:`frontend/.env.local.example`(白名單外,已補)、`frontend/src/app/login/page.tsx`
- **問題**:task 範圍要點寫「SSO 按鈕導向 backend SSO 端點(task-003)」,但 task-003 僅有 callback / me / logout / back-channel 四端點,無 authorize 入口 — DF-SSO 契約的登入起點是中央 `<SSO_URL>/api/auth/sso/authorize`,前端組此 URL 需要可公開 env `NEXT_PUBLIC_SSO_URL` / `NEXT_PUBLIC_SSO_APP_ID`,而 env 登記檔(`frontend/.env.local.example`)不在 task-009 affected_files
- **根因**:拆解時誤把「SSO 登入入口」歸為 backend 端點,未對照 08-df-sso 契約(authorize 在中央,前端整頁跳轉);連帶漏列 env 登記檔(與 §1/§4 同型白名單缺口)
- **修正**:登入頁 SSO 按鈕組 `${NEXT_PUBLIC_SSO_URL}/api/auth/sso/authorize?client_id=...&redirect_uri=<backend>/sso/callback` 整頁跳轉;`frontend/.env.local.example` 補兩個可公開 env(白名單外最小異動);env 未設定時按鈕 disabled 並顯示提示,不影響本地帳密軌
- **規範參照**:`docs/Design-Base/02-frontend/03-env-and-auth.md § 環境變數前綴(所有 env 須登記於 .env.example)`、`docs/Design-Base/90-third-party-service/08-df-sso.md § env`
- **後續**:task-012 / 收口時評估是否把 `NEXT_PUBLIC_SSO_URL` / `NEXT_PUBLIC_SSO_APP_ID` 同步進根 `.env.example`(前端部署 build args);正式環境部署時由 user 填實際值

> 收口(2026-07-06):已完成 — 根 `.env.example` 補 `NEXT_PUBLIC_SSO_URL` / `NEXT_PUBLIC_SSO_APP_ID` 登記(placeholder);正式值與前端 image build args 由 user 部署時處理。

## §13 — dashboard 401 的 silent re-auth 未落地:`/auth/me` 不暴露 provider,前端無從分流

- **時間**:2026-07-03T21:30+08:00
- **commit / PR**:task-009 commit
- **影響檔案**:`frontend/src/app/(main)/layout.tsx`、`frontend/src/lib/auth/useAuth.ts`、`backend/app/schemas/auth.py`(未動,僅受限)
- **問題**:08-df-sso 規定 dashboard 工作中 401 禁直接踢登入頁,模式 B 應先 `/me` 取 `provider` 分流(sso → silent re-auth / local → 本地登入頁);但通用 `/api/v1/auth/me` 的 `UserResponse` 只有 uid/username/role,無 `provider` 欄位,前端拿不到分流依據(token 為 httpOnly,前端依規不可解析)
- **根因**:task-002 定義 `UserResponse` 時尚無雙軌概念、task-003 只補了 SSO 側 `/sso/me`(有 provider)但通用 me 未回補;task-009 又不得動 backend schema(白名單),silent re-auth 的攔截器缺前置資訊 — 與 §8(守衛不辨 provider)同根源的前端面
- **修正**:本 task 以「(main) layout 於 /me 401 時 `router.replace('/login')`」落地(登入頁顯示雙軌按鈕,不自動跳 authorize,無導向迴圈);SSO 使用者中央 session 仍在時,回登入頁按一次 SSO 按鈕即無感重登,體感接近 silent re-auth
- **規範參照**:`docs/Design-Base/90-third-party-service/08-df-sso.md § Silent Re-Auth / 不要做(dashboard 401 直接踢登入頁)`(部分未落地)
- **後續**:收口或後續版本:`UserResponse` 增 `provider` 欄(或後端設非機密 `last_login_provider` hint cookie)後,前端補 401 攔截器(去重 / 重試上限 / 保留現場);見 §8

> 收口(2026-07-06):已完成 — `UserResponse` 增 `provider` 欄(守衛判定後掛 request.state);前端 401 攔截器落地(`lib/auth/sso.ts`:去重 flag / sessionStorage 重試上限 2 / 保留現場並由 dashboard 進入點復原 / hint 為 sso 且 env 有值 → 整頁跳中央 authorize,否則回登入頁),provider hint 存 localStorage。

## §14 — Next 16 `middleware.ts` 檔名慣例已被標記 deprecated(改名 `proxy.ts`),task 白名單鎖定舊檔名

- **時間**:2026-07-03T21:30+08:00
- **commit / PR**:task-009 commit
- **影響檔案**:`frontend/src/middleware.ts`
- **問題**:task-009 affected_files 指定 `frontend/src/middleware.ts`,build 可過但 Next 16.2.7 輸出警告「The "middleware" file convention is deprecated. Please use "proxy" instead」;Next 17 起舊檔名將失效
- **根因**:拆解時沿用 Next 15 以前的檔名慣例,未對照鎖定版本(Next 16)的 breaking-change 清單;白名單鎖死檔名使 worker 不得自行改名
- **修正**:依 task 白名單維持 `middleware.ts`(功能正常,僅 deprecation 警告);auth guard 邏輯本身與檔名無關,改名成本為零風險搬移
- **規範參照**:—(非違規;框架版本演進 vs 拆解檔名)
- **後續**:收口或下版本把 `src/middleware.ts` 改名 `src/proxy.ts`(export 同步改 `proxy`);升 Next 17 前必須完成

> 收口(2026-07-06):已完成 — 改名 `src/proxy.ts`、export 改 `proxy`(matcher 與守衛邏輯不變);build 顯示 `ƒ Proxy (Middleware)`,deprecation 警告消失。

## §15 — 手動觸發「回傳 run uid」在佇列模式(redis broker)下無法保證,回應改為 nullable

- **時間**:2026-07-03T17:42+08:00
- **commit / PR**:task-005 commit(排程 / 執行紀錄 / 手動觸發 API)
- **影響檔案**:`backend/app/services/schedule_service.py`、`backend/app/schemas/run.py`、`backend/app/worker/tasks.py`(未改,僅受限)
- **問題**:task-005 範圍要點要求手動觸發「回傳 run uid」,但 task-007 的 `run_etl` task 於 **worker 端**才建立 `etl_runs` 紀錄(`store.create_run` 在 task 內);production 佇列模式(redis ListQueueBroker)下 API enqueue 當下 run 尚不存在,無法取得 run uid,而 `run_etl` 簽章(`trigger_type / schedule_pid / etl_table_pid`)不收外部預建的 run 識別,`app/worker/tasks.py` 又不在 task-005 白名單不得修改
- **根因**:拆解時 task-005(回傳 run uid)與 task-007(run 由 worker 建立)的介面契約未對齊 — enqueue 型架構下「觸發即得 run uid」需要「API 預建 run + task 收 run 識別」的協作設計,兩 task 各自實作時無人擁有該跨檔契約
- **修正**:`RunTriggerResponse` 定為 `{task_id: str, run_uid: UUID | null}`;就地執行 broker(pytest 的 InMemoryBroker `await_inplace`)已同步跑完 → 以結果 `run_pid` 換 uid 回傳(測試可驗全欄位),redis 佇列模式回 `null`,前端(task-011)應以 run 清單(最新在前)查看觸發結果
- **規範參照**:—(非違規;跨 task 介面契約缺口)
- **後續**:若 production 需要「觸發即得 run uid」,收口或下版本把 `run_etl` 改為可收 API 預建之 run 識別(uid),API 先建 `etl_runs(status=pending)` 再 enqueue;task-011 前端實作時注意 `run_uid` 可能為 null;reflect 候選 — 拆 task 時跨 task 的 API ↔ worker 介面契約應指定唯一 owner

## §16 — 前端 ApiEnvelope / unwrap / 錯誤 detail 萃取跨檔重複,共用型別檔無 owner task

- **時間**:2026-07-03T17:52+08:00
- **commit / PR**:task-010 commit(前端 Data Table 管理頁)
- **影響檔案**:`frontend/src/lib/api/etlConfigApi.ts`、`frontend/src/lib/api/authApi.ts`(未改,僅受限)、`frontend/src/app/login/page.tsx`(未改,僅受限)
- **問題**:`05-components.md` 規定跨檔 ≥ 2 次使用的 Type / utility 必抽共用檔(如 `types/api.ts` / `utils/`),但後端統一回應信封 `ApiEnvelope<T>` 與 `unwrap()` 已在 task-009 的 `authApi.ts` 定義(未 export),RTK Query 錯誤物件的 detail 萃取(`extractDetail`)亦 inline 於 `login/page.tsx`;task-010 需要同型別與同邏輯,而 `types/` / `utils/` 新檔與 task-009 檔案均不在 task-010 affected_files 白名單
- **根因**:與 §1 / §4 / §5 / §7 同型 — 拆 task 時前端「跨 API 檔共用單元」(回應信封型別、unwrap、錯誤萃取)未指派唯一 owner task,規範義務(reuse 必抽)與檔案白名單互斥
- **修正**:task-010 在 `etlConfigApi.ts` 內重複定義 `ApiEnvelope` / `unwrap`,並將錯誤萃取以 `extractApiErrorDetail(error, fallback)` 具名 export(單一定義供 tables 清單 / 明細 / MappingEditor 三處共用);task-011 需要時 import `etlConfigApi.extractApiErrorDetail`,勿再自寫
- **規範參照**:`docs/Design-Base/02-frontend/05-components.md § Reuse 規則(Type / utility 跨檔 ≥ 2 必抽)`
- **後續**:收口時把 `ApiEnvelope` / `unwrap` 抽至 `frontend/src/types/api.ts`(或 `lib/api/envelope.ts`)、`extractApiErrorDetail` 抽至 `utils/`,並改 `authApi.ts` / `login/page.tsx` / `etlConfigApi.ts` 三處 import;reflect 候選 — 拆 task 時共用型別 / util 檔應指派唯一 owner task(與 §5 後端同型)

> 收口(2026-07-06):已完成 — `ApiEnvelope` / `unwrap` 抽 `types/api.ts`、`extractApiErrorDetail` 抽 `utils/apiError.ts`;authApi / etlConfigApi / scheduleApi / runApi 與七處使用端全改 import 單一定義,login 頁 inline `extractDetail` 移除。

## §17 — task-011 跨頁共用 UI 單元(Pagination / StatusBadge / formatNullableDateTime)無 components/common 白名單,暫集中於 RunLogTable.tsx

- **時間**:2026-07-03T18:10+08:00
- **commit / PR**:task-011 commit(前端排程管理 + 執行紀錄頁)
- **影響檔案**:`frontend/src/components/runs/RunLogTable.tsx`、`frontend/src/components/common/`(未建,僅受限)、`frontend/src/utils/datetime.ts`(未改,僅受限)
- **問題**:`05-components.md` 規定 ≥ 2 處使用的 component / utility 必抽共用檔(`components/common/` / `utils/`),task-011 的三頁(schedules / runs / runs/[uid])共用分頁列、狀態 badge、觸發方式字樣與可 null 時間格式化;但 affected_files 白名單僅含 `components/runs/RunLogTable.tsx`,無 `components/common/` 或 `utils/` 路徑可落檔
- **根因**:與 §16 同型 — 拆 task 時未預留共用元件目錄的 owner;白名單以「頁面 + 單一元件檔」視角列檔,跨頁共用單元無處可放
- **修正**:`Pagination` / `StatusBadge` / `TRIGGER_TYPE_LABELS` / `formatNullableDateTime` 具名 export 於 `components/runs/RunLogTable.tsx`(檔頭註解標記),三頁 import 同一處、無 inline 重複;`ApiEnvelope` / `unwrap` 依 §16 指示於 `scheduleApi.ts` 定義一次並供 `runApi.ts` import,錯誤萃取沿用 `etlConfigApi.extractApiErrorDetail` 未再自寫
- **規範參照**:`docs/Design-Base/02-frontend/05-components.md § Reuse 規則 / 命名與位置`
- **後續**:收口時把上述單元搬至 `components/common/Pagination.tsx` / `components/common/StatusBadge.tsx` 與 `utils/datetime.ts`(formatNullableDateTime),並改三頁 import;與 §16 合併處理;reflect 候選同 §16

> 收口(2026-07-06):已完成 — `Pagination` / `StatusBadge` 抽 `components/common/`、`TRIGGER_TYPE_LABELS` 抽 `constants/labels.ts`、`formatNullableDateTime` 併 `utils/datetime.ts`;RunLogTable 具名 export 與暫置註解移除,三頁 import 改指新位置。

## §18 — etl_runs.created_at 以 UTC wall-clock 寫入,與 started_at(+8)混用,前端顯示相差 8 小時

- **時間**:2026-07-03T18:10+08:00
- **commit / PR**:—(task-011 手測時發現;非本 task 引入)
- **影響檔案**:`backend/app/models/*`(base 欄位 server_default,未改,僅受限)、`backend/app/core/db.py`(未改,僅受限)、`docker-compose.yml`(未改,僅受限)
- **問題**:手測手動觸發後,同一瞬間建立的 run 其 `created_at=2026-07-03T09:59:34`(UTC wall-clock、無 tz)而 `started_at=2026-07-03T17:59:34`(+8 wall-clock、無 tz),秒內毫秒值幾乎相同證實為同一時刻的兩種時區寫法;前端 `formatDateTime` 統一以 Asia/Taipei 呈現,`created_at` 類欄位(DB server_default 產生)顯示會早 8 小時,`started_at` / `finished_at` / `updated_at`(Python `now_tw()` 寫入)則正確
- **根因**:`05-timezone.md` 要求 DB session timezone 對齊 Asia/Taipei(`SET TIME ZONE` 或 connection string options),但 compose 只設了 container `TZ=Asia/Taipei`,postgres 服務的 session timezone 仍為預設 UTC → `server_default=func.now()` 類欄位寫 UTC;Python 側寫入的欄位走 `now_tw()`(+8),兩種來源混用且序列化皆為 naive 字串,違反「全棧一致」與「禁裸時戳無 tz」
- **修正**:本 task(前端白名單)無法修;前端不做自行時區轉換(依 `04-datetime.md` 禁雙偏移),顯示以後端字串為準,偏差留待後端修正
- **規範參照**:`docs/Design-Base/00-overview/05-timezone.md § 資料庫 / Log 時戳格式`
- **後續**:收口時擇一:(1) DB 連線加 `?options=-c%20TimeZone%3DAsia/Taipei` 或 postgres 設 `timezone=Asia/Taipei`;(2) models 的 created_at server_default 改由 Python `now_tw()` 統一寫入;並評估 API 序列化補 `+08:00` offset(對齊 log 時戳規範)

> 收口(2026-07-06):已完成 — 採方案 (1):`core/db.py` engine 加 `connect_args={"server_settings": {"timezone": "Asia/Taipei"}}`,server_default 欄位改寫 +8 wall-clock;compose 實測手動觸發 run 之 `created_at` 與 `started_at` 同刻(09:24:03.227 / 09:24:03.236)。API 序列化補 offset 未做(前端顯示一致無雙偏移),列下版本候選。

## §19 — ListQueueBroker 閒置時每 5 秒 TimeoutError,worker 子行程反覆 reload(redis-py 8 預設 socket_timeout 所致)

- **時間**:2026-07-03T18:55+08:00
- **commit / PR**:task-012 commit(Docker 化;現象於 compose 實跑驗收時發現)
- **影響檔案**:`backend/app/worker/broker.py`(未改,僅受限)、`backend/uv.lock`(未改,僅受限)
- **問題**:`docker compose up` 後 worker 容器 healthy 且可正常消費任務(實測 kiq run_etl → etl_runs 寫入 success),但閒置時 log 每 ~5 秒出現 `redis.exceptions.TimeoutError: Timeout reading from redis:6379`,taskiq process-manager 隨即 reload 子行程(worker-N is dead → restarted),形成無止盡的子行程重啟迴圈;重啟間隙(~1 秒)入列的任務會多等數秒才被消費
- **根因**:task-001 鎖定的 redis-py 8.0.1 將 `DEFAULT_SOCKET_TIMEOUT` 從 None 改為 5 秒(read timeout);taskiq-redis 1.2.3 `ListQueueBroker.listen()` 以無限期 `BRPOP` 阻塞等待、且只 catch `ConnectionError` 不 catch `TimeoutError` → 佇列閒置超過 5 秒必炸並殺死 receiver。task-007 開發時以 InMemoryBroker 跑測試,redis 實連路徑未被驗證;修法在 `broker.py`(如 `ListQueueBroker(url=..., socket_timeout=None)` 傳入 connection_kwargs,或改用 RedisStreamBroker),但該檔屬 task-007 白名單,task-012 依 multi-agent 硬約束不得修改;REDIS_URL query 參數無法表達 `socket_timeout=None`(from_url 只收 float),env 層無解
- **修正**:task-012 範圍內未修(僅白名單三檔);compose 服務層以 restart 策略 + healthcheck 保底,功能可用。待 task-007 owner / 收口在 `broker.py` 補 `socket_timeout=None`(一行)後迴圈即消失
- **規範參照**:—(非違規;鎖版組合相容性 bug,與 §3 passlib/bcrypt 同型)
- **後續**:收口(或 task-005 動 worker 相關檔時)在 `create_broker()` 對 `ListQueueBroker` 傳 `socket_timeout=None` 並實連 redis 驗證;reflect 候選 — 依賴鎖版後應對「間接依賴 major 升版」跑一次實連煙霧測試,InMemory 測試替身蓋不到此類問題。另註:task-005 的 affected_files 不含 `app/worker/*`,本條仍待收口處理

> 收口(2026-07-06):已完成 — `create_broker()` 對 `ListQueueBroker` 傳 `socket_timeout=None`;compose 實連 redis 驗證:worker 閒置 7+ 分鐘 log 無任何 TimeoutError / reload(修正前每 ~5 秒一次),手動觸發任務消費正常。
