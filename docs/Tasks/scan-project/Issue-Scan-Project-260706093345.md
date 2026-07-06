# Issue — Scan Project(2026-07-06 09:33:45 +08)

> focus=all;v1.1.0 收口後全域檢測(工作樹為最新收口狀態,未 commit)。
> 無舊報告(`docs/Tasks/scan-project/` 僅 .gitkeep)→ 第 0 章「與前次差異」免寫。
> 已記錄於 `docs/Tasks/v1.1.0/fixed.md` 且有收口註記者視為已處理,不重複回報(見第 5 章)。

---

## 1. 總覽

| 項目 | 內容 |
| --- | --- |
| 掃描時間 | 2026-07-06 09:33 (UTC+8) |
| 範圍 | `backend/`(FastAPI + SQLAlchemy 2 async + taskiq)/ `frontend/`(Next.js 16 + TS strict + RTK Query)/ 根層(compose、.env*.example、.gitignore)/ `docs/`(僅第 7 章) |
| 嚴重度統計 | 🔴 0 🟠 6 🟡 10 🔵 10 ⚪ 2 |
| 結論 | **無 Critical**。核心功能面(認證雙軌、權限、軟刪除、SQL 安全、機密處理、時區收口)品質扎實,fixed.md §1–§19 收口項均已確認落地。主要問題集中在:**版本鎖定線與實際部署產物分歧**(PostgreSQL 18 / Node 24 / Next 16 均高於 `01-versions.md` 鎖定線且未記錄)、**跨網域部署時 cookie 守衛會形成導向迴圈**(production example 拓撲即中招)、以及登入端點缺 rate limit / 安全 headers 兩條 SEC 地板。前端另有日期工具違反 `04-datetime.md` 模板與收口抽共用後仍殘留的重複 UI。 |

---

## 2. 專案摘要

- **目標**:ETL 管理後台 — 自有 DB 驅動的表設定 / mapping(每欄必帶 Comment)、taskiq + redis 排程與手動觸發、逐表詳細執行 log(含 stack trace)、本地帳密 + DF-SSO 雙軌登入(admin / viewer 角色)。
- **技術棧對照**:
  | 層 | 規範 | 實際 | 對齊 |
  | --- | --- | --- | --- |
  | Frontend | Next.js(表列 15.x)+ TS strict + RTK Query + Tailwind v4 | Next 16.2.7 + TS 5.9.3(strict ✓、無 `any` ✓)+ RTK Query ✓ + Tailwind 4.2.4 ✓ | 版本表未同步(見 3.🟠-2) |
  | Backend | FastAPI + SQLAlchemy 2 async + Pydantic 2 + Alembic + uv | 全數符合;taskiq / redis 經 user 授權採用(propose 註記)| ✓ |
  | DB | PostgreSQL 17.x | compose 直寫 `postgres:18-alpine` | 偏離(見 3.🟠-1) |
- **目錄結構**:backend 分層 `api → services → repositories → models` + `clients/` + `worker/` + `etl/`(執行核心),層次乾淨無跨層;frontend `app/(main)` route group + `lib/api`(RTK Query 集中)+ `components/common`(收口後抽出)。
- **Task 進度**:v1.1.0 12/12 done + 收口完成(fixed.md §1–§19 處理完畢);待 user 人工部署。`etl/`(v1.0.0 Glue 版)已驗證凍結:`git log` 顯示 v1.1.0 期間無任何 commit 觸及、工作樹亦無異動 ✓。
- **完成度**:功能面完整、後端測試 12 檔(真 PostgreSQL 測試 DB ✓);前端無任何測試、無 CI(見詳細發現)。

---

## 3. 詳細發現

### 🟠 High

### 🟠 [AD-001] 前後端跨 host 部署時,httpOnly cookie 不會出現在前端網域 — proxy 守衛形成登入導向迴圈
- 檔案:`frontend/src/proxy.ts:21`、`backend/app/core/cookies.py:6-15`、`.env.production.example:39,43`
- 內容:JWT cookie 由後端 `set_cookie`(無 `domain` → host-only,只綁後端 host)。`proxy.ts` 以 `request.cookies.has('access_token')` 做第一層守衛 — 但該請求打的是**前端 host**。`.env.production.example` 的示範拓撲即為 `FRONTEND_URL=https://app.example.com` + `NEXT_PUBLIC_API_URL=https://api.example.com/api/v1`(不同 host):登入成功後 cookie 只存在 `api.example.com`,瀏覽 `app.example.com` 時 middleware 永遠看不到 cookie → 導向 `/login`;登入頁 `/me`(fetch 到 api,same-site 會帶 cookie)又判定已登入 → `router.replace('/')` → middleware 再踢回 `/login`,形成迴圈,**production 依範例配置整個後台不可進入**。本地(localhost 同 host、cookie 不分 port)與 compose 驗證不會踩到,故收口實測未發現。
- 白話:登入狀態的「門票」放在 api 網域,但「驗票口」開在 app 網域 — 只要前後端網域不同,驗票口永遠看不到票。
- 修正(擇一):(1) 部署時前後端走**同一網域路徑路由**(如 `app.example.com/api/*` → backend;Coolify 反向代理可設),並修改 `.env.production.example:43` 範例為同網域寫法 + 註記此限制;(2) `cookies.py:6` `set_cookie` 增 `domain=<父網域>` 由 env 注入(`COOKIE_DOMAIN=.example.com`),讓 cookie 覆蓋兩個子網域;(3) `proxy.ts` 改為不依賴 cookie(僅頁面層 `/me` 守衛)— 但會失去第一層 SSR 守衛。建議 (1)+文件註記,成本最低。
- 首次發現:2026-07-06

