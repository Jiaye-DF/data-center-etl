# Propose v1.3.1

> **草稿**:由 agent 依 user 口述整理,propose 由 user 認可後才生效(`01-propose/01-propose-format.md`);確認 / 修改後即可跑 `/propose-to-tasks`。

## 版本目標

修正 v1.3.0 排程模型的設計缺口:v1.3.0 採「全表統一排程 + 逐表排除」,並為此多出一個「排程涵蓋」頁(`/schedules/coverage`)——排程本體(cron 條目)與逐表狀態(涵蓋 / 排除)被拆在兩頁、兩套機制(`schedules` 條目 vs `rds_table_meta.sync_excluded`)。本版把排程模型**單一化為「一張原始資料表 ↔ 一筆排程」**:RDS 快照同步時**自動為每張來源表建立專屬排程**(預設每天 00:00:00、預設**停用**),排程管理頁本身就是逐表檢視——「排程涵蓋」頁與逐表排除機制因此**整個移除**(功能由排程管理頁涵蓋);排程管理 UI 同步改版,樣式對齊原始資料管理(`/sources`)與 ETL 資料管理(`/sources-hub`)的 schema 分頁籤 + 表清單瀏覽器。

## In Scope

- **排程模型改為一表一排程**:`schedules` 加 `source_schema` / `source_table` 欄位(對應 `rds_table_meta` 的來源表;加 partial unique index `(source_schema, source_table) WHERE is_deleted = false`);一筆排程只管一張表。`etl_table_pid`(v1.1 config ETL 遺留)不再使用,**保留欄位、標記 deprecated**(禁 DROP COLUMN)。
- **快照同步自動建立排程**:`SnapshotService.refresh`(dataset=source)完成 metadata upsert 後,對**每張沒有排程的來源表自動新增一筆**:`name = "<schema>.<table>"`、`cron_expr = "0 0 * * *"`(每天 00:00:00,UTC+8)、`is_enabled = false`(**預設全部停用**)、來源表欄位填齊。來源表消失 → 對應排程**軟刪除**(表回來時重建,沿用預設值)。
- **既有資料一次性收斂(migration + backfill)**:
  - 為當前 `rds_table_meta`(dataset=source、未刪除)所有表 backfill 一表一排程(預設值同上)。
  - v1.3.0 建立的「全表增量」排程條目**軟刪除**(其行為由新模型取代;不做硬刪)。
  - `sync_excluded` 逐表排除機制**廢止**:欄位保留(禁 DROP COLUMN)、程式面停止讀寫;其語意由「該表排程 `is_enabled`」取代(本版預設全停用,原排除名單無需搬移)。
- **排程派工改依表分組**:`scheduler.py` 改為——讀取啟用且未刪除的排程,**依 `cron_expr` 分組**,同一 cron 的表合併派一發 `mirror_sync(incremental=True, tables=[...])`(沿用既有 `tables` 參數);一輪變動偵測、只同步「已啟用排程且被判定變動」的表。停用排程的表**不參與夜間同步**。
- **移除「排程涵蓋」頁與相關程式(多出來的 page)**:
  - 前端:刪 `/schedules/coverage` 頁、`ScheduleCoverageBrowser`、`scheduleCoverageApi`;Sidebar 移除「排程涵蓋」導覽項。
  - 後端:刪 `schedule_coverage` API / service / repo / schemas 與對應測試(功能併入排程管理 API)。
- **移除 v1.1 config ETL 遺留鏈路(user 已確認刪除)**:前端 `/tables` 與 `/tables/[uid]` 頁(ETL 資料表管理,現已不在 Sidebar)、`etlConfigApi.ts`;後端 `api/v1/etl_tables.py` 端點;`run_etl` worker task 與 config-driven ETL 引擎路徑(其設定來源 `etl_tables` / `etl_mappings` 已下線,任務失去意義)一併程式面移除,對應測試同步清理。
- **相關資料表 / 欄位「移除」的定義(受毀滅性操作禁止約束)**:本版「移除」= **程式面完全下線**(model 欄位標記 deprecated、API / UI / worker 不再讀寫)+ 文件列「人工移除清單」;**不產生任何 DROP migration**(CLAUDE.md 禁止)。實體 DROP(如 `etl_tables` / `etl_mappings` / `schedules.etl_table_pid` / `rds_table_meta.sync_excluded`)由人類負責人**備份後手動執行**。
- **排程管理頁 UI 改版(硬需求)**:`/schedules` 改為與 `/sources`、`/sources-hub` **非常相近**的樣式——schema 分頁籤 + 表清單瀏覽器 + 分頁 + 進階篩選,整體概念對齊原始資料管理:
  - 欄位:資料表(代碼)、業務資料名稱、**啟用**(toggle,admin only)、**排程時間**(友善 cron 摘要如「每天 00:00」)、上次同步時間、**上次結果**(沿用 StatusBadge)、**下次執行**(cron 推算;停用顯示「—」)。
  - **編輯排程走 Dialog**(沿用 v1.3.0 task-008 的 Dialog 元件與友善 cron picker):點某表的排程時間 → Dialog 修改執行時間 / 啟停 / 描述。**不再有「新增排程」按鈕**——排程由系統自動建立,使用者只做啟停與調時間。
  - **進階篩選**(對齊原始資料管理的可摺疊進階篩選):依 schema、啟用狀態(全部 / 已啟用 / 停用)、上次結果、關鍵字(表名 / 業務名)。
  - **批次啟停(硬需求)**:提供「**全部啟用**」按鈕(定位類比原始資料管理的「全量同步」——一鍵對全部表生效),搭配進階篩選提供「**符合篩選批量啟用 / 停用**」(類比 sources 頁的符合篩選批量同步);操作前以 Dialog 確認並顯示影響筆數,admin only。
