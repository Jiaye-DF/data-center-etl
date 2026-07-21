# Issue Scan — data-center-etl(260721145815)

> 掃描時間:2026-07-21 14:58 (UTC+8)|範圍:v1.5.1 全部新碼(`7b2a77e..HEAD`,commit ccfcfa2 + af5d31d;32 檔 +2,715/-167)+ 前次遺留存續確認|方法:三區域(後端/前端/ENV·GIT·DEP·docs)並行掃描彙整
> 已記錄於 `docs/Tasks/v1.5.1/fixed.md` 者視為已處理(§1 introspect 排除、§2 殭屍 run 個案收殮、§3 updated_by text→uuid),僅在修法本身有新問題時另列。

## 0. 與前次差異(前次:Issue-Scan-Project-260720073813.md)

前次 🔴0 🟠2 🟡9 🔵14 ⚪3 → 本次 🔴0 🟠4 🟡14 🔵14 ⚪3。

- ✅ 已修 8 項:**AD-111~AD-118**(前次報告發布後於 v1.5.0 收口完成:0f2ad6e 後端 / 0e809d9 前端;本次逐項確認修正在位且 v1.5.1 改動無回歸 — 尤其 view_generator 大改後 AD-112「42P16 才 DROP」與 AD-113「全成功才寫簽名」語意均保留,對應測試齊全)
- 🆕 新增 13 項:AD-119~AD-131(🟠2 🟡8 🔵3)+ ⚪1(測試 env 覆寫 pattern 擴散)— 全部來自 v1.5.1 新碼,無 Critical
- ⏸ 仍在 20 項:前次全部遺留逐項確認存續。三處所在檔案本版有動但關切未處理:**AD-101**(fixed.md §2 僅個案收殮,worker 啟動收殮/watchdog 治本未實作)、**AD-102**(worker/tasks.py 增的是語意映射收尾,同表並發防疊未動)、**R-ENV-002**(.gitignore 有動但為移除 html 忽略,三樣式關切未處理且見 🆕 AD-127);其餘所在檔案未動沿用前次結論
- 🔄 變化 1 項:**R-AI-001 記錄**(內網 IP 面擴大 — 除 tools/ script 外,本版入版控的 7 個 HTML 報告 header 亦含內網 DB IP + sa/sys 帳號名,見 ⚪ 節)

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 嚴重度統計 | 🔴 0 🟠 4 🟡 14 🔵 14 ⚪ 3(🟠 2 為前次遺留 + 2 🆕;v1.5.1 新碼零 Critical) |
| 結論 | v1.5.1 新碼在注入面、權限(8 新端點全 require_admin + 403 測試)、時間型別通則、alembic 安全性、型別紀律(前端零 any)上全數乾淨;新發現集中在**進度 key/併發互斥的維運正確性**(AD-119/120)與**輪詢面放大踩上測試站 502 實錘根因**(AD-121)兩群,加上 .gitignore 白名單紀律與 39 MB HTML 入庫的 repo 衛生問題 — 🟠 兩條建議部署前修,其餘不擋合併 |

## 2. 專案摘要

- 目標:ERP Oracle → DMS → RDS PG 資料中心 ETL;v1.5.1 = 快照/套用全局進度條 + 語意映射管理頁(CRUD/Combobox/套用變更)+ view schema 改 `_view` + erp_metadata 排除 + updated_by uuid 對齊
- 技術棧:Next.js 16 + TS strict / FastAPI + SQLAlchemy 2 async / PostgreSQL — 與 CLAUDE.md 鎖定棧一致,**零新增依賴**(pyproject/uv.lock/package.json 本版零 diff)
- Task 進度:v1.5.1 7/7 done(tasks-v1.5.1.md);verification-v1.5.1.md 真實 RDS 端到端冒煙全過;後端 308 passed、前端 typecheck/lint/build 綠(前端零測試 R-TEST-001 ⏸)
- 文件:fixed.md 3 條均含根因段,格式合規;tasks/verification/propose 狀態一致

## 3. 詳細發現(依嚴重度;⏸ 遺留項僅列 ID,細節見前次報告)

