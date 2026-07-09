# Issue — Scan Project(2026-07-09 13:14 +08)

> focus=all;v1.4.0 六 task 收口後全域檢測(dev-v1.4/parallel-sync @ 7812bc9,已併 development)。
> 差異基準:`Issue-Scan-Project-260706093345.md`(2026-07-06,v1.1.0 收口後)。
> 掃描方式:三路子 agent(後端+DB / 前端 / ENV+GIT+DEP+SEC 組態)並行,主 agent 彙整。
> 已記錄於 `docs/Tasks/v1.4.0/fixed.md` 者視為已處理(§1 COMMENT 冒號 text() 誤判、§2 StatusBadge 折行)。

---

## 0. 與前次差異

上次 🟠6 🟡10 🔵10 ⚪2 → 本次 🟠2 🟡6 🔵11 ⚪2。**v1.2.0~v1.4.0 途中修掉了大半舊帳**:

### ✅ 已修(16 項)
| ID | 證據 |
| --- | --- |
| AD-002 datetime.ts 雙偏移 | `frontend/src/utils/datetime.ts:3-21` 已改純 regex 字串切割,無 `new Date()`+`Intl`;AutoRefreshControl 的 formatTime 路徑亦合規 |
| AD-003 TableList 複製品 | `components/tables/` 已不存在;分頁/badge 全走 `common/Pagination`、`common/StatusBadge` |
| AD-005 health DB fail 回 200 | `backend/app/api/v1/health.py:26-29` 改短連線探測,失敗回 503 |
| AD-006 ETL 整表載入記憶體 | `etl/mirror.py:328-330` server-side cursor `stream().partitions()` 分批;reader/writer 亦分批 |
| AD-007 get_settings 無快取 | `core/config.py:54` `@lru_cache` |
| R-PII-003 登入無 audit | `auth_service.py:37,45-51`(成敗皆記,失敗走獨立 session)、logout/sso_revoke 亦記;audit_logs 表+端點已建 |
| R-LOG-005 無 logging 組態 | `core/logging.py` setup_logging;main/worker/scheduler 皆初始化 |
| R-BE-016 etl 用 Any | 僅剩 `mirror.py` 4 處 DB row `Mapping[str, Any]` 合理用法 |
| R-ENV-004 localhost fallback | `lib/api/baseApi.ts:5-10` 改 fail-fast throw;`.env.example:13,95` 已登記 COMPOSE_PROJECT_NAME / NEXT_PUBLIC_API_URL |
| R-GIT-001 tsbuildinfo | 已不追蹤;`.gitignore:45` 已加 `*.tsbuildinfo` |
| R-DEP-002/003 前端版本 | `package.json:5` node pin `24.14.0`;next/react 與 `01-versions.md:13,38` 同步;Dockerfile 補 TZ+tzdata+HEALTHCHECK |
| AD-001 跨 host cookie 迴圈 | `core/config.py:41` COOKIE_DOMAIN env 化、`cookies.py:8-11` set/clear 帶 domain;前端已無 middleware 守衛(全 client 端),迴圈碼面不存在;production example 拓撲 `.zerozero.tw` |
| 舊🔵 store/provider 回傳型別 | `store.ts:21-27`、`provider.tsx:11-13` 已標 |
| 舊🔵 schemas 缺 description / 列舉散落 / sso response_model / health dict | `schemas/run.py:8-38` StrEnum+Field(description);`sso.py:96-98`;`health.py:13` HealthResponse |
| 舊🔵 passlib 殘留 | `pyproject.toml` 已移除,bcrypt 直呼直列 |
| 舊🔵 compose 檔名註解漂移 | `docker-compose-staging.yml` / `-production.yml` 現已實際存在 |

### ⏸ 仍在(7 項)
R-SEC-002(login rate limit)、R-SEC-003(安全 headers)、R-ENV-002(.gitignore 機密樣式)、R-TEST-001(前端零測試)、R-TEST-002/R-DEP-004(無 CI/依賴掃描排程)、舊🔵 422 無欄位級錯誤、舊🔵 缺 /api/v1/version — 詳見第 3 章。