### 🟠 [R-DEP-003] PostgreSQL 直寫 `postgres:18-alpine`,高於 `01-versions.md` 鎖定線 17.x,且未走 `${POSTGRES_VERSION}` 插值
- 檔案:`docker-compose.yml:173`、`docker-compose.development.yml:118`、`.env.example:18`、`docs/Design-Base/00-overview/01-versions.md:14`
- 內容:三處違規疊加 — (1) `01-versions.md` 鎖 PostgreSQL 17.x,compose 用 18(跨 major,規範要求「跨 major 先寫 propose 評估,禁單一 commit 帶過」,且未記 fixed.md;fixed.md §9 僅涵蓋 python/uv);(2) `01-compose.md § 規則` 要求 image tag 必走 `${SERVICE_VERSION}` env、禁直寫,兩份 compose 均直寫;(3) `.env.example:18` 已登記 `POSTGRES_VERSION=18` 但無任何檔案引用它(死變數),`.env.development.example:3` 註解還寫著「禁寫死於 compose」自相矛盾。
- 白話:規範說資料庫版本要用變數管、鎖 17;實際寫死 18,而且登記的變數根本沒人用。
- 修正:`docker-compose.yml:173` 與 `docker-compose.development.yml:118` 改 `image: postgres:${POSTGRES_VERSION}-alpine`(或把 `-alpine` 併入變數值);再擇一:(a) 若確定採 18 → `01-versions.md:14` 鎖定線改 `18.x` 並補一條 fixed.md 記錄跨 major 決策;(b) 若要守規範 → `.env.example` / dev example 改 `POSTGRES_VERSION=17.x` 值(**注意**:既有 volume 由 18 初始化,降版需 dump/restore,建議走 (a))。
- 首次發現:2026-07-06

### 🟠 [R-DEP-002/003] 前端版本鎖定全面偏離:Node 24 / Next 16 未同步 `01-versions.md`,`engines.node` 用浮動範圍
- 檔案:`frontend/package.json:5,14`、`frontend/Dockerfile:2,7,21`、`docs/Design-Base/00-overview/01-versions.md:12-48`
- 內容:(1) `engines.node: ">=24.0.0"` 用 `>=` 浮動範圍 — `01-versions.md § 鎖定原則` 明文禁 `>=`,且規範 Node 鎖定線為 22.x LTS,Dockerfile 用 `node:24-alpine`(模板為 `node:22.13.0-bookworm-slim`,tag 也未鎖到 patch);(2) `next 16.2.7` vs 表列 15.x、`@types/react 19.1.6` 低於表列 19.2.x lock 範例;(3) 收口(fixed.md §1/§9)僅同步了**後端**套件表,前端表與 `package.json` 的分歧未處理 — 與 §1 同型的「規範表 vs Sources of Truth 分歧」,前端側無人收。另 frontend image 缺 `TZ=Asia/Taipei` + tzdata 與 `HEALTHCHECK`(模板 `03-dockerfile-frontend.md` 皆要求;TZ 目前靠 compose 注入補救)。
- 白話:後端版本帳本收口對齊了,前端帳本整頁還是舊的,而且 Node 版本用「24 以上都行」這種規範明文禁止的寫法。
- 修正:`package.json:5` 改 `"node": "24.x.y"`(鎖 patch,或依規範降回 22.x);`frontend/Dockerfile:2,7,21` 改鎖 patch tag(如 `node:24.4.0-alpine`)並補 `ENV TZ=Asia/Taipei` + `apk add tzdata` + `HEALTHCHECK`;`01-versions.md` 前端表以 `package.json` / `package-lock.json` 為準整批校正(next 16.2.x / node 24.x),並比照後端補「Sources of Truth」註記;分歧決策補一條 fixed.md。
- 首次發現:2026-07-06

### 🟠 [R-SEC-002] `/api/v1/auth/login` 無 rate limit
- 檔案:`backend/app/api/v1/auth.py:19-38`
- 內容:本地帳密登入端點無任何節流;`INIT_ADMIN_USERNAME` 在 `.env.example:37` 給了預設值 `init-admin`(帳號可猜),攻擊面 = 純密碼暴力嘗試。bcrypt 驗證(~100ms/次)有天然減速但不構成防護。
- 白話:登入接口可以無限次試密碼,管理員帳號名還幾乎是公開的。
- 修正:最小成本 — `deps.py` 增一個 in-process 滑動視窗限流 dependency(以 client IP + username 計數,如 5 次/分鐘超過回 429)套在 `auth.py:19` 的 login 上;或部署層在 Coolify / 反向代理對 `/api/v1/auth/login` 設 rate limit 並於部署文件載明。redis 已在棧內,亦可用 redis 計數器(多 worker 一致)。
- 首次發現:2026-07-06

