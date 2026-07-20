# Propose v1.5.0

> 版本目標與 scope 已由 user 口述、agent 整理(2026-07-20);**user 認可後生效**(`01-propose/01-propose-format.md`),之後即可跑 `/propose-to-tasks`。

## 版本目標

建立**欄位語意層**:對外 JSON 與 SQL/BI 消費者不再面對鼎新魔術文字(`gen01`),而是語意化英文名(`employee_number`),同時補齊 ETL 中文 comment 的覆蓋缺口與模組分類。價值對象:介接資料中心的下游系統(拿到正常 key 的 JSON)、直連查詢的 SQL/BI 使用者(語意化 view)、資料維運(comment 更完整、表可按 ERP 模組分類)。

## In Scope

### A. 欄位語意層(英文名) — 方案 1「鏡像不動 + mapping 驅動語意層」(已定案,否決實體改 column name)

- **A1. RDS mapping table(全域、不分 schema)**:於目標 RDS 建獨立 schema `erp_metadata`,單一表 `semantic_mappings`(PK=`table_name+column_name`;`column_name=''` 代表表層級映射(表英文名),其餘為欄位映射;欄位含 `english_name`/`zh_name`(GAQ03/GAT03 帶入)/`status`(draft/confirmed)/`updated_by`/`updated_at`)。帳套 schema 同構、字典全域(同 DS 字典設計),**mapping 只維護一份,不因 schema 重建**;例外 override 表本版不做。
- **A2. 英文名草稿→複核流程**:先只挑 JSON 會回傳的表(首批清單由 user 提供),由 GAQ 中文名批次產英文草稿(`status='draft'`),人工複核後轉 `confirmed`;未 confirmed 欄位不出現在對外輸出。本版複核以腳本/SQL 進行,不做後台編輯 UI。
- **A3. JSON key 轉換**:API 依 confirmed mapping 回傳英文 key(`gen01`→`employee_number`)。
- **A4. view 產生器**:迴圈各帳套 schema,以同一份 mapping 對實際存在的表 `CREATE OR REPLACE VIEW <schema>_en.<english_table>`;schema 差異只在 view 層處理。
- **A5. mapping 副本同步回系統**:RDS `erp_metadata.semantic_mappings` 為唯一事實來源;ETL 同步時單向同步回 backend 自有 DB 本地副本(小表,免增量、整表重灌),JSON API 讀本地副本(同 `rds_table_meta` 快照模式,不即時打 RDS)。同步後失效轉換 cache;view 重生掛同一時點(mapping 有異動才重生)。禁雙向同步。
- 實作注意:mapping 寫入走獨立 RDS 連線/權限(backend 自有 DB 與 RDS 分離);mirror TRUNCATE+INSERT 不受 view 影響,未來欄位型別 ALTER 需先重建 view。

### B. ETL 字典/comment 補強(來源=ERP 字典分析 `docs/ERP-Analyze/mapping-alignment.md`)

- **B1. 欄位 comment 缺漏 fallback**:GAQ 缺中文名時退 `DS.GAE_FILE` 畫面標籤(GAQ 缺 191 欄中可補 126 欄)。**前置**:DMS 複寫加 `GAE_FILE` + 來源帳號授權(`RO_M2201` 現僅被授權 `GAT/GAQ/PAT_FILE`);前置未成則本項順延,不阻塞 A。
- **B2. 資料集頁模組分類**:以 `GAT_FILE.GAT06` 模組代碼分類/篩選資料表(欄位已在現行複寫表內,無前置)。
- **B3.(可選)欄位說明/選項值增強**:`GAQ_FILE.GAQ04/05`(欄位說明與選項代碼意義)補進欄 comment,現行只用 GAQ03 中文名。

## Out of Scope

- **實體改 column name**(已否決:破壞自動內省同步、無英文命名來源、斷 ERP 對照)。
- **表↔ERP 作業對應(ZR/GAZ)、GAU 邏輯 FK / 單頭單身關聯展示** — 作業流程/展示類,與 ETL 資料職責無關(ERP 分析 §5.2 確認)。
- **多帳套同步範圍擴充**(SDF/GDF/MDF/DF) — 屬 DMS / Phase 3 資料湖範疇,另案決策。
- **mapping override 表**(同名欄位跨帳套語意不同的例外) — 遇到再做。
- **後台 mapping 編輯 UI** — 本版複核走腳本/SQL,UI 視 v1.6 需求再議。
- 背景參考候選未圈選者(進度條、SSO 姓名、502 修法、v1.4.0 遺留)。

## 對外承諾

- 指定表的 JSON API 回傳 key 一律為 confirmed 英文名;未 confirmed 欄位不出現在回傳(不外流草稿名/魔術名)。
- 各帳套提供 `<schema>_en` 語意化 view 供 SQL/BI 直查。
- mapping 異動於「下一次 ETL 同步完成後」生效(API 副本 + view 重生同一時點)。
- comment 覆蓋:GAQ 缺漏 191 欄降至 ≤65(B1 前置達成時)。

