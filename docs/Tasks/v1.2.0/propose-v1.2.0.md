# Propose v1.2.0

> **草稿**:由 agent 依 user 口述整理,propose 由 user 認可後才生效(`01-propose/01-propose-format.md`);確認 / 修改後即可跑 `/propose-to-tasks`。

## 版本目標

把 v1.1.0「逐表登記的 config-driven ETL」演進為**自動偵測同步的 Raw → Hub 資料中心平台**。核心差異化(相對 Mage ETL):使用者**不必逐張 pipeline 登記**,系統連上來源即自動偵測所有 schema / table,一鍵同步到資料中心庫並依 ERP 資料字典自動掛中文 COMMENT。為降低對 RDS 的重複查詢,應用以**自有 DB 的 metadata 快照**為讀取來源(存 metadata,不存每筆 record),熱點查詢必要時走 Redis。對資料團隊的價值:原始資料 / 轉換後資料一目了然、同步一鍵完成、排程用友善 UI 而非看不懂的 cron 欄位。

## In Scope

- **原始資料管理頁(原始 Raw / `erp_migration_test`)**:依 schema 分組瀏覽來源資料表清單。**schema 選項需附說明文字**(如 DS = ERP 資料字典、M2201 = 業務資料),不可只有裸 tag。清單欄位:資料表、欄位數、資料筆數、**RDS 同步時間**、**ETL 轉換時間**、**同步按鈕**。**預設過濾資料筆數 = 0 的表**(可切換顯示)。**移除**逐表「查看欄位結構」功能。
- **ETL 資料管理頁(轉換後 Hub / `erp_etl_hub_test`)**:依 schema 分組瀏覽 ETL 轉換後資料表(命名同來源代碼、欄位帶中文 COMMENT)。
- **DB metadata 快照**:把來源 / 目標的**結構 metadata**(schema、table、欄位數、bounded 資料筆數、同步狀態時間)擷取後存入**自有 DB**;兩瀏覽頁一律讀快照,**不即時打 RDS**。提供「重整快照」動作(內省 RDS → upsert metadata)。資料筆數以 `SELECT 1 … LIMIT 1001` 探測,> 1000 顯示 `1000+`,禁 `COUNT(*)`。
- **Redis 快取**:對高頻 / 大量的 metadata 讀取(schema 清單、表清單分頁)加 Redis cache,降低自有 DB 與 RDS 壓力;快照重整或同步後失效對應 key。
- **自動鏡像 + DS 字典 COMMENT 轉換引擎**:內省來源所有非系統 schema / table → 目標端**保留來源真實型別** `CREATE SCHEMA/TABLE IF NOT EXISTS` + `TRUNCATE` + 分批 `INSERT`(禁 DROP、禁整表物化)→ 套 DS 字典中文 COMMENT。字典 join:表用 `DS.GAT_FILE`(`lower(GAT01)=表名` AND `GAT02='0'` 繁優先、缺退 `'2'` 简 → `GAT03`)、欄用 `DS.GAQ_FILE`(`lower(GAQ01)=欄名` AND `GAQ02='0'` → `GAQ03`)。**DS schema 優先同步**(字典先落地)。無字典對應者 COMMENT 留空。
- **同步觸發 + 狀態追蹤**:提供「同步」動作(全量 / 逐表);同步經 worker 執行,寫入 `sync_states`(每表 last_synced_at / last_transformed_at / row_count 快照)並落**執行紀錄**(沿用 etl_runs / etl_run_logs)。
- **每欄必帶 Comment 規範放寬**:自動鏡像路徑允許欄位無 Comment(來源 ERP 表多無 PG comment);對應 `docs/Design-Base` 規範調整走 `/reflect-rules` 記錄。
- **排程友善 UI**:排程**預設全部表都跑**;前端以下拉 / 輸入選頻率與時間(每日 / 每週 + 時:分等),**取代原始 cron 5 欄位輸入**(使用者看不懂「分 時 日 月 週」);後台仍可設計哪些跑、何時跑。既有 cron 內部表示可保留,UI 層負責雙向轉換。

## Out of Scope

- **資料異動日期偵測**:來源逐表 `MAX(<前綴>DATE)` 掃描以判斷異動 —— 本版**不做**,延後版本處理(欄位先不顯示)。
- **中文識別字改名**:hub 表 / 欄一律**保留原代碼**,中文只掛 COMMENT;不把識別字改成中文。
- **DS / M2201 以外 schema 的字典來源**:字典僅 GAT_FILE / GAQ_FILE;其他 schema 若無對應字典則 COMMENT 留空。
- **儲存每筆 record 於自有 DB**:自有 DB 只存 metadata 與同步狀態,**不**鏡像資料列(資料列只落目標 RDS hub)。
- **Coolify 正式部署 / AWS 機器建立**:本版以 **localhost 可跑**為準,不上 Coolify;部署由 user 人工處理。
- **通知 / 告警**、**水平擴充 / 分散式**:沿用 v1.1.0 Out of Scope。