### 🔄 變化(2 項)
- **AD-004 partial 死狀態**:config-ETL 路徑已下線(engine 無 run task),唯一活路徑 mirror;DB CHECK 已放寬允許 `partial`(`models/etl_run.py:40,78`)但 `worker/tasks.py:333` 收尾仍 `failed if failed else success` — 燈號接線仍缺,且如今 schema/dashboard 說明又不列 partial,三方不一致(併入本次 🔵-1)。
- **R-DEP-003 PostgreSQL 版本治理**:`01-versions.md:14` 鎖定線已改 18.x(版本爭議解),但三份 compose 仍直寫 `postgres:18-alpine`、`POSTGRES_VERSION` 為死變數(降級為本次 🟡-3)。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-07-09 13:14 (UTC+8) |
| 範圍 | backend / frontend / 根層組態(3×compose、5×.env*.example、.gitignore、lock)/ docs(第 7 章) |
| 嚴重度統計 | 🔴 0 🟠 2 🟡 6 🔵 11 ⚪ 2 |
| 結論 | **無 Critical,舊帳大幅清償**(16 項已修,含全部部署阻斷級:cookie 迴圈、health 200、localhost fallback)。v1.2~v1.4 新增碼品質高:RBAC 每端點 require_admin 無漏網、v1.4 併發模型(Lock 序列化 session、計數回傳收斂)驗證正確、migration 全新 revision、DDL 白名單合規、輪詢皆未聚焦暫停。剩餘 🟠 僅 login rate limit 與安全 headers 兩條 SEC 地板(上次即在);新發現以「殭屍 run 卡死 /runs/active 進度條」與「同表並發同步無防疊」兩條 🟡 最值得下版處理。 |

---

## 2. 專案摘要

- **目標**:ETL 管理後台 — 自動偵測鏡像同步(v1.2)+ 增量 skip(v1.3)+ 一表一排程(v1.3.1)+ 表級平行同步/全域進度條/RBAC admin-only/AWS 式自動刷新(v1.4.0)。
- **技術棧對照**:Next.js 16.2.7 + TS 5.9(strict、無 any)+ RTK Query ✓;FastAPI + SQLAlchemy 2 async + taskiq + redis ✓;PostgreSQL 18(鎖定線已同步 18.x)✓ — 版本表與實際**已對齊**(僅 redis python 客戶端未登記,見 🔵-5)。
- **Task 進度**:v1.4.0 6/6 done、API 冒煙通過(`/runs/active` 遞增、並行 running=2 生效);已併 development。
- **完成度**:後端測試 218 passed(真 DB);前端仍零測試、無 CI(唯二成片缺口)。

---

## 3. 詳細發現

### 🟠 High

### 🟠 [R-SEC-002] `/api/v1/auth/login` 無 rate limit(⏸ 自 2026-07-06)
- 檔案:`backend/app/api/v1/auth.py:43`
- 內容:本地帳密登入無任何節流;`INIT_ADMIN_USERNAME` 預設 `init-admin` 可猜,攻擊面=純密碼暴力。全 backend 無 limiter 相依。
- 修正:redis 已在棧內 — `deps.py` 加 redis 計數滑動視窗 dependency(IP+username,5 次/分鐘回 429)套在 login;或 Coolify 反代層設限並載明文件。
- 首次發現:2026-07-06

### 🟠 [R-SEC-003] 全棧缺安全 headers(⏸ 自 2026-07-06)
- 檔案:`backend/app/main.py:41-59`(middleware 僅 X-Request-ID)、`frontend/next.config.ts:1-9`
- 內容:X-Frame-Options / X-Content-Type-Options / Referrer-Policy 兩端皆缺;HSTS 屬部署層。
- 修正:`main.py` 既有 middleware 補三個 header;`next.config.ts` 加 `headers()` 同組;HSTS 記於部署文件交 Coolify 反代。
- 首次發現:2026-07-06

### 🟡 Medium