### 🟠 [R-SEC-003] 全棧缺安全 headers(CSP / X-Frame-Options / X-Content-Type-Options / HSTS)
- 檔案:`backend/app/main.py:24-42`、`frontend/next.config.ts`(無 headers 設定)
- 內容:後端無 middleware 附加安全 headers,前端 Next config 亦未設 `headers()`。內網後台脈絡下 CSP 風險較低,但 X-Frame-Options(clickjacking)與 X-Content-Type-Options 屬零成本地板;HSTS 於部署 TLS 後必要。
- 白話:回應缺少幾個一行成本的防護頭,點擊劫持與 MIME 嗅探沒有擋。
- 修正:`main.py` 加一個 `@app.middleware("http")` 統一附 `X-Frame-Options: DENY`、`X-Content-Type-Options: nosniff`、`Referrer-Policy: same-origin`;前端 `next.config.ts` 加 `headers()` 回傳同組 headers;HSTS 留給 Coolify 反向代理層並於部署文件註記。
- 首次發現:2026-07-06

### 🟠 [R-GIT-001] build 產物 `frontend/tsconfig.tsbuildinfo` 被追蹤
- 檔案:`frontend/tsconfig.tsbuildinfo`(git tracked;commit c00d72d 甚至專門提交它)、`.gitignore:11-16`
- 內容:TypeScript 增量編譯快取被納入版控,每次 typecheck 都會產生 diff 噪音與潛在 merge conflict;`.gitignore` Node 區缺 `*.tsbuildinfo`。
- 白話:一個機器產生的快取檔被當成源碼在管,每跑一次檢查就髒一次工作樹。
- 修正:`git rm --cached frontend/tsconfig.tsbuildinfo`;`.gitignore:16`(coverage/ 後)加一行 `*.tsbuildinfo`。
- 首次發現:2026-07-06

### 🟡 Medium

### 🟡 [AD-002] `utils/datetime.ts` 用 `new Date()` + `Intl timeZone` 格式化,違反 `04-datetime.md` 模板 — 非 +8 瀏覽器顯示雙偏移
- 檔案:`frontend/src/utils/datetime.ts:1-41`
- 內容:後端序列化為 naive +8 wall-clock 字串(無 offset,fixed.md §18 收口決策)。`formatDateTime` 走 `new Date(iso)`(JS 把無 offset 字串解讀為**瀏覽器本地時間**)再以 `timeZone: 'Asia/Taipei'` 格式化 — 瀏覽器時區 = 台北時恰好抵銷(收口手測因此看不出),任何非 +8 的瀏覽器(出差 / VPN / 系統時區設錯)顯示即偏移 N 小時。`02-frontend/04-datetime.md` 明文「DB 存 UTC+8 wall-clock:禁 `new Date(...)` 帶 `timeZone`」並給了字串切割模板。
- 白話:時間字串被「先當成本地時間、再轉回台北時間」繞了一圈,只有人剛好在台北時區時結果才正確。
- 修正:`utils/datetime.ts` 改用 `04-datetime.md` 的 regex 切割實作(`formatDateTime` / `formatDate` / `formatTime` 全數改為純字串處理,不經 `Date`);`formatNullableDateTime` 不動。
- 首次發現:2026-07-06

### 🟡 [AD-003] `TableList.tsx` 殘留 inline 分頁 UI 與 status badge,繞過收口抽出的 `components/common/*`
- 檔案:`frontend/src/components/tables/TableList.tsx:14-56,156-247`、`frontend/src/components/common/Pagination.tsx`、`common/StatusBadge.tsx`
- 內容:fixed.md §17 收口把 `Pagination` / `StatusBadge` 抽到 `components/common/` 並改了三頁(schedules / runs / runs/[uid])import,但 task-010 的 `TableList.tsx` 未回收:L156-247 的分頁列與 `common/Pagination.tsx` **逐字相同**(「共 X 筆,第 X / Y 頁」+ 上下頁),L14-56 的 `RUN_STATUS_LABELS/CLASSES` + `RunStatusBadge` 與 `common/StatusBadge` 的字典重疊。`05-components.md`:「已存在共用但被繞過 → 改回走共用」。
- 白話:共用元件抽出來了,但其中一頁還留著自己手刻的複製品。
- 修正:`TableList.tsx:156-247` 刪除 inline 分頁改 `<Pagination page={data.page} pageSize={data.page_size} total={data.total} onPageChange={onPageChange} />`;`RunStatusBadge` 內部改組合 `<StatusBadge status={status} />` + 時間副行,刪除本檔的 LABELS/CLASSES 字典。
- 首次發現:2026-07-06

