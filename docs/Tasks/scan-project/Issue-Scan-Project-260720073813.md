# Issue Scan — data-center-etl(260720073813)

> 掃描時間:2026-07-20(UTC+8)|範圍:v1.5.0 全部新碼(e4b736c..44f090c,task-001~009)+ 前次遺留存續確認|方法:三區域(後端/前端/ENV·GIT·DEP)並行掃描彙整
> 註:掃描基準為 44f090c;掃描進行中另依 user 指示落地「RDS PG 時間型別一律 naive timestamp(datetime2 等價)」修正(648a092),不在本報告發現範圍內,見第 7 章升規備註。

## 0. 與前次差異(前次:Issue-Scan-Project-260710131118.md)

前次 🔴0 🟠2 🟡6 🔵12 ⚪3 → 本次 🔴0 🟠2 🟡9 🔵14 ⚪3。

- 🆕 新增 8 項(全部來自 v1.5.0 新碼,無 Critical/High):AD-111~AD-115(後端語意層健壯性 3🟡 + 效能 1🔵)、AD-116~AD-118(前端模組篩選一致性 2🟡 3🔵 中取問題級別者)
- ✅ 已修 0 項
- ⏸ 仍在 21 項(前次全部遺留逐項確認存續;其中 4 項所在檔案 v1.5.0 有動但目標關切未處理:AD-101/AD-102(worker/tasks.py 增的是語意映射功能)、R-ENV-002(.gitignore 增的是 ERP 排除)、R-TEST-001(前端有動但無測試新增))
- 🔄 變化 0 項

## 1. 總覽

| 項目 | 值 |
| --- | --- |
| 嚴重度統計 | 🔴 0 🟠 2 🟡 9 🔵 14 ⚪ 3(🟠 全為前次遺留;v1.5.0 新碼零 Critical/High) |
| 結論 | v1.5.0 語意層新碼在注入面、權限、分層、機密、交易硬規則上全數乾淨(rows 端點識別字流白名單完整);新發現集中在「confirmed 映射 vs 實體 schema 漂移」的健壯性、view 重生維運盲點、前端模組篩選的資料一致性 — 皆屬 🟡 級互動/維運正確性,不擋合併 |

## 2. 專案摘要

- 目標:ERP Oracle → DMS → RDS PG 的資料中心 ETL;v1.5.0 新增欄位語意層(erp_metadata.semantic_mappings 全域 mapping + JSON 英文 key API + 各帳套 `<schema>_en` view)與字典補強(GAE fallback/GAQ04-05/GAT06 模組)
- 技術棧:Next.js 16 + TS strict / FastAPI + SQLAlchemy 2 async / PostgreSQL(自有 DB + 目標 RDS)— 對照 CLAUDE.md 鎖定棧一致
- Task 進度:v1.5.0 9/9 done(tasks-v1.5.0.md),verification-v1.5.0.md 真實 RDS 端到端通過,對外承諾 4/4
- 測試:後端 282 passed(本掃描時點);前端 lint/typecheck/build 綠、零測試(R-TEST-001 ⏸)

## 3. 詳細發現(依嚴重度;⏸ 遺留項僅列 ID,細節見前次報告)

### 🟠 High(2 項,皆 ⏸)

- [R-SEC-002] login rate limit(`backend/app/api/v1/auth.py`)— ⏸ 自 2026-07-06
- [R-SEC-003] 安全 headers(`backend/app/main.py` / `frontend/next.config.ts`)— ⏸ 自 2026-07-06

### 🟡 Medium(9 項:6 ⏸ + 3 🆕)

#### 🆕 [AD-111] rows 端點未驗證 (schema,table) 共存、未與實際欄位取交集 → mapping 漂移即 500
- 檔案:`backend/app/services/data_query_service.py:59-70`、`99-121`
- 內容:`get_confirmed_map(table_name)` 全域查(不綁 schema);`columns = sorted(column_map)` 直接進 SELECT,未與 `information_schema.columns` 實際欄位取交集。實體 ERP 欄位改名/移除後,SELECT 直接拋 Postgres 例外 → 500(無洩漏但功能對該表壞掉)。對照 `view_generator.select_view_columns:122-131` 有交集保護,兩處健壯性不一致。
- 修正:`query_rows` 組 SQL 前查該 `(schema, table)` 實際欄位集合,`columns` 取交集;交集空或表不存在走既有 `_NOT_AVAILABLE_DETAIL` 404。
- 首次發現:2026-07-20