### 🟠 High(4 項:2 ⏸ + 2 🆕)

- [R-SEC-002] login rate limit(`backend/app/api/v1/auth.py`)— ⏸ 自 2026-07-06
- [R-SEC-003] 安全 headers(`backend/app/main.py` / `frontend/next.config.ts`)— ⏸ 自 2026-07-06

#### 🆕 [AD-119] 快照進度 key 落在 mirror_sync 收尾 delete_pattern 的 blast radius → 進行中進度條被誤刪
- 檔案:`backend/app/services/snapshot_service.py:156`(`_progress_key`)、`backend/app/worker/tasks.py:477`
- 內容:快照進度 key 命名 `datasets:{dataset}:refresh-progress`,落在 mirror_sync 每輪收尾必打的 `delete_pattern("datasets:source:*")` 範圍內。一表一排程下 run 結束頻繁;admin 正在跑數分鐘級 source 快照 refresh 時,任一 run 收尾就把進度 key 刪掉 → 前端讀到 `active=false`,進度條中途消失、被誤判已完成(persist 階段每 200 表才回報一次,空窗期不短)。`tasks.py:301` 的註解已明確識別此類 hazard 並讓 APPLY_PROGRESS_KEY 刻意避開,snapshot key 自己踩進同型陷阱。
- 修正:`_progress_key` 改獨立 namespace,如 `cache.cache_key("snapshot-progress", dataset_value)`(對齊 APPLY_PROGRESS_KEY 設計);`test_snapshot_refresh_progress.py` 的 spy 以 `endswith("refresh-progress")` 攔截,不受影響。
- 首次發現:2026-07-21