- **排程管理 API 重構**:`/schedules` 列表改為逐表視角(JOIN `schedules` × `rds_table_meta`(業務名 / `last_synced_at`)× `etl_run_logs` 最新結果——查詢邏輯可自 coverage repo 遷移沿用);更新端點收斂為「改 cron / 啟停 / 描述」(不可改綁定的表);不提供手動新增 / 刪除排程端點(生命週期跟隨快照同步)。
- **人工全量同步保底**:沿用 v1.3.0,「全量同步」動作不受排程啟停影響(強制覆蓋全部表)。

## Out of Scope

- **逐表獨立 cron 以外的進階排程**(排程依賴、錯峰自動分配、重試策略):本版每表一筆 cron、預設同一時間,進階編排列未來。
- **批次調整排程時間**:批次啟停已入 scope;「批量改 cron 時間」列未來(逐表 Dialog 可改)。
- **CDC / 邏輯複製、逐筆 upsert、改動來源、時間欄 watermark**:沿用 v1.3.0 Out of Scope。
- **實體 DROP 資料表 / 欄位**:一律不由本版程式或 migration 執行(見 In Scope「移除」定義)。
- **通知 / 告警、Coolify 正式部署**:沿用既有 Out of Scope;本版仍以 localhost `docker compose` 可跑為準。

## 對外承諾

- 從 RDS 快照同步後,排程管理頁**自動出現當前所有原始資料表的排程**(一表一筆),不需人工登記;新表下次快照同步自動補上,消失的表其排程自動下線。
- 自動建立的排程**預設每天 00:00:00、預設停用**;停用的表夜間**不會**被同步(增量偵測也不看它);啟用後到點自動參與增量同步。
- 排程管理頁提供「**全部啟用**」一鍵按鈕與「符合篩選批量啟用 / 停用」,不需逐表點擊即可讓全部(或篩選命中的)表加入夜間同步。
- 排程管理頁與原始資料管理 / ETL 資料管理**同一套視覺語言**(schema 分頁籤 + 表清單 + 進階篩選 + 分頁),逐表看得到:啟用狀態、排程時間、上次同步、上次結果、下次執行;調整走 Dialog。
- 「排程涵蓋」頁自 Sidebar 與路由**消失**,其資訊(涵蓋 / 排除 / 上次結果 / 下次執行)全數併入排程管理頁,無功能遺失;v1.1 遺留的 `/tables` 頁與 config ETL 鏈路一併移除。
- 廢止結構(coverage API、`sync_excluded` 機制、`etl_table_pid`)程式面零引用;附「人工移除清單」供負責人備份後手動 DROP。
- 「全量同步」人工動作行為不變(強制覆蓋全部表)。

## 風險與相依

- **夜間同步語意反轉(已知悉的行為變更)**:v1.3.0 是「預設全表納入夜間增量」;本版改為**預設全部停用**——上線後需人工啟用才會同步(「全部啟用」一鍵按鈕已入 scope,操作成本低);此為 user 明示要求。
- **派工粒度(user 已確認:合併派工)**:同 cron 的啟用表**分組合併派一發 `mirror_sync`**——一輪 pg_stat 偵測、一筆 run,逐表結果(同步 / skip / 失敗)記在 `etl_run_logs` 明細;排程頁「上次結果」自逐表明細取,不受合併影響。一表一發(N 次偵測 + N 筆 run)已否決。
- **「移除相關資料表」範圍(user 已確認)**:廢止對象為 `etl_tables` / `etl_mappings`(v1.1 config ETL)、`schedules.etl_table_pid`、`rds_table_meta.sync_excluded`;前端 `/tables` 頁與 `run_etl` 鏈路一併刪除(見 In Scope)。實體 DROP 仍走人工移除清單。
- **`mirror_sync` 參數並用需驗證**:`incremental=True` + `tables=[...]` 的組合行為(偵測範圍是否正確限縮於指定表)需在 task 中驗證補強;現有簽名已支援參數,語意需確認。
- **排程數量放大**:排程從個位數變數百筆(每表一筆);`DbScheduleSource` 每輪重讀 DB 的成本仍低(單表查詢),但排程管理 API 必須分頁(已納入 UI 設計);taskiq 派工端因合併分組不受影響。
- **快照同步事務邊界**:自動建排程掛在 `SnapshotService.refresh` 之後,需與 metadata upsert 同交易或緊接執行,避免「表有快照、無排程」的中間態;失敗需可重入(下次 refresh 補齊)。
- **前置相依**:v1.3.0 需已落地(增量 `mirror_sync`、Dialog 排程表單、友善 cron 工具、coverage 查詢邏輯可遷移);v1.3.0 收口待辦(套 v4 migration、rebuild)完成後再開工,避免 migration 序衝突。
- **本專案跑法**:改碼後以 `docker compose up -d --build` 驗證(禁 start-dev)。