#### 🆕 [AD-112] view 重建分支 DROP VIEW 後 CREATE 失敗 → 語意 view 永久消失
- 檔案:`backend/app/etl/view_generator.py:165-177`(外層 202-213)
- 內容:`_create_or_replace_view` 對任何 REPLACE 失敗(含權限/暫時性錯誤)都走 `DROP VIEW IF EXISTS` + `CREATE VIEW`;AUTOCOMMIT 下 DROP 立即生效,後續 CREATE 失敗僅 warning,view 消失且下輪可能被簽名抑制不重試(見 AD-113)。
- 修正:僅在確認欄位集合不相容(42P16)時走重建;或改「先建新驗證成功才卸舊」順序。
- 首次發現:2026-07-20

#### 🆕 [AD-113] 部分 view 產生失敗仍寫入內容簽名 → 抑制後續重試
- 檔案:`backend/app/etl/view_generator.py:237-260`(單表吞例外 212-213)
- 內容:單表失敗 warning 略過後,`regenerate_views_if_changed` 仍無條件 `cache_set(_SIGNATURE_CACHE_KEY, signature)`;下輪 `cached == signature` 直接跳過,缺的 view 長期缺到 confirmed 內容再變動。
- 修正:`generate_views_for_schema` 回報失敗清單;僅全部成功才寫簽名。
- 首次發現:2026-07-20

#### ⏸ 遺留 6 項(見前次報告):AD-102 同表並發防疊、R-FE/UX 與其他 🟡 4 項

### 🔵 Low(14 項:11 ⏸ + 3 🆕)

#### 🆕 [AD-114] rows 查詢 ORDER BY 全欄 + offset 無上限,共用小連線池(pool 2+3)
- 檔案:`backend/app/services/data_query_service.py:112-121`、`backend/app/etl/introspect.py:38`
- 修正:排序改單一穩定鍵;offset 加上界(如 `le=100000`)或 keyset 分頁。
- 首次發現:2026-07-20

#### 🆕 [AD-115] 模組下拉選項只從第 1 頁(50 筆)聚合,分頁外模組無法被篩選
- 檔案:`frontend/src/components/datasets/DatasetBrowser.tsx:506-518`、`531-548`、`825-829`
- 內容:選項來源(當頁 50 筆 distinct)與後端跨全頁等值篩選能力不對稱;schema 表數 >50 時,他頁才有的模組列不進下拉(「未分類」選項同理)。`nameSuggestions(519-528)` 同限制。
- 修正:後端提供 distinct module 清單端點,或聚合查詢用專用 aggregate/夠大 pageSize。
- 首次發現:2026-07-20

#### 🆕 [AD-116] `activeModule` 不隨進階篩選變動重置 → 隱形過濾
- 檔案:`frontend/src/components/datasets/DatasetBrowser.tsx:146-148`、`578-581`
- 內容:進階篩選重算後選定代碼掉出 `moduleOptions` 時,受控 select 顯示空白但後端仍以舊代碼過濾;使用者見「沒篩卻沒資料」。切 schema 有重置(562-567),切篩選沒有。
- 修正:`updateFilters` 內偵測 `activeModule` 不在最新選項即重置 null。
- 首次發現:2026-07-20

#### 🆕 [AD-117] 「未分類」前端過濾與分頁筆數/空狀態訊息語意誤導
- 檔案:`frontend/src/components/datasets/DatasetBrowser.tsx:903-909`、`997-1010`
- 內容:某頁 50 筆內剛好無 null 列時顯示「查無符合」,他頁其實有;分頁總數為全 schema 統計(worker 已加提示文字部分緩解)。
- 修正:後端補 `module_code IS NULL` 篩選(治本);短期空頁訊息區分「本頁無/整體無」。
- 首次發現:2026-07-20