### 🟡 [R-ENV-004] `NEXT_PUBLIC_API_URL` / `COMPOSE_PROJECT_NAME` 被 compose 引用但根 `.env.example` 未登記;前端 code fallback 會把 `localhost` 烘進 production bundle
- 檔案:`docker-compose.yml:12,211,213`、`.env.example`(缺兩鍵)、`frontend/src/lib/api/baseApi.ts:6`、`frontend/src/lib/api/authApi.ts:22-23`
- 內容:(1) `docker-compose.yml:12` build args 引用 `${NEXT_PUBLIC_API_URL}`、L211/213 volume 名引用 `${COMPOSE_PROJECT_NAME}`,但根 `.env.example` 均未登記(staging / production example 有 `NEXT_PUBLIC_API_URL`,root 版漏)— `02-frontend/03-env-and-auth.md`「所有 env 須登記於 .env.example」;(2) `baseApi.ts:6` / `authApi.ts:23` 的 `?? 'http://localhost:8000/api/v1'` fallback:build 時漏傳 build args 不會失敗,而是**靜默把 localhost 烘進 bundle**,部署後所有 API 打向使用者自己的機器,錯誤難排查。
- 白話:部署時忘了給前端 API 網址,build 照樣成功,只是成品會打 localhost — 這種錯應該在 build 就炸出來。
- 修正:`.env.example` 補 `NEXT_PUBLIC_API_URL=`(註記 compose build args 用)與 `COMPOSE_PROJECT_NAME=data-center-etl`;`baseApi.ts:6` 改為 `const base = process.env.NEXT_PUBLIC_API_URL; if (!base) throw new Error('NEXT_PUBLIC_API_URL 未設定')`(dev 由 `.env.local` 提供,build 缺值即 fail-fast),`authApi.ts:22-23` 同步。
- 首次發現:2026-07-06

### 🟡 [R-ENV-002] `.gitignore` 缺 `02-secrets.md` 規定必排的 `credentials*` / `*.key` / `*.pem`
- 檔案:`.gitignore:18-24`、`docs/Design-Base/00-overview/02-secrets.md:27-35`
- 內容:規範「.gitignore 必排」清單含 `credentials*`、`*.key`、`*.pem`,現行 `.gitignore` 只排 `.env*` 系列 — 未來任何人把金鑰檔放進 repo 目錄就會被 `git add -A` 收進去。
- 白話:防呆名單少了三行,金鑰檔案現在沒有防線。
- 修正:`.gitignore:24`(`!.env.*.example` 後)補三行:`credentials*`、`*.key`、`*.pem`。
- 首次發現:2026-07-06

### 🟡 [R-TEST-001] 前端零測試(無測試框架、無 test script;`AGENTS.md` 標準指令 `npm run test` 會直接失敗)
- 檔案:`frontend/package.json:6-12,20-31`
- 內容:`package.json` 無 `test` script、devDependencies 無 vitest/jest/@testing-library;`AGENTS.md § Build / Test / Lint` 的前端標準流程含 `npm run test`,照跑會 exit 1。後端 12 個測試檔對照下,前端關鍵邏輯(`sanitizeNextPath` open-redirect 防護、`extractApiErrorDetail`、silent re-auth 重試計數、`consumeReauthReturnTo` 路徑白名單)全靠手測。
- 白話:前端一行測試都沒有,連跑測試的指令都不存在,規範文件裡的標準指令是壞的。
- 修正:Next 路線依 `AGENTS.md § Testing` 補 jest(或經授權改 vitest)+ `@testing-library/react`(鎖 patch、同步 `01-versions.md`),先覆蓋純函式(`utils/apiError.ts`、`lib/auth/sso.ts`、`login/page.tsx` 的 `sanitizeNextPath`)與 `package.json` 補 `"test"` script;或短期先在 `AGENTS.md` 註記前端 test 缺口避免指令誤導(治標)。
- 首次發現:2026-07-06

### 🟡 [AD-004] `etl_runs.status` 的 `partial` 永遠不會產生 — engine 一律標 `failed`,前端「部分失敗」過濾是死選項
- 檔案:`backend/app/etl/engine.py:421`、`backend/app/models/etl_run.py:77-80`、`frontend/src/app/(main)/runs/page.tsx:28`
- 內容:schema check constraint 與前端 filter 都定義了 `partial`(部分成功部分失敗),但 `engine.run_etl` 的收尾為 `status = "failed" if failed else "success"` — 10 表成功 1 表失敗與 11 表全失敗都顯示同一個「失敗」,`partial` 語意存在但無產生路徑,前端過濾「部分失敗」永遠查無資料。
- 白話:狀態欄設計了「部分失敗」這個燈號,但點火開關從來沒接線。
- 修正:`engine.py:421` 改三態:`status = "success" if failed == 0 else ("partial" if success > 0 else "failed")`;同步確認 `tests/test_etl_engine.py` 補 partial case。
- 首次發現:2026-07-06

