# fixed.md — v1.5.0

> 收口補登(2026-07-20):以下條目由 orchestrator 依各 worker 回報與 scan 修正紀錄補登(worker 執行當下未即時寫入)。

## §1 — 語意副本同步(附加步驟)波及既有 mirror_sync 測試

- **時間**:2026-07-20T05:30+08:00
- **commit / PR**:`e987203`
- **影響檔案**:`backend/app/worker/tasks.py`、`backend/tests/test_mirror_sync_parallel.py`(未改,受害方)
- **問題**:task-003 初版把「語意映射副本重灌」接進 `mirror_sync` 後,7 個既有 FakeSession 測試(`test_mirror_sync_parallel.py`/`test_mirror_sync_tables_v131.py`)`AttributeError` 失敗
- **根因**:兩個系統性原因疊加 —(a)測試環境的 `AWS_RDS_*` env 是 module-level 全域覆寫(pytest 收集階段即生效),FakeSession 測試因此仍連得到真測試 RDS 讀到列;(b)附加步驟初版 graceful 範圍只包「來源缺表」,未涵蓋「本步驟任何失敗」,附加流程的失敗邊界未定義即上線
- **修正**:整段「副本重灌」包單一 `try/except Exception` log warning 略過,定位為「附加同步,不得波及主流程」(`e987203`)
- **規範參照**:`docs/Design-Base/03-backend/07-testing.md`(共用測試 DB 慣例;規範未涵蓋 module-level env 覆寫的跨檔副作用)
- **後續**:佐證既有 reflect 候選(260709 候選 2「並行 worker 測試 DB 使用約定」、260710 候選 2「共用測試 DB schema/seed 同步」);「附加流程失敗語意」列 reflect 觀察名單(見 §4)

## §2 — 拆解 affected_files 誤植與分層必經檔遺漏

- **時間**:2026-07-20T06:10+08:00
- **commit / PR**:`cc72cbe`
- **影響檔案**:`docs/Tasks/v1.5.0/tasks/task-007-module-classify-backend.md`、`backend/app/schemas/rawdata.py`、`backend/app/repositories/rds_table_meta_repo.py`
- **問題**:task-007 的 affected_files 列了不存在的 `backend/app/schemas/dataset.py`(實際為 `rawdata.py`);且依 `03-backend/00-overview.md` 分層規則結構性必經的 `rds_table_meta_repo.py` 未列入白名單,worker 需自行揭露偏離
- **根因**:orchestrator 拆解時 affected_files 憑 API 模組推測命名、未逐一驗證路徑存在性;也未依分層規則推導「service 改動必經的 repo 層檔案」— 白名單生成缺一道「存在性 + 分層必經」檢查
- **修正**:worker 揭露後改於正確檔案實作,orchestrator 於 `tasks-v1.5.0.md` 補記更正(`cc72cbe`)
- **規範參照**:`docs/Design-Base/01-propose/02-task-decomposition.md § 拆解禁忌`(affected_files 精確路徑)
- **後續**:佐證既有 reflect 候選(260706 候選 1「規範連動檔納入 affected_files」、260710 候選 1「白名單 × 規格演進同步紀律」)

## §3 — RDS 目標庫時間型別規範缺漏被推翻:一律 naive timestamp(datetime2 等價)

- **時間**:2026-07-20T07:20+08:00
- **commit / PR**:`648a092`
- **影響檔案**:`backend/app/etl/semantic_schema.py`、`backend/app/etl/mirror.py`、`backend/scripts/seed_semantic_mappings.py`
- **問題**:task-001 依 propose 字面把 `semantic_mappings.updated_at` 建為 `timestamptz` 並已在真實 RDS 落地;user 隨後決議「RDS PG 上時間型別一律 MSSQL datetime2 等價(naive timestamp),值存 UTC+8」,mirror 引擎的 timestamptz/timetz 保留分支同屬違反
- **根因**:`04-databases/06-timezone.md` 只規範自有 DB(naive TIMESTAMP +08),**未涵蓋目標 RDS 的 DDL 時間型別**;propose/task 撰寫時無規則可依,預設沿用 PG 慣用 timestamptz,與資料平台實際慣例(DMS 產出即 naive)不一致
- **修正**:semantic_schema 改 timestamp + `now() AT TIME ZONE 'Asia/Taipei'` DEFAULT,含既有表冪等 ALTER 轉型保資料;mirror 帶時區來源型別 DDL 正規化 + 寫入值轉 UTC+8 naive;seed 兩處 now() 轉時區(`648a092`)
- **規範參照**:`docs/Design-Base/04-databases/06-timezone.md`(缺目標 RDS 條目 — 規範缺漏)
- **後續**:**reflect 候選(升規)** — `06-timezone.md` 補「目標 RDS 時間型別一律 naive timestamp(datetime2 等價)+ UTC+8」條目