### 🟡 [AD-101] 殭屍 run 無啟動對帳 — worker 硬崩潰後 `/runs/active` 永遠卡住,SyncProgress 進度條不清除 🆕
- 檔案:`backend/app/worker/tasks.py:120,355`、`backend/app/repositories/run_repo.py:76`、`backend/app/etl/engine.py:156`
- 內容:`create_run` 先 commit `status=running`;worker 被 SIGKILL / OOM / 容器重啟時 `finish_run` 永不執行,`_mark_failed_if_dangling` 只攔程序內軟例外。`latest_running_run()` 從此永遠回這筆殭屍 → 新 `/runs/active` 端點卡死、全站進度條永不消失、儀表板「執行中」誤導,需人工改 DB。v1.4.0 進度條上線後此舊隱患**從潛在變成天天可見**。
- 白話:同步程序若被硬殺,系統會永遠以為它還在跑,進度條掛在畫面上下不來。
- 修正:worker 入口(`tasks.py` broker startup hook)啟動時把「超過閾值仍 running 的 run」補標 failed(附 note);或 `run_repo.latest_running_run` 加 `started_at > now - N 小時` 門檻雙保險。
- 首次發現:2026-07-09

### 🟡 [AD-102] 同表並發同步無防疊 — 排程與手動、或長同步跨 cron 週期會重複 enqueue 🆕
- 檔案:`backend/app/worker/scheduler.py:60-77`、`backend/app/etl/mirror.py:228,243`
- 內容:enqueue 前不檢查同 scope 是否已有執行中 run;兩輪對同一 target 表 TRUNCATE+INSERT(DB 表鎖序列化不致損毀,全量覆蓋冪等),但重複灌庫、來源 RDS 讀壓翻倍、signature 基準被雙寫。v1.4.0 併發度提高後,長同步跨週期的機率上升。
- 白話:同一張表可能被兩個同步任務前後腳搬兩次,白做工還加重來源資料庫負擔。
- 修正:`sync 服務`/`scheduler` enqueue 前查有無 running run 覆蓋同表(有則 skip + log);或 mirror 逐表取 Postgres advisory lock(`pg_try_advisory_lock(hash(schema.table))`)拿不到即跳過。
- 首次發現:2026-07-09

### 🟡 [R-DEP-003] 三份 compose 直寫 `postgres:18-alpine`,`POSTGRES_VERSION` 死變數(🔄 部分解)
- 檔案:`docker-compose.yml:133`、`docker-compose-staging.yml:182`、`docker-compose-production.yml:182`、`docs/Design-Base/00-overview/01-versions.md:25`
- 內容:鎖定線已同步 18.x(版本爭議解),但 `01-versions.md:25`「compose 用 `${POSTGRES_VERSION}` 引用,禁直寫」仍被三檔違反;五份 env 都登記了 `POSTGRES_VERSION` 卻無人消費,compose 註解還寫「版本由 .env 注入」與事實不符。
- 修正:三檔改 `image: postgres:${POSTGRES_VERSION}-alpine`,即刻讓既有登記生效。
- 首次發現:2026-07-06(形態變化)

### 🟡 [AD-103] production compose 常駐 adminer,DB 管理 UI 經 Coolify 反代外露 🆕
- 檔案:`docker-compose-production.yml:218-233`
- 內容:adminer 服務帶 `SERVICE_URL_ADMINER_8080`(反代即公開路由)且 `restart: unless-stopped` 常駐;註解自承「登入密碼=DB 密碼,正式環境須加 Basic Auth / IP 白名單或平時停用」但未落實。dev compose 反而沒有 adminer。
- 白話:正式站掛著一扇通往資料庫的網頁後門,鎖只有 DB 密碼一道。
- 修正:production 移除 adminer(需要時臨時起)或 Coolify 停用該服務;至少加 Basic Auth / IP 白名單。
- 首次發現:2026-07-09