### 🟡 [AD-005] `/api/v1/health` DB 掛掉仍回 HTTP 200 — compose healthcheck 偵測不到 DB 斷線
- 檔案:`backend/app/api/v1/health.py:19-25`、`docker-compose.yml:72`
- 內容:health 端點捕捉 DB 例外後回 `200 + {"db": "fail"}`;compose healthcheck 用 `curl -fsS` 只看 HTTP status → DB 斷線時 backend 仍判 healthy,`depends_on: service_healthy` 的 worker / scheduler 也不會被擋,restart 策略不會介入。
- 白話:健康檢查嘴上說「DB 壞了」,但回的狀態碼是「我很好」,監控系統只聽狀態碼。
- 修正:`health.py:25` 當 `db_ok == "fail"` 時改回 503(`JSONResponse(status_code=503, ...)` 或沿用 `failure(detail="db unavailable", response_code=503, status_code=503)`),200 僅在全綠時回。
- 首次發現:2026-07-06

### 🟡 [AD-006] ETL 整表載入記憶體:`fetch_rows` 一次讀全表、writer 單交易全量 INSERT — 大表 OOM / 長交易風險
- 檔案:`backend/app/etl/reader.py:59-67`、`backend/app/etl/writer.py:51-97`
- 內容:`PostgresSourceReader.fetch_rows` 把整表 `SELECT` 結果物化為 `list[dict]`,engine 再 `map_row` 產生第二份完整複本,writer 在單一交易內 executemany 全量寫入 — 記憶體占用 ≈ 2×表大小,ERP 來源表若達百萬列等級,worker 容器(無資源上限)可能 OOM,且 TRUNCATE+INSERT 長交易期間目標表整段不可讀。v1.0.0 Glue 版(`etl/common/reader.py`)有 fetchsize/partition 設計,移植時簡化掉了。
- 白話:搬資料是「整卡車一次扛」,表小沒事,表大會閃到腰。
- 修正:`reader.py` 改 `conn.stream(text(sql))`(server-side cursor)+ `yield` batch(如 5000 列);`writer.write_table` 收 iterator 分批 `executemany`(交易邊界可維持單交易保原子性,記憶體則降為單 batch)。若近期表量可控,至少在 `docs/Tasks` 註記此限制與表大小上限。
- 首次發現:2026-07-06

### 🟡 [R-PII-003] 無 audit log:登入(成敗)、角色 / 設定變更未留稽核紀錄
- 檔案:`backend/app/api/v1/auth.py:24-38`、`backend/app/services/auth_service.py:21-28`
- 內容:規則要求登入 / 權限變更須記錄。現況登入成功 / 失敗完全無 log(連應用級 `logger.info` 都沒有),誰在何時停用了某表 / 改了 mapping 只能靠 `updated_by/updated_at` 推最後一次,無事件序列。脈絡註記:內部工具、users 僅 admin/viewer 二角、ETL 設定變更已有 `updated_by` 欄位半覆蓋 → 由規則地板 🟠 降為 🟡。
- 白話:誰登入過、誰改過設定,出事時查不到完整足跡。
- 修正:最小成本 — `auth_service.authenticate` 成功 / 失敗各補一行結構化 `logger.info`(帳號 + 結果 + IP,由 router 傳入;禁記密碼);`sso_service.login_with_code` 同。完整 audit 表(`10-statistics-log.md` 選用方案)列下版評估。
- 首次發現:2026-07-06

### 🟡 [R-LOG-005] 無任何 logging 組態:無 app_name / request_id、時戳格式非 ISO+offset
- 檔案:`backend/app/main.py`(無 logging 設定)、`docs/Design-Base/03-backend/05-exceptions-and-logging.md:18-22`
- 內容:全後端僅 `logging.getLogger(__name__)` 裸用,無 `logging.basicConfig` / dictConfig — 實際輸出格式由 uvicorn 預設決定(worker / scheduler 下更是 root logger 預設 WARNING,`engine.py` 的 `logger.info` 逐表紀錄在容器 log **根本不會出現**);規範要求結構化欄位 `app_name` / `request_id` / ISO+offset 時戳全缺。
- 白話:程式有寫 log,但沒接喇叭 — worker 的 info 級訊息實際上是靜音的。
- 修正:`main.py`(與 `worker/tasks.py` 或共用 `core/logging.py`)加統一 `logging.basicConfig(level=INFO, format="%(asctime)s%(msecs)03d+08:00 %(name)s %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S.")` 起步;`request_id` 以 middleware 產 UUID 掛 `request.state` 並入 log(可下版);log level 走 env。
- 首次發現:2026-07-06

### 🔵 Low

### 🔵 [R-BE-016] `typing.Any` 用於 etl 模組與 seed script(規範禁 `Any`,異質容器應 `object`)
- 檔案:`backend/app/etl/engine.py:19`、`etl/reader.py:12`、`etl/writer.py:13`、`etl/transforms.py:16`、`backend/scripts/seed_etl_config.py:22`
- 內容:`AGENTS.md` / `03-backend/00-overview.md` 明文禁 `Any`;etl 資料面全部用 `dict[str, Any]`。mypy strict 下 `Any` 合法故未被攔。
- 修正:五檔把 `Any` 全域替換為 `object`(轉換函式 `to_int(value: object)` 等簽章不受影響;`map_row` 回傳 `dict[str, object]`)。
- 首次發現:2026-07-06