## 驗收標準

- 對來源 RDS 執行快照同步 → `schedules` 出現**每張來源表各一筆**排程,`cron_expr = "0 0 * * *"`、`is_enabled = false`;排程管理頁逐表可見。
- 來源新增一張表 → 下次快照同步後該表排程自動出現(預設值同上);來源移除一張表 → 該表排程軟刪除、頁面不再顯示。
- 既有表啟用排程並調成近期測試 cron → 到點觸發 `mirror_sync` 增量,**僅**啟用的表參與偵測 / 同步;停用表完全不動(`last_synced_at` 不變、無 run log)。
- 多張表同 cron 且皆啟用 → 到點**單一** run 內逐表偵測 / 同步(合併派工),`etl_run_logs` 可見每張表同步 / skip 結果。
- `/schedules` 頁為 schema 分頁籤 + 表清單樣式,欄位含啟用 toggle / 排程時間 / 上次同步 / 上次結果 / 下次執行;進階篩選(啟用狀態 / 上次結果 / 關鍵字)可用;編輯於 Dialog 完成;視覺與 `/sources`、`/sources-hub` 一致。
- 「**全部啟用**」按鈕一鍵把全部表的排程啟用(Dialog 確認 + 影響筆數);設定進階篩選後「符合篩選批量啟用 / 停用」僅作用於命中的表;再次快照同步後啟停狀態不被重置。
- `/schedules/coverage` 路由與 Sidebar「排程涵蓋」項**不存在**;coverage API 端點回 404;全 repo 無 `schedule_coverage` / `sync_excluded` 程式引用(欄位定義除外,標記 deprecated)。
- `/tables` 與 `/tables/[uid]` 路由**不存在**;`etl_tables` API 端點回 404;`run_etl` 不再註冊為 worker task;`uv run pytest` 無殘留 config ETL 測試失敗。
- 文件附「人工移除清單」(待 DROP 的表 / 欄位 + 備份指引);repo 內**無任何 DROP migration**。
- `cd backend && uv run pytest` / `cd frontend && npm run typecheck && npm run lint && npm run build` 全綠;localhost `docker compose up -d --build` 全流程可跑。

## 變更紀錄

- 2026-07-07:由 user 口述整理成 v1.3.1 草稿。動機:v1.3.0 的「全表統一排程 + 排程涵蓋頁」把排程與逐表狀態拆成兩頁兩套機制,多出一個頁面;user 要求改為「一表一排程」——快照同步自動建立逐表排程(預設每天 00:00:00、全部停用),排程管理頁本身即逐表檢視並對齊 `/sources`、`/sources-hub` 樣式,「排程涵蓋」頁與相關廢止結構移除(受禁 DROP 約束,實體移除走人工清單)。
- 2026-07-07(補):user 決議——(1)預設全停用但**必須有「全部啟用」按鈕**,整體概念對齊原始資料管理(schema 分類 + 進階搜尋 + 批量動作,「全部啟用」定位類比「全量同步」),批次啟停由 Out of Scope 移入 In Scope;(2)`/tables` 頁確認刪除,連同 `etl_tables` API 與 `run_etl` config ETL 鏈路一併程式面移除;(3)派工粒度確認採**同 cron 合併派工**(一輪偵測、一筆 run、逐表明細),一表一發否決。

---

## 背景參考(非 scope,供拆 task 對照)

- **v1.3.0 現況**:`scheduler.py` 對每筆啟用排程派 `mirror_sync(incremental=True)` 全表增量;涵蓋 / 排除走 `/schedules/coverage` 頁 + `rds_table_meta.sync_excluded` + `schedule_coverage` API / service / repo。
- **`mirror_sync` 簽名**(`app/worker/tasks.py`):已有 `schema` / `table` / `tables` / `incremental` 參數,per-table 派工有現成基礎;需驗證 `incremental + tables` 並用語意。
- **可遷移資產**:coverage repo 的逐表查詢(JOIN `rds_table_meta` × `etl_run_logs` 最新結果、schema 聚合、關鍵字跳脫)可直接改造為新排程管理 API 的查詢層;前端 `ScheduleCoverageBrowser` 的表格骨架、`utils/cron.ts` 的 `nextRunAt` / `describeFriendly`、task-008 的 Dialog 表單皆可沿用。
- **樣式基準(前兩者)**:`/sources`(原始資料管理)與 `/sources-hub`(ETL 資料管理)的 schema 分頁籤 + 表清單瀏覽器 + 篩選列。
- **人工移除清單(草稿,待 task 落地時確版)**:`etl_tables`、`etl_mappings`(v1.1 config ETL)、`schedules.etl_table_pid`、`rds_table_meta.sync_excluded`;皆須先備份、由人類負責人手動執行,repo 不產生 DROP。