## §4 — view 重生流程失敗語意不足:重建先毀後建 + 部分失敗仍記成功簽名

- **時間**:2026-07-20T08:00+08:00
- **commit / PR**:`0f2ad6e`(發現於 scan AD-112/AD-113)
- **影響檔案**:`backend/app/etl/view_generator.py`
- **問題**:(a)REPLACE 失敗一律走 DROP VIEW+CREATE,任何非相容性錯誤也會先毀掉可用 view,CREATE 再失敗即 view 消失;(b)單表失敗僅 warning,簽名照寫,下輪「內容未異動」直接跳過,缺的 view 長期化
- **根因**:重生流程只設計 happy path,未定義失敗狀態機 — 「先破壞後建設」無回退、「成功狀態」在部分失敗時過早記錄;與 §1 同類:附加/背景流程的失敗邊界未在設計期明確化
- **修正**:重建僅限 SQLSTATE 42P16(欄位不相容)觸發,其餘例外保留原 view;`generate_views` 回報失敗清單,全成功才寫簽名(`0f2ad6e`)
- **規範參照**:無對應規則(規範缺漏)
- **後續**:與 §1 併列 reflect 觀察名單「附加型背景步驟的失敗語意」(同版本 2 條,未達跨版本門檻)

## §5 — rows 端點未與實體欄位取交集:同一資料兩個消費端健壯性不一致

- **時間**:2026-07-20T08:00+08:00
- **commit / PR**:`0f2ad6e`(發現於 scan AD-111)
- **影響檔案**:`backend/app/services/data_query_service.py`
- **問題**:confirmed mapping 的兩個消費端行為分歧 — view_generator 有「實際欄位 ∩ confirmed」交集保護,data_query 直接拿 confirmed 欄組 SELECT;實體 ERP 欄位漂移時前者跳過、後者 500
- **根因**:「以靜態映射查動態實體」的漂移防禦是通用需求,但兩個 task(004/005)由不同 worker 平行實作,無規則要求對外查詢前驗證識別字存在於實體 — 健壯性慣例散落在個別實作品味
- **修正**:query_rows 組 SQL 前查 information_schema 取交集,空交集走 404(`0f2ad6e`)
- **規範參照**:`docs/Design-Base/04-databases/04-sql-safety.md`(白名單涵蓋注入面,未涵蓋「白名單本身過期」的漂移面)
- **後續**:reflect 觀察名單(單版本單條;若後續版本再現同類漂移缺陷再升規)

## §6 — 前端模組篩選:衍生 UI 狀態與後端查詢能力邊界不同步

- **時間**:2026-07-20T08:30+08:00
- **commit / PR**:`0e809d9`(發現於 scan AD-115/116/117)
- **影響檔案**:`frontend/src/components/datasets/DatasetBrowser.tsx`、`frontend/src/lib/api/datasetApi.ts`
- **問題**:(a)篩選選項由當頁 50 筆聚合,分頁外模組篩不到;(b)受控 select 的選定值在選項重算後失效,呈現空白但仍隱形過濾;(c)「未分類」前端過濾與後端分頁統計語意脫節
- **根因**:task-008 在後端只有等值篩選的前提下用「前端聚合 + 前端過濾」補功能缺口,衍生狀態(選項/選定值/分頁)各自來源不一致 — 跨 task 的 API 能力缺口(distinct 清單、null 篩選)在拆解期未被識別為後端職責
- **修正**:後端補 modules 端點與 `__unclassified__` null 篩選(`0f2ad6e`),前端改吃後端 distinct、失效重置、移除前端過濾(`0e809d9`)
- **規範參照**:`docs/Design-Base/02-frontend/02-api-and-state.md`(未涵蓋「篩選選項/能力應由後端供給」)
- **後續**:reflect 觀察名單;佐證 260706 候選 2「跨 task 介面契約指派唯一 owner」(篩選能力的前後端契約無 owner)