### 🔵 [04-api-docs] Pydantic schema 欄位普遍缺 `Field(description=...)`(規範標「必填;空字串視為缺漏」)
- 檔案:`backend/app/schemas/run.py`、`schemas/schedule.py`、`schemas/etl_config.py`、`schemas/auth.py`(全檔多數欄位)
- 內容:`00-overview/04-api-docs.md` 要求每欄 `description` 必填供 `/api/docs`;現況僅少數欄有註解、無 description,Swagger 上欄位語意全靠猜。
- 修正:各 schema 欄位補 `Field(..., description="<語意>")`;優先補對外請求類(`EtlMappingUpsertRequest` / `ScheduleCreateRequest` / `RunTriggerRequest`)。
- 首次發現:2026-07-06

### 🔵 [04-api-docs] 狀態列舉以 `Literal` / 裸 `str` 散落,未用 `Enum`
- 檔案:`backend/app/api/v1/runs.py:23-25`、`schemas/run.py:9-10,34`(`status: str`)
- 內容:規範「列舉值用 Enum,禁 Literal 散落」;run/log 狀態在 model check constraint、router Literal、schema str、前端 type 四處各自定義,新增狀態要改四處。
- 修正:`app/schemas/run.py`(或 `models/enums.py`)定義 `RunStatus(str, Enum)` / `RunLogStatus` / `TriggerType`,router 查詢參數與 response schema 均改用之,check constraint 值由 Enum 產生。
- 首次發現:2026-07-06

### 🔵 [R-BE-004] `sso.py` 三端點無 `response_model`;`health.py` 以 `dict[str, str]` 作 data 型別
- 檔案:`backend/app/api/v1/sso.py:62,92,152`、`backend/app/api/v1/health.py:16`
- 內容:`/sso/me` 回裸 `Response`(OpenAPI 無 schema),callback / logout 為 redirect 可豁免但未標 `response_class` 說明;health 的 `ApiResponse[dict[str, str]]` 與「路由 response type 必用 Pydantic schema、禁 dict」有落差(health 屬邊緣端點,影響僅文件)。
- 修正:`sso_me` 加 `response_model=ApiResponse[SsoMeResponse]`(維持手動 JSONResponse 亦可標 `responses={...}`);health 定義 `HealthResponse(BaseModel): db: str` 取代 dict。
- 首次發現:2026-07-06

### 🔵 [AD-007] `get_settings()` 每次呼叫重新實例化 `Settings`(重讀 `.env` 檔)
- 檔案:`backend/app/core/config.py:41-42`
- 內容:`deps.get_current_user` / 各 router 每請求呼叫 `get_settings()`,pydantic-settings 每次 init 都做一次 `.env` 檔案 I/O 與驗證;非正確性問題,純浪費。
- 修正:`config.py:41` 加 `@lru_cache` 於 `get_settings`(標準 FastAPI 模式);測試若需覆寫 env 記得 `get_settings.cache_clear()`。
- 首次發現:2026-07-06

### 🔵 [TS 型別地板] `store.ts` / `provider.tsx` 三處函式缺回傳型別標註
- 檔案:`frontend/src/store/store.ts:5,17`、`frontend/src/store/provider.tsx:11`
- 內容:`02-frontend/00-overview.md`「函式必標參數+回傳型別」;`makeStore`、`setupStoreListeners`、`StoreProvider` 均靠推導。
- 修正:`makeStore = (): AppStore =>`(需先以 `configureStore` 回傳型別定義)、`setupStoreListeners(store: AppStore): void`、`StoreProvider(...): React.ReactNode`。
- 首次發現:2026-07-06

### 🔵 [R-TEST-002 / R-DEP-004] 無 CI(`05-CI/` 規範存在,repo 無 `.github/workflows`;依賴掃描 pip-audit 已裝但無排程執行)
- 檔案:`.github/`(不存在)、`docs/Design-Base/05-CI/00-overview.md`
- 內容:lint / typecheck / test / pip-audit / gitleaks(`.gitleaks.toml` 已在 repo)全靠人工執行,收口品質依賴 worker 自律。
- 修正:補最小 workflow(backend:`uv sync --frozen && ruff && mypy && pytest`;frontend:`npm ci && lint && typecheck && build`;另 job 跑 `pip-audit` + `gitleaks`),分階段對齊 `05-CI/*`。
- 首次發現:2026-07-06

### 🔵 [R-LOG-006] 缺 `/api/v1/version`
- 檔案:`backend/app/api/v1/health.py`(僅 health)
- 內容:規範建議 version 端點供部署驗證(現無法從線上確認跑的是哪個 build)。
- 修正:`health.py` 同檔加 `GET /version` 回 `{version, git_sha}`(由 env `APP_VERSION` / `GIT_SHA` 注入,compose build args 傳入)。
- 首次發現:2026-07-06