## 風險與相依

- 技術風險:英文命名主觀性 → 複核可能成為瓶頸(以「先只翻 JSON 回傳表」控量);view 依賴會擋未來欄位型別 ALTER(先重建 view 即可)。
- 第三方依賴 / 跨團隊阻塞:B1 需 DMS 加 `GAE_FILE` 複寫 + `RO_M2201` 授權(DMS 目前同步進行中,需與負責方協調);`erp_metadata` schema 建立需 RDS 權限。
- **同步範圍未決(ERP 分析 §1)**:來源 Oracle 有多個公司帳套,`SDF`(5,919 萬列)/`GDF`(4,937 萬)/`MDF`/`DF` 資料量皆大於 `M2201`(755 萬);是否納入其他帳套屬 scope 決策,連動 Phase 3 資料湖 750 表盤點(本版不擴,僅記錄)。
- **無 PK 表 32/333(ERP 分析實查)**:本專案增量為「表級計數器比對+變動表整表重灌」,不依賴 PK,無阻斷;但 (a) `TLF_FILE`(85 萬列)等異動記錄大表幾乎每日變動,每次整表重灌成本最高;(b) 上游 DMS CDC 對無 PK 表的 update/delete 有重複/漏更風險,可作為「750 表同步失敗根因」排查線索之一。
- **本專案跑法**:改碼後以 `docker compose up -d --build` 驗證(禁 start-dev)。

## 驗收標準

- RDS 存在 `erp_metadata.semantic_mappings`,首批 JSON 回傳表的草稿已匯入(含 `zh_name` 帶入與 `status`)。
- 手測:任一 confirmed 表的 JSON API 回傳 key 為英文名(如 `gen01`→`employee_number`),未 confirmed 欄位不出現。
- view 產生器對至少一個帳套產出 `<schema>_en` view,SQL 查詢可得英文欄名;mapping 更新後重跑產生器,view 定義同步更新。
- ETL 同步 job 完成後,自有 DB 副本與 RDS mapping 一致,轉換 cache 已失效。
- 資料集頁可按 GAT06 模組分類/篩選(B2)。
- B1(若前置達成):同步後 comment 缺漏欄數 ≤65。
- 後端/前端測試全綠;`docker compose up -d --build` 手測通過。

## 變更紀錄

- 2026-07-17:建立 v1.5.0 骨架,scope 待 user 決定。
- 2026-07-20:依 ERP 字典分析(docs/ERP-Analyze/)補入「執行期字典擴充」In Scope 候選,待 user 認可。
- 2026-07-20:與 erp-metadata 報告全面比對後,補入可選候選 2 條(GAQ04/05 說明值、單頭單身關聯併入 GAU 條目)與風險 2 條(多帳套同步範圍未決、無 PK 表 32 張);作業流程/畫面異動別(報告 §5.2)確認與 ETL 無關,不納入。
- 2026-07-20:與 user 討論定案「欄位語意層(英文名)」方向 — 採方案 1(鏡像不動 + RDS 全域 mapping table + JSON key 轉換/view 產生器),否決實體改 column name;mapping 落點 `erp_metadata.semantic_mappings`,不分 schema,schema 差異僅在 view 層處理;副本單向同步回自有 DB。
- 2026-07-20:整理為正式 propose — In Scope 收斂為「A. 欄位語意層 + B. ETL 字典/comment 補強」,作業流程展示類/多帳套擴充/編輯 UI 列 Out of Scope;補版本目標/對外承諾/驗收標準,待 user 認可。

---

## 背景參考 — 既有待辦候選(非 scope,僅供 user 圈選)

以下為先前版本累積、尚未排入任何版本的候選項目;要納入本版者請移入 In Scope:

- **同步進度條**:任何同步操作要有進度條;執行模型調查與設計方向已完成,待走 propose-to-tasks。順帶修 runs 手動觸發按鈕 404。
- **儀表板 / Header 顯示 SSO 姓名**:`display_name` 欄位已加(e7a101c)但未填入 SSO name,目前仍顯示 email。
- **測試站間歇 502 修法**:輪詢 × 每請求回源 SSO 驗證打爆中央 rate limit(429 被 `df_sso.py` 轉 502);修法待決議(本地 TTL 快取 vs SSO 契約調整)。
- **v1.4.0 遺留**:adminer 外露、rate limit、殭屍 run 清理、750 表同步失敗根因。
- **升規候選 15 條**(260706×8 + 260709×4 + 260710×3)全未決議 — 屬 `/reflect-rules` 決議流程,不必占版本 scope。
- **UI 視覺 3 項人工複測**(v1.4.1 角色回退後):Sidebar admin-only / member 直開 `/users` 導 no-access / 自己那列下拉停用。