### 🟡 [R-ENV-002] `.gitignore` 缺 `credentials*` / `*.key` / `*.pem`(⏸ 自 2026-07-06)
- 檔案:`.gitignore:18-24`、`docs/Design-Base/00-overview/02-secrets.md:27-35`
- 內容:規範必排清單三樣式仍缺(現無此類檔,屬預防護欄)。
- 修正:`.gitignore` 補三行。
- 首次發現:2026-07-06

### 🟡 [R-TEST-001] 前端零測試(⏸ 自 2026-07-06)
- 檔案:`frontend/package.json:6-12,20-31`
- 內容:無 test script、無框架;v1.4.0 後值得測的純邏輯又多了(輪詢開關、進度百分比防呆、RBAC 導向)。
- 修正:同前次建議 — jest/vitest + testing-library,先覆蓋純函式與守衛邏輯;或至少 `AGENTS.md` 註記缺口。
- 首次發現:2026-07-06

### 🔵 Low

### 🔵 [AD-104] `partial` 死狀態三方不一致(承 AD-004)
- 檔案:`backend/app/worker/tasks.py:333`、`models/etl_run.py:40,78`、`schemas/run.py:38`、`schemas/dashboard.py:17`
- 內容:CHECK 允許 partial、worker 從不產生、schema/dashboard 說明不列 — 三方各說各話。
- 修正:擇一 — 接線(`success if failed==0 else partial if success>0 else failed`)或 CHECK 移除該值統一文件。
- 首次發現:2026-07-06(形態變化)

### 🔵 [AD-105] `no-access/page.tsx` 巢狀 `<main>` landmark 🆕
- 檔案:`frontend/src/app/(main)/no-access/page.tsx:9`、`(main)/layout.tsx:107`
- 內容:layout 已有 `<main>`,此頁又渲一層(其餘頁用 `<section>`);讀屏跳 landmark 出現重複 main。
- 修正:改 `<div>`/`<section>`。
- 首次發現:2026-07-09

### 🔵 [AD-106] DatasetBrowser 概覽統計列與表格刷新節奏不一致 🆕
- 檔案:`frontend/src/components/datasets/DatasetBrowser.tsx:361,446-449`
- 內容:`SchemaSummaryBar` 的 summary query 無輪詢、且 `handleRefreshAll` 不含它 — 表格 30s 更新,上方「總表數/有資料/空表」不動。
- 修正:`refetch` 併入 `handleRefreshAll`,或給 summary 加 `pollingInterval: 30_000`。
- 首次發現:2026-07-09

### 🔵 [R-DEP-005] 三份 compose 皆無資源上限 🆕
- 檔案:`docker-compose*.yml`(全服務)
- 內容:env 註解多次提到 OOM 致 502,卻無任何 `deploy.resources.limits`;單服務暴衝可拖垮整機(v1.4 併發調高後 worker 記憶體峰值上升)。
- 修正:至少對 backend/worker/postgres 設 memory limit。
- 首次發現:2026-07-09

### 🔵 [R-DEP-002] `redis==8.0.1`(python 客戶端)未登記 `01-versions.md` 後端表 🆕
- 檔案:`backend/pyproject.toml:22`、`docs/Design-Base/00-overview/01-versions.md:53-74`
- 修正:後端表補一列。
- 首次發現:2026-07-09

### 🔵 [R-ENV-004] `.env.development.example` 埠與鍵雙漂移 🆕
- 檔案:`.env.development.example:7`
- 內容:`DATABASE_URL` 用 `localhost:5432`,但 compose 映射 `5435:5432`、根 example 用 5435 — 照抄連不上;且缺 `UVICORN_WORKERS`/`DB_POOL_SIZE`/`SYNC_CONCURRENCY`/`REDIS_URL` 等鍵,與其他四份不對齊。
- 修正:埠改 5435(或明註容器內用途)+ 補齊缺鍵。
- 首次發現:2026-07-09

### 🔵 [R-ENV-004] `.env.staging.example` 缺 `COMPOSE_PROJECT_NAME` 🆕
- 檔案:`.env.staging.example`(全檔)、`docker-compose-staging.yml:237-239`
- 內容:volume 命名依賴它,空值產生 `-postgres-data`;production 版有對照說明,staging 沒有。
- 修正:比照 production footer 補說明。
- 首次發現:2026-07-09