#### 🆕 [AD-121] 全局進度條讓每個 admin 分頁閒置輪詢 ×4,疊上「輪詢×每請求回源 SSO 驗證→429→502」已實錘根因
- 檔案:`frontend/src/components/sync/SnapshotProgress.tsx:64-72`、`ApplyProgress.tsx:17-23`、`app/(main)/layout.tsx:106-108`;`backend/app/api/v1/semantic_mappings.py:113`、`datasets.py:184`
- 內容:v1.5.1 前 layout 只有 SyncProgress 一條 5s 輪詢;現在加 snapshot source、snapshot target、apply 三條,全部**無條件** 5s 輪詢(skip 只擋非 admin)— 閒置分頁 4 req/5s(48 req/min)。而 progress GET 掛 require_admin → SSO 登入者每請求回源中央驗證,測試站 502 的實錘根因(見 staging 502 調查)正是這個組合;本版把該風險放大 4 倍且修法(TTL 快取 vs 契約 #1)尚未決議。另 `datasetApi.ts:181` 註解「僅 refresh 進行中輪詢」與實況不符。
- 修正:優先合併為單一聚合進度端點(如 `GET /progress` 一次回 sync/snapshot×2/apply),layout 只輪詢一條;退而求其次 snapshot 端點一次回 source+target + 閒置降頻(連續 N 次 `active=false` 改 30s,偵測到 active 回 5s)。同步把 `datasetApi.ts:181` 註解改與實況一致。
- 首次發現:2026-07-21

### 🟡 Medium(14 項:6 ⏸ + 8 🆕)

#### 🆕 [AD-120] 手動「套用變更」與排程 mirror_sync 收尾無互斥,併發互踩
- 檔案:`backend/app/services/semantic_admin_service.py:176`(sync_views)、`backend/app/worker/tasks.py:313-339`(refresh_semantic_copy_and_views)
- 內容:API process(手動)與 worker process(排程收尾)共用 `refresh_semantic_copy_and_views` 但無鎖。併發時:(a) 兩邊各自 replace_all(DELETE+INSERT),後跑者 INSERT 撞 `uq_semantic_mappings_table_name_column_name` → 手動端 500;(b) 先結束者 finally 刪共用 APPLY_PROGRESS_KEY,另一方還在跑,進度條被誤判結束;(c) 兩邊同時對 RDS 做 view DDL 可能互撞(簽名機制可自癒但當輪統計失真)。同 dataset 兩個併發 snapshot refresh 也共用同一進度 key,同型互刪。
- 修正:以 Redis `SET NX`(帶 TTL)跨 process 互斥 — 手動端取不到鎖回 409「套用進行中」;mirror_sync 收尾取不到鎖 log info 略過本輪(下輪簽名補)。前端輔助:`SemanticMappingManager.tsx:375-382` 按鈕 disabled 加 `applyProgress?.active === true`(與全局進度條共用 RTK Query 快取,不多打 API)。
- 首次發現:2026-07-21

#### 🆕 [AD-122] POST /sync-views 為同步長請求(數分鐘級),超 proxy timeout 統計遺失甚至中斷
- 檔案:`backend/app/api/v1/semantic_mappings.py:100`
- 內容:HTTP request 內同步跑「12k 列副本重灌 + 全量 view 重生」;超過反向代理 timeout 時回應(copied/created/failed)遺失,request task 被取消更會中斷重生(finally 清 key、簽名不寫入可自癒,但當次白跑)。
- 修正:改派 taskiq task(專案已有 broker),POST 立即回 202 + 前端純靠 progress key 收斂;與 AD-120 的鎖一起做順路。
- 首次發現:2026-07-21

#### 🆕 [AD-123] 語意映射寫入(PATCH / confirm-table / sync-views)未寫 audit_logs,偏離既有稽核慣例
- 檔案:`backend/app/api/v1/semantic_mappings.py:69-104`、`semantic_admin_service.py:128/165/176`
- 內容:專案慣例 admin 設定變更/手動觸發皆寫 audit_logs(schedule_service/sync_service/user_service 皆有)。語意映射直接改 RDS 真身並影響對外 view,現在誰改了什麼、誰整表 confirm、誰觸發套用,自有 DB 稽核軌跡全空(RDS 端 updated_by 只留最後一手,無歷程)。
- 修正:三個 endpoint 注入 `Depends(get_db)`,呼叫 `AuditService(db).log(action="semantic_mapping.update" / ".confirm_table" / ".sync_views", ...)`(隨 get_db 尾端 commit)。
- 首次發現:2026-07-21

#### 🆕 [AD-124] 多條進度條同時 active 時,捲動後互相疊在同一 sticky 位置(後蓋前)
- 檔案:`app/(main)/layout.tsx:106-108`、`SyncProgress.tsx:37`、`SnapshotProgress.tsx:89`、`ApplyProgress.tsx:39`
- 內容:三個進度條為 layout 獨立 sibling,各自 `sticky top-14 z-40`;同時 active(ETL 收尾自動套用 + 快照並行等)且往下捲時,各自釘在 top-14 互相覆蓋,只看得到 DOM 最後一條。頁頂未捲動時正常,平時測不到。
- 修正:layout.tsx 把三元件包進單一 `<div className="sticky top-14 z-40">`,各元件移除自身 sticky 定位(保留列樣式),同容器內自然垂直堆疊。
- 首次發現:2026-07-21

#### 🆕 [AD-125] 管理頁表清單查詢失敗靜默吞錯 → 表篩選/整表轉已確認整組無聲失能(AD-118 同型重現)
- 檔案:`frontend/src/components/semantic/SemanticMappingManager.tsx:165`(未取 isError)
- 內容:`useListSemanticTablesQuery` 失敗時 tables=undefined:combobox 建議池空、自由打字永遠 matched=null 無法選表、「整表轉已確認」按鈕不出現,無任何錯誤提示。同型問題前次 AD-118 已在 DatasetBrowser 修掉(modulesError 提示),新頁又寫回無 error 態版本。
- 修正:取出 `isError`,比照 `DatasetBrowser.tsx:149-151` 在「資料表」列旁顯示「表清單載入失敗」。
- 首次發現:2026-07-21

#### 🆕 [AD-126] 表名 combobox 自由打字不命中時靜默不動作,顯示文字與實際篩選脫鉤
- 檔案:`frontend/src/components/semantic/SemanticMappingManager.tsx:233-251`(handleTableCommit)
- 內容:不命中時什麼都不發生:輸入框顯示新字串、列表仍以先前 activeTable 過濾,無提示;且同一共用元件在 DatasetBrowser 是「打什麼就模糊篩什麼」,兩頁行為不一致。
- 修正:`matched === null` 分支在 `activeTable !== ''` 時解除表篩選(`setActiveTable(''); setPage(1)`);或 combobox 旁加「查無此表,請自下拉選取」提示。
- 首次發現:2026-07-21

#### 🆕 [AD-127] .gitignore 整條移除 `output/*.html` 忽略 → 未來重生報告自動入版控,無人為把關
- 檔案:`.gitignore:60`
- 內容:本次入版控 7 檔是有意為之,但規則整條拿掉後,日後 tools/ 重跑產出的任何 HTML(可能含更多資料或一次性草稿)都會被 git 自動追蹤。
- 修正:改精確白名單 — 保留 `docs/ERP-Analyze/output/*.html` 忽略,逐檔 `!docs/ERP-Analyze/output/bpm-metadata.html` 等 7 條 negate;順手刪殘留空行。
- 首次發現:2026-07-21
- **裁定(2026-07-21)**:user 決議 ERP HTML 報告(含日後重生)一律入版控 — **不修**,`.gitignore` 維持無忽略規則(白名單方案已提出並被否決)。

#### 🆕 [AD-128] 7 個 HTML 共約 39 MB 永久進 git 歷史
- 檔案:`docs/ERP-Analyze/output/`(m2201 11.0 MB、f2204 8.8 MB、s2202 7.0 MB、erp-data-clean 4.3 MB、hrm 4.2 MB、g2203 3.3 MB、bpm 0.6 MB;+196,927 行)
- 內容:clone 與 CI checkout 從此變慢;HTML 重生再 commit 是整檔重寫,delta 無效。已入歷史除非改寫歷史拿不掉。
- 修正:至少從下一版起停止累積(配合 AD-127 白名單);若需長期版控考慮 Git LFS 或改存壓縮/摘要 md。
- 首次發現:2026-07-21
- **裁定(2026-07-21)**:隨 AD-127 裁定接受現狀(HTML 一律入版控)。

#### ⏸ 遺留 6 項(見前次報告):AD-101(殭屍 run — fixed.md §2 個案收殮,治本待做)、AD-102(同表並發)、AD-103(production adminer)、R-DEP-003、R-ENV-002、R-TEST-001

### 🔵 Low(14 項:11 ⏸ + 3 🆕)

#### 🆕 [AD-129] introspect 後綴排除 `%_view` / `%_en` 同時作用於 source 側且靜默,存在誤殺邊界
- 檔案:`backend/app/etl/introspect.py:46-52`(`_EXCLUDED_SCHEMA_CONDS`)
- 內容:語意化 view 只落 target;若來源 ERP 未來出現 `_view` / `_en` 結尾的業務 schema,會被靜默排除(無 log、永不同步)。現有四帳套命名無撞名,僅邊界風險。
- 修正:對被排除的 schema log info 一次;或於 `docs/Design-Base/04-databases` 登記「來源 schema 命名不得以 _view/_en 結尾」約束並在程式註解明載。
- 首次發現:2026-07-21

#### 🆕 [AD-130] 管理頁狀態膠囊字級低於規範地板,且未沿用既有 df-badge
- 檔案:`frontend/src/components/semantic/SemanticMappingManager.tsx:56`
- 內容:局部 StatusBadge 用 `text-xs font-medium md:text-sm`(桌機 14px),低於 `02-frontend/00-overview`「桌機表格內容最低 text-base」地板;專案已有 `df-badge` utility(globals.css:204)且 runs/schedules/users 膠囊全走它。
- 修正:className 改 `df-badge ${cls}`,刪手刻字級組合。
- 首次發現:2026-07-21

#### 🆕 [AD-131] 狀態切換使 total 縮水後 page 懸空 → 停在空頁顯示誤導「查無符合」
- 檔案:`frontend/src/components/semantic/SemanticMappingManager.tsx:316-334`(toggleStatus)、`505-518`
- 內容:statusFilter='draft' 停在末頁把最後幾筆轉「已確認」→ total 變小、page 未夾回 → 空頁 +「查無符合」誤導;逐筆審核流程高頻踩到。
- 修正:渲染前夾頁碼 — `!isFetching && page > totalPages` 時 `setPage(totalPages)`(或在 Pagination 元件統一夾,DatasetBrowser 一起受益)。
- 首次發現:2026-07-21

#### ⏸ 遺留 11 項(含 AD-104~108、R-DEP-005/002、R-ENV-004×2、R-SEC-004、R-LOG-006、CI 群,見前次報告)

### ⚪ Info(3 項)

- 🔄 [R-AI-001 記錄擴充] 內網連線資訊面擴大:除 tools/ script 外,入版控的 HTML 報告 header 含內網 DB IP + 高權帳號名(`bpm-metadata.html:25` `10.200.206.222 | 帳號 sa`、`hrm-metadata.html:32` 同、四份 erp-metadata `10.200.206.130` / sys / RO_M2201;無密碼)— RFC1918 + 帳號名同前次判定不成案,但這批是長存文件:**repo 對外(open source/外包)前須清洗 header**,記入遺留清單
- 🆕 [reflect 佐證] 新測試延續 module-level `os.environ` 硬覆寫 pattern(`test_semantic_mappings_api.py:24-30`、`test_snapshot_refresh_progress.py:24`)— 現況值一致無實害,但 pattern 持續擴散;屬歷史 reflect 候選「共用測試 DB 使用約定」的第 4 版佐證,本版不開 AD,待 reflect 決議收斂(conftest 統一注入 or pytest-env)
- ⏸ [07-testing] 測試建 schema 用 `create_all` 非 alembic(自 2026-07-06)

## 4. 修正優先序

### 立刻(部署前)
1. 🟠 AD-119 snapshot 進度 key 換 namespace(一行級,痛感/成本比最高)
2. 🟠 AD-121 輪詢面收斂(至少閒置降頻 + snapshot 合併 source/target;聚合端點可後補)— 疊在 502 實錘根因上,測試站部署 v1.5.1 前必處理
3. 🟠 R-SEC-002 / R-SEC-003 + AD-103 adminer(前次「立刻」清單維持)

### 本週(v1.5.1 收口建議)
4. 🟡 AD-120 + AD-122 合併修:SET NX 互斥 + sync-views 改 taskiq 202(順路一起)
5. 🟡 AD-123 audit log 三事件、AD-125 tables isError、AD-124 sticky 容器、AD-127 .gitignore 白名單(皆小改)
6. 🔵 AD-130 df-badge、AD-131 page 夾回、🟡 AD-126 combobox 脫鉤

### 有空
7. 🔵 AD-129 introspect 排除診斷 log;AD-128 停止累積 HTML(隨 AD-127 白名單自然達成);遺留群(前端測試/CI/env example 等)

## 5. 已跳過類別 / 規則與脈絡衝突註記

- 前端 i18n(R-FE-004)、inline 繁中 literal:單語系裁定沿用,不硬套
- 新測試以真實本地 PG 假扮 RDS(非 mock SQL):專案既定慣例,不硬套 R-TEST-004
- `count(*)` 用於 ~12k 列 semantic_mappings 與 group by 統計:不觸犯「大表禁 COUNT(*)」設計脈絡(該規則針對 ERP 750 表 row 探測)
- 測試 env fallback `changeme-development` 命中 R-ENV-001 樣式:development 預設已公開、production fail-fast 護欄擋,沿用前次不回報
- DEP 全類:零依賴變動,無新發現;GIT:兩 commit 均符 `(AI) <類型>:` 規範;`__pycache__` 未被追蹤(R-GIT-001 不成立)
- PII:7 個 HTML 以 pattern 全掃(password/jdbc/JWT/AKIA/身分證樣式/email/手機/樣本列),165+293 命中逐檔抽驗全為欄位名/表名 metadata 誤中,**無真值、無個資列**

## 6. AD-xxx(規則外發現)

本次新增 AD-119~AD-131(見第 3 章)。已巡視無發現的面向:
- **注入面**:semantic_admin_service/repo 識別字全走 quote_ident 白名單(不符即 raise)、值 bind params;english_name `^[a-z][a-z0-9_]*$`;view_generator 動態識別字全 quote_ident
- **權限**:8 個新端點全 `require_admin`,member 403 測試覆蓋;admin 頁前端守衛與既有 (main) 頁一致
- **時間型別通則**:RDS DDL/寫值全 naive + `AT TIME ZONE 'Asia/Taipei'`;副本 `to_tw` 無雙偏移;alembic v152 不觸時間欄
- **alembic v152**:新 revision 不改舊、鏈線性、USING CASE + UUID 正則無損轉型、downgrade round-trip、零 DROP
- **AD-111~118 回歸**:全數在位(rows 欄位交集、42P16 gated DROP、全成功才寫簽名、模組篩選後端化、activeModule 重置、IS NULL 篩選、modulesError)
- **前端紀律**:零 any、零原生 alert/confirm、無 localStorage token/dangerouslySetInnerHTML、三態+in-flight disable 主流程齊備、invalidatesTags 正確、輪詢終止條件與 TTL 兜底齊備、MappingRow memo、CollapsibleSection 抽出逐行等價、TableSearchCombobox 300ms debounce、關鍵字前後端語意對齊
- **錯誤處理**:detail 無 SQL/traceback/內部表名;log 無機密

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **patch 版本流程與 `05-version-bump` 矛盾(升規候選,user 已裁定)**:v1.5.1 以 patch 開 propose,推翻「新功能走 minor / patch 不寫 propose」— 待 reflect 決議修規則
2. **scan 檢查清單缺「表結構 vs `04-databases` 必備欄位型別比對」**(fixed.md §3 實證:updated_by text 雙重漏網)— 升規候選
3. **拆解階段對 propose 未指定型別應回查規範地板**(fixed.md §3 實證:拆解自行具體化 text)— 建議 `02-task-decomposition.md` 補條目,升規候選
4. **admin 寫入操作必寫 audit_logs 僅為程式慣例、未成文**(AD-123 實證:新模組漏掉無規則可對)— 建議 `03-backend` 補一條,可與 AD-123 修正同批
5. **來源 schema 命名保留字(`_view`/`_en` 後綴)未登記**(AD-129)— 修 AD-129 時順手落 `04-databases`

## 8. 掃描後補記(收口修正窗口)

- **[AD-132 🟠 已修]** `CREATE SCHEMA IF NOT EXISTS` 併發 race:掃描後 user 回報 ETL 同步撞 `pg_namespace_nspname_index`(Key=G2203)。根因:v1.4.0 多表並行同步下,同 schema 首次落地時多張表同時通過「不存在」檢查再搶建(PG 該語法非併發安全),搶輸者 IntegrityError 且整筆鏡像交易中止 → 該表記失敗。修正:`backend/app/etl/mirror.py` `write_mirror` 的 CREATE SCHEMA 以 SAVEPOINT(`begin_nested`)包裹並吞 IntegrityError 續行;回歸測試 `tests/test_mirror.py::test_write_mirror_swallows_schema_create_race`。屬 v1.4.0 併發化的遺留邊界,非 v1.5.1 新碼(前兩次 scan 均未涵蓋「DDL 併發安全」面向)。
- **修正落地**:AD-119~126、129~131 於本報告產出後同批修畢(AD-121/122 依 user 裁定走「從根收斂」:聚合 `GET /api/v1/progress` 單一輪詢 + sync-views 改 taskiq 202);AD-127/128 依 user 裁定不修(見各條裁定註記)。後端 320 passed / ruff 綠 / mypy 零新錯;前端 typecheck / lint / build 三綠。

---

> 本次 🔴 0 🟠 4 🟡 14 🔵 14 ⚪ 3;v1.5.1 新碼零 Critical,新增 🟠2 🟡8 🔵3 ⚪1。部署 v1.5.1 到測試站前,AD-119 + AD-121 建議必修(前者一行級、後者直接疊在 502 實錘根因上)— 已於收口窗口修畢(見第 8 章)。