### 🔵 [05-exceptions] `RequestValidationError` handler 只回「輸入驗證失敗」,無欄位級錯誤
- 檔案:`backend/app/core/exceptions.py:34-36`
- 內容:規範表定 RequestValidationError → 欄位級錯誤;現況前端只拿到通用句,表單哪個欄位錯無從顯示(目前前端多為受控輸入影響小,但排程 cron 欄等 422 時使用者只看到籠統訊息)。
- 修正:`exceptions.py:36` 把 `exc.errors()` 精簡為 `[{"field": ".".join(str(x) for x in e["loc"][1:]), "message": e["msg"]}]` 放入 `data` 欄回傳(維持 detail 通用句)。
- 首次發現:2026-07-06

### 🔵 [Docs 漂移] `.env.staging.example` / `.env.production.example` 註解引用不存在的 compose 檔名
- 檔案:`.env.staging.example:2`(`docker-compose-staging.yml`)、`.env.production.example:2`(`docker-compose-production.yml`)
- 內容:repo 實際只有 `docker-compose.yml`(部署)與 `docker-compose.development.yml`;兩行註解引用的檔案不存在,部署者會找錯檔。
- 修正:兩檔 L2 註解改指 `docker-compose.yml`(Coolify 讀根目錄檔)。
- 首次發現:2026-07-06

### ⚪ Info

### ⚪ [依賴殘留] `passlib[bcrypt]==1.7.4` 仍列依賴但程式已改 bcrypt 直呼;bcrypt 版本僅由 uv.lock 間接鎖定
- 檔案:`backend/pyproject.toml:11`、`backend/app/core/security.py:18` — 見 fixed.md §3(已記錄,收口未調整依賴,屬既知取捨)
- 修正建議(下版):移除 passlib、改直列 `bcrypt==5.0.x` 並同步 `01-versions.md`。
- 首次發現:2026-07-06

### ⚪ [07-testing] 測試建 schema 用 `Base.metadata.create_all` 而非 alembic
- 檔案:`backend/tests/test_auth.py:41`(等多檔)
- 內容:規範建議 alembic 跑 schema 以驗證 migration 本身;create_all 等效建表但 migration 的 server_default / index 定義若與 model 漂移,測試抓不到。目前兩者一致,列資訊供下版測試基建參考。
- 首次發現:2026-07-06

---

## 4. 修正優先序

### 立刻(部署前必處理)
1. 🟠 AD-001 跨 host cookie 守衛迴圈 — user 部署拓撲決策前必須定案(同網域路由或 COOKIE_DOMAIN),否則 production 登入直接壞
2. 🟠 R-SEC-002 login rate limit(部署後即暴露)
3. 🟡 R-ENV-004 `NEXT_PUBLIC_API_URL` fail-fast + 登記(部署 build 防呆)
4. 🟡 AD-005 health 503(部署 healthcheck 正確性)

### 本週
5. 🟠 PostgreSQL 18 / Node 24 / Next 16 版本鎖定線三案收斂:決策 + `01-versions.md` 同步 + fixed.md 記錄 + compose 改 `${POSTGRES_VERSION}`
6. 🟠 R-SEC-003 安全 headers、🟠 R-GIT-001 tsbuildinfo 移除追蹤(各 10 分鐘)
7. 🟡 AD-002 datetime.ts 改字串切割、🟡 AD-003 TableList 回收共用、🟡 AD-004 partial 狀態接線
8. 🟡 R-LOG-005 logging 組態(worker log 目前實質靜音,影響維運)

### 有空
9. 🟡 R-TEST-001 前端測試基建、🟡 AD-006 ETL 分批讀寫、🟡 R-PII-003 登入 log
10. 🔵 全部(Any 替換、Field description、Enum 收斂、lru_cache、CI、/version、422 欄位級、compose 檔名註解)

---

## 5. 已跳過類別 / 規則與脈絡衝突註記

- **組成偵測**:ENV / AI / FE / BE / DB / SEC / PII / LOG / GIT / TEST / DEP 全數存在,**無跳過類別**。
- **`etl/` 目錄**:v1.0.0 凍結遺產,依任務脈絡僅驗證「未被 v1.1.0 動到」(git log + 工作樹確認 ✓),內部品質不掃。
- **規則與脈絡衝突(依心法 3 跳過,非漏掃)**:
  - **R-BE-019(service 多表寫入無 `db.begin()`)**:`deps.get_db` 為 request-scope 單一交易(結尾 commit、例外 rollback),`create_table` / `delete_table` / `replace_mappings` 的跨表寫入實質原子,service 層再包 begin 反而與 autobegin 衝突 — 等效實現,不回報。
  - **R-FE-007(後端 error 直顯)+ R-FE-004(語言 literal)**:單語系內部後台,後端 detail 即繁中使用者訊息,為 §11 / §16 既定做法 — 見 fixed.md §11。
  - **R-DB-004(SQL 字串組裝)**:`etl/reader.py` / `writer.py` / `comments.py` 的 DDL / 識別字無法 bind params,已按 `04-sql-safety.md` 走白名單 regex + 引號化、值走 bind — 合規實作,不回報。
  - **SSO 每請求回源中央(效能)**:`deps._verify_sso_session` 對每個受保護請求多一次 HTTP roundtrip,為 `08-df-sso.md` 契約 #1 的硬性要求 — 設計取捨,不回報。
  - **`error_stack` 完整回傳前端**:propose 驗收明文要求逐表 log 含 stack trace(僅登入者可讀,落 DB 前已遮罩 DB 密碼)— 產品需求,不回報。