## 對外承諾

- 後台登入後可:於**原始資料管理**依 schema(附說明)瀏覽來源所有資料表(預設隱藏 0 筆表)、於**ETL 資料管理**瀏覽轉換後資料表;兩頁讀自有 DB 快照,重整快照才打 RDS。
- 按「同步」→ worker 自動鏡像來源 → hub(保留型別)並套 DS 字典中文 COMMENT(繁優先);同步結果與逐表 log 可於執行紀錄查得;`sync_states` 記錄每表最近同步 / 轉換時間並反映於清單。
- DS schema 於同步時優先處理(字典先落地)。
- 排程 UI 不再要求輸入 cron 5 欄位:使用者用下拉 / 時間選擇即可建立排程;預設涵蓋全部表。
- localhost `docker compose up` 全服務健康;瀏覽頁與同步皆可於本機完成,不需上雲。

## 風險與相依

- **技術棧註記**:Redis 作為 cache(非僅 taskiq broker)為本版新增用途,經 user 明示採用;正式化規範走 `/reflect-rules` 補。
- **規範衝突**:「每欄必帶繁中 Comment」為 v1.0/v1.1 底線,本版自動鏡像放寬為「可留空」,屬設計規範調整,須 `/reflect-rules` 記錄並經 user 認可。
- **效能風險**:來源 DS 2456 表 / M2201 2291 表(≈ 4747 表、~10 萬欄),全量同步為大規模 RDS 寫入;需分批串流(禁整表物化)、DS 優先、可逐表 / 分批同步;全量前先小規模試跑驗證。
- **RDS 寫入屬對外不可逆動作**:目標 `erp_etl_hub_test` 已建;同步為 TRUNCATE + 重灌(禁 DROP);全量跑前 user 確認。
- **前置相依**:來源 `erp_migration_test` 可讀(已驗)、目標 `erp_etl_hub_test` 可寫(已建空庫)、Redis 可用;RDS 連線走 `.env` 的 `AWS_RDS_*`(未進 git)。

## 驗收標準

- 原始資料管理頁:讀自有 DB 快照列出來源 schema(附說明文字)與資料表;預設不顯示 0 筆表,切換後可見;無「查看欄位」按鈕;清單含 RDS 同步時間 / ETL 轉換時間欄與同步按鈕。
- 「重整快照」後,自有 DB 的 metadata 表筆數 = 來源實際表數(DS 2456 / M2201 2291);瀏覽頁不再逐次打 RDS(可由 RDS 連線數 / log 佐證)。
- 按「同步」某張非空表 → 執行紀錄出現一筆 run 且狀態成功;`erp_etl_hub_test` 對應 schema.table 有資料,且欄位 COMMENT 取自 GAT/GAQ 繁中字典(如 `AAA_FILE` 表註解「帳別參數檔」、`AAA01` 註解「帳別編號」);`sync_states` 該表 last_synced_at 更新。
- DS schema 於全量同步時排在其他 schema 之前處理(log 順序可證)。
- 排程頁可不輸入 cron 字串、僅用下拉 / 時間選擇建立一筆排程,且到點正常觸發(內部 cron 由 UI 轉換產生)。
- Redis 快取生效:重複開啟同一 schema 表清單第二次不再查自有 DB(或 RDS);快照重整 / 同步後對應 cache 失效。
- localhost `docker compose up` 全服務健康;全流程(瀏覽 → 同步 → 查看轉換結果)本機可完成。

---

## 背景參考(非 scope,供拆 task 對照)

- **已落地(dev-v1.2/auto-sync)**:原始 / ETL 資料管理雙瀏覽頁與 RDS 結構內省 API(`app/etl/introspect.py`、`app/api/v1/datasets.py`、前端 `DatasetBrowser`)已於 commit `cf9d324` / `1918932` 完成;本版於其上補強(改讀快照、加時間欄 / 同步鈕 / 過濾 / schema 說明、移除查看欄位)。
- **DS 字典 join 已實測**:`GAT_FILE`(表名→中文,GAT02 語系)、`GAQ_FILE`(欄名→中文,GAQ02 語系 0=繁 2=简),繁優先缺退简;`AAA_FILE`→帳別參數檔、`AAA01`→帳別編號。
- **既有 ETL 引擎**:`app/etl/{engine,reader,writer,comments}.py`(config-driven,逐表 COMMENT);自動鏡像為**新路徑**,型別保留與 comment 放寬與既有粗型別 / 強制 comment 不同,需獨立模組。
- **RDS 連線**:`.env` `AWS_RDS_*`(source `erp_migration_test` / target `erp_etl_hub_test`,同實例共用 HOST/PORT/USER/PASSWORD);localhost 直連可用。
- **服務**:frontend / backend / worker / scheduler / redis / 自有 postgres;image `etl_` prefix。