### 🔵 [R-SEC-004] fail-fast 未擋 `INIT_ADMIN_PASSWORD` 沿用 development 弱值 🆕
- 檔案:`backend/app/core/config.py:43-51`、`.env.development.example:12`
- 內容:護欄只比對 `JWT_SECRET_KEY`;staging/production 誤帶 `changeme-development` 系列弱密碼不會炸。
- 修正:`_fail_fast_in_prod` 迴圈追加 `INIT_ADMIN_PASSWORD` 弱值比對。
- 首次發現:2026-07-09

### 🔵 [05-exceptions] 422 無欄位級錯誤(⏸)
- 檔案:`backend/app/core/exceptions.py:36` — 同前次建議,`exc.errors()` 精簡入 `data`。
- 首次發現:2026-07-06

### 🔵 [R-LOG-006] 缺 `/api/v1/version`(⏸)
- 檔案:`backend/app/api/v1/__init__.py` — 同前次建議。
- 首次發現:2026-07-06

### 🔵 [R-TEST-002 / R-DEP-004] 無 CI;pip-audit / gitleaks 無自動觸發點(⏸)
- 檔案:`.github/`(不存在)、`backend/pyproject.toml:33`、`.gitleaks.toml`
- 修正:同前次 — 最小 workflow(後端 ruff/mypy/pytest;前端 lint/typecheck/build;pip-audit+gitleaks job)。
- 首次發現:2026-07-06

### ⚪ Info

### ⚪ [AD-107] config-ETL 死碼:`PostgresSourceReader` / `PostgresTargetWriter` 已無 live 呼叫端 🆕
- 檔案:`backend/app/etl/reader.py:53`、`etl/writer.py:41,52`
- 內容:v1.3.1 config-ETL 下線後僅剩匯出與 Protocol 註解引用,仍保有測試;留或清需一個明確決定,避免誤導維護者。
- 首次發現:2026-07-09

### ⚪ [07-testing] 測試建 schema 用 `create_all` 非 alembic(⏸)
- 檔案:`backend/tests/test_auth.py:93` 等 — 同前次,列資訊。
- 首次發現:2026-07-06

---

## 4. 修正優先序

### 立刻(部署前)
1. 🟡 AD-103 production adminer 收口(移除/停用/加鎖)— 外露面,10 分鐘
2. 🟠 R-SEC-002 login rate limit(redis 在棧內,成本低)
3. 🟡 AD-101 殭屍 run 對帳 — v1.4 進度條上線後此問題會直接呈現在所有人畫面上

### 本週
4. 🟠 R-SEC-003 安全 headers(兩端各 10 分鐘)
5. 🟡 AD-102 同表並發防疊(advisory lock 或 enqueue 前查)
6. 🟡 R-DEP-003 compose 改 `${POSTGRES_VERSION}`、🟡 R-ENV-002 .gitignore 三行(各 5 分鐘)
7. 🔵 R-SEC-004 fail-fast 補弱密碼比對、🔵 兩份 env example 對齊(development 埠/staging COMPOSE_PROJECT_NAME)

### 有空
8. 🟡 R-TEST-001 前端測試基建、🔵 CI 最小 workflow
9. 🔵 AD-104 partial 接線或移除、AD-105 巢狀 main、AD-106 概覽列刷新、R-DEP-005 資源上限、redis 登記、422 欄位級、/version
10. ⚪ AD-107 config-ETL 死碼去留決策

---

## 5. 已跳過類別 / 規則與脈絡衝突註記