- **fixed.md 已載明、不重複回報**:§2 多來源字串約定、§7 client 單檔未升格子目錄(列下版候選)、§8 撤銷註記 process-local(列下版候選)、§11 i18n 豁免、§15 run_uid nullable、§18 API 序列化未補 offset(列下版候選)。

---

## 6. AD-xxx(規則外發現)

| ID | 嚴重度 | 摘要 |
| --- | --- | --- |
| AD-001 | 🟠 | 跨 host 部署 cookie 守衛導向迴圈(production example 拓撲即中招)|
| AD-002 | 🟡 | datetime.ts `new Date`+`Intl timeZone` 違 04-datetime 模板,非 +8 瀏覽器雙偏移 |
| AD-003 | 🟡 | TableList 殘留 inline 分頁 / badge,繞過收口抽出的 common 元件 |
| AD-004 | 🟡 | `partial` run 狀態定義了但永不產生,前端過濾死選項 |
| AD-005 | 🟡 | health DB fail 仍回 200,compose healthcheck 失效 |
| AD-006 | 🟡 | ETL 整表載入記憶體 + 單交易全量寫,大表 OOM 風險 |
| AD-007 | 🔵 | `get_settings()` 未快取,每請求重讀 `.env` |

**已巡視面向**(未發現額外問題者):邏輯邊界(分頁 offset / cron 驗證 / UUID 解析 / open-redirect 防護 `sanitizeNextPath` ✓)、N+1(list 端點均批次 `in_` 查詢 ✓)、race(init_admin 冪等、replace_mappings 同交易軟刪重建 ✓)、狀態機(run pending→running→終態、殭屍 run 補標 failed ✓)、啟動流程(migration 先於 API、lifespan dispose ✓)、re-render(useCallback / memo / 字面值提取普遍到位 ✓)、機密(無硬編、log 遮罩、`.env` 從未入版控 `git log --all` 為空 ✓)、幻覺 API(taskiq `cron_offset` / `ScheduleSource` 等均為真實 API ✓)。

---

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **`02-frontend/03-env-and-auth.md` vs `90-third-party-service/08-df-sso.md` 矛盾**:前者規定「SSO callback 須驗 state CSRF」,但 DF-SSO 契約的 `authorize` / `callback` 協定**不存在 state 參數**(§ 5 端點行為契約僅 code)— 採用 DF-SSO 的專案永遠無法滿足前者。建議:`03-env-and-auth.md` 該條補「DF-SSO 走 08-df-sso 契約者豁免(協定無 state)」註記,並向中央登入器回饋 CSRF 缺口(authorize 缺 state 使 callback 可被跨站觸發,屬中央協定層風險)。
2. **`01-versions.md` 前端表無 Sources of Truth 收斂機制**:收口(fixed.md §1/§9)為後端補了「以 pyproject / uv.lock 為準」規則,前端表(next 15.x / node 22.x / vitest 2.x / prettier)與實際 `package.json`(next 16 / node 24 / 無測試框架 / 無 prettier)整批分歧且無同步義務條款 — 與 §1 同型問題的前端側缺口。建議:前端表比照補「Sources of Truth 為 package.json / package-lock.json」並本次一併校正。
3. **`06-Coolify-CD/01-compose.md` 模板與 Coolify 實務未對齊**:模板要求 image tag 走 `${SERVICE_VERSION}`、backend healthcheck 例示 port 8000/80,但 task-012 實作(經收口驗證通過)在多處合理偏離:官方 image 直寫 tag、production compose 不設 `image:` 名(Coolify 自管命名,致 propose「image 全 etl_ prefix」驗收實際僅 development compose 滿足)、`SERVICE_URL_*` magic env 為 Coolify 特有慣例但模板未提。建議:`01-compose.md` 補「Coolify 部署變體」小節,收斂直寫 tag 與 image 命名的允許條件,避免下個專案在同一點反覆偏離。
4. **`03-backend/07-testing.md` 過薄**:僅三行,未定義測試 DB 生命週期(本專案各測試檔自建 `data_center_etl_test` + `create_all`,與「alembic 跑 schema」的規範句衝突而無裁決細則)、無 fixture 共用規範(12 個測試檔各自複製 env 注入前置碼)。建議下版 reflect 時擴充。

---

> 本次掃描共 🟠 6 / 🟡 10 / 🔵 10 / ⚪ 2,無 🔴 Critical。多數 🟠 為部署前置風險與版本治理,建議依第 4 章順序處理。**需要我幫你修 High(🟠)項目嗎?**