#### ⏸ 遺留 11 項(含 AD-108 ck_users_role 等,見前次報告)

### ⚪ Info(3 項)

- 🆕 [AD-118] 模組選項/combobox 建議來源查詢靜默吞錯(`DatasetBrowser.tsx:506` 未取 `isError`)+ 空狀態指引不涵蓋 module(`resetFilters:583` 不清 `activeModule`、`activeFilterCount:550` 不計入)— 次要控件退化不崩潰,合併記一項
- ⏸ [07-testing] 測試建 schema 用 `create_all` 非 alembic(自 2026-07-06)
- 🆕 [R-AI-001 記錄] ERP 分析工具內網 IP 硬編碼(`docs/ERP-Analyze/tools/*`)— RFC1918 位址、一次性分析工具既知脈絡,不構成問題級別,僅記錄

## 4. 修正優先序

### 立刻(部署前;與前次一致)
1. 🟠 R-SEC-002 login rate limit、🟠 R-SEC-003 安全 headers(前次遺留)
2. AD-103 production adminer 外露、AD-101 殭屍 run 清理(前次「立刻」清單維持)

### 本週(v1.5.0 收口補洞建議)
3. 🟡 AD-111 rows 欄位交集驗證(語意層招牌功能的健壯性)
4. 🟡 AD-112 + AD-113 view 重生健壯性(合併修:縮小重建觸發 + 全成功才寫簽名)
5. 🔵 AD-116 activeModule 重置(前端一行級修正,痛感/成本比最高)

### 有空
6. 🔵 AD-114 rows 分頁上界、AD-115 模組選項聚合、AD-117 未分類 null 篩選(可併成一個「模組篩選 v2」小 task)

## 5. 已跳過類別 / 規則與脈絡衝突註記

- 前端 i18n(R-FE-004):專案無 i18n 框架、既有慣例即 inline 繁中 → 不硬套
- rows 回應 `{rows,total_returned,columns}` 非標準 `{items,total}`(R-BE-011):禁 COUNT(*) 設計下無法給 total,屬有脈絡合理偏離 → 不列violation
- `replace_all` 副本整表 DELETE+INSERT(R-DB 軟刪除):replica 語意已文件化 → 不列
- alembic downgrade drop(R-DB-012):round-trip 必要例外,僅撤本次新增 → 不列
- LOG/DEP/PII/GIT 全類:掃畢無新發現(依賴零新增、.env 未曾入庫、機密脫敏無回歸、gitignore 對 ERP data/html/db.properties 完全有效)

## 6. AD-xxx(規則外發現)

本次新增 AD-111~AD-118(見第 3 章)。已巡視無發現的面向:注入面(rows 識別字流完整白名單:Literal dataset + 快照 schema 集合 + confirmed 表名 + quote_ident 正則)、錯誤洩漏(404 統一訊息不回打輸入)、權限(全端點 require_admin 非僅前端)、log 機密(mask_secrets 全覆蓋)、TODO 殘留(零)、re-render(TableRow memo/useCallback 完備)、未分類 sentinel 撞名(雙底線哨符,機率極低)。

## 7. 規範自身問題(Design-Base 矛盾 / 缺漏)

1. **RDS 端時間型別規範缺漏(升規候選)**:user 於本掃描期間決議「RDS PG 上時間型別一律 naive timestamp(MSSQL datetime2 等價),值存 UTC+8」並已落地(648a092:semantic_schema 含既有表冪等轉型、mirror 型別正規化+值轉換、seed now() 轉時區)。`04-databases/06-timezone.md` 目前只涵蓋自有 DB,建議 `/reflect-rules` 時補「目標 RDS 時間型別」條目。
2. task 拆解 affected_files 誤植(schemas/dataset.py 實為 rawdata.py)已於 tasks-v1.5.0.md 更正 — 流程面無規範矛盾。

---

> 本次 🔴 0 🟠 2 🟡 9 🔵 14 ⚪ 3;v1.5.0 新碼零 Critical/High。**需要我幫你修「本週」清單(AD-111/112/113 + AD-116)嗎?**