- **組成偵測**:全類別存在,無跳過。
- **`etl/` v1.0.0 Glue 遺產**:config-ETL 下線後活路徑僅 mirror;reader/writer 列 AD-107 待決,內部品質不掃。
- **規則與脈絡衝突(沿前次,均不回報)**:request-scope 單交易=等效 transaction;單語系繁中 literal / 後端 detail 直顯(fixed.md §11);DDL 識別字白名單+quote_literal+`exec_driver_sql`(v1.4.0 fixed.md §1 已修 text() 誤判)為合規;SSO 每請求回源=契約要求;error_stack 回前端=產品需求;SyncProgress inline style width=動態值等效合規;`utils/cron.ts` 本地時間近似下次執行=註解已明示的內部工具取捨。
- **fixed.md 已載明不重複回報**:v1.4.0 §1(COMMENT 冒號)、§2(badge 折行);v1.1.0 §2/§7/§8/§11/§15/§18 同前次。

---

## 6. AD-xxx(規則外發現)

| ID | 嚴重度 | 摘要 |
| --- | --- | --- |
| AD-101 | 🟡 | 殭屍 run 無啟動對帳,/runs/active 卡死、進度條永不清除 🆕 |
| AD-102 | 🟡 | 同表並發同步無防疊,重複灌庫+RDS 讀壓翻倍 🆕 |
| AD-103 | 🟡 | production compose 常駐 adminer 外露 🆕 |
| AD-104 | 🔵 | partial 死狀態三方不一致(承 AD-004)|
| AD-105 | 🔵 | no-access 巢狀 `<main>` landmark 🆕 |
| AD-106 | 🔵 | DatasetBrowser 概覽列與表格刷新節奏不一致 🆕 |
| AD-107 | ⚪ | config-ETL reader/writer 死碼待決 🆕 |

**已巡視面向**(未發現額外問題者):v1.4 併發模型(db_lock 序列化共用 session ✓、計數回傳值收斂無 race ✓、單表失敗不中斷 ✓、skip 不進併發池 ✓)、RBAC 端點覆蓋(六 router 每端點 require_admin,401/403 語意分明 ✓)、`/runs/active` 路由順序(置於 `/{uid}` 前 ✓)、增量 signature 邊界(baseline None/counter 倒退皆保守視為變動 ✓)、migration 串接(v4/v5/v6 全新 revision、可重入 guard ✓)、前端輪詢紀律(全部 skipPollingIfUnfocused、run 結束停輪詢 ✓)、送出鈕 disable / 三態 / 無 any / 無原生 alert ✓、機密(git 歷史無 .env、tracked 檔無硬編機密、lock 全 pin ✓)。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **`01-versions.md:25` 與三份 compose 長期互相矛盾**(規範禁直寫 tag、實作全直寫且註解不實):要嘛 compose 改插值(建議,5 分鐘),要嘛規範放寬「官方 image 可直寫但須同步鎖定線」— 二擇一收斂,不要繼續兩邊都對不上。
2. **`03-backend/07-testing.md` 仍過薄**(前次第 4 點,未動):v1.4.0 多 worker 共用測試 DB 爭用問題(本次實戰中 task-001/003 併跑互踩)正是缺「測試 DB 隔離/序列化」規範的直接後果,建議 reflect 時一併補「多 agent 並行時測試 DB 使用約定」。
3. **多 agent 並行工作目錄約定缺失**:`01-propose/03-multi-agent-flow.md` 有認領/互鎖協議,但未禁止 worker 對共用工作樹执行 `git stash`/`checkout` 類全域操作 — 本次 v1.4.0 實戰 worker 誤 stash 清掉他人 WIP。建議升規(見 reflect)。
4. **`06-Coolify-CD/01-compose.md` 與 adminer 實務**:模板未規範「輔助管理服務(adminer 等)在 production 的允許條件」,導致 AD-103 無地板可循;建議補「production 禁常駐管理 UI,臨時使用須加鎖」條款。

---

> 本次 🔴 0 🟠 2 🟡 6 🔵 11 ⚪ 2;對比前次 16 項已修、7 項仍在、2 項變化、11 項新增(多為 🔵)。優先序第 1-3 項(adminer / rate limit / 殭屍 run)建議部署前處理。**需要我幫你修 High(🟠)與「立刻」清單嗎?**
