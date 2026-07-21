# Propose v1.5.1

## 版本目標

修補 v1.5.0 語意層上線後的第一批使用回饋:快照同步過程可視化(進度條)、語意化 view schema 命名更直觀(`_view`)、語意映射(erp_metadata)提供獨立的管理介面讓複核與 view 重生不再依賴腳本,並修正英文草稿的 unused 命名缺陷。價值對象:操作同步的管理者(不再乾等)、複核映射的維運者(圖形化編輯 + 即時生效)、SQL/BI 使用者(schema 命名一目了然、欄名不失真)。

## In Scope

- **快照同步進度條**:原始資料管理 / ETL 資料管理兩頁的快照同步執行期間,頁面顯示階段化進度(已於分支 `dev-v1.5.1/snapshot-progress` 先行實作,本版補登驗收)。
- **語意化 view schema 改名**:後綴 `_en` → `_view`(例 `S2202_en` → `S2202_view`);系統側改產生器落點,RDS 既有 `_en` schema 由 user 手動 `ALTER SCHEMA ... RENAME`(非 DROP,view 隨 schema 平移,不需人工移除清單)。
- **語意映射管理獨立頁**:sidebar 獨立入口(不併入 ETL 資料管理區塊),admin-only;可瀏覽 / 分頁 / 依表名與狀態篩選 RDS `erp_metadata.semantic_mappings`(唯一事實來源),可編輯英文名 / 中文名、draft ↔ confirmed 轉態,並可手動觸發「同步 view」(本地副本重灌 + view 重生)讓映射異動即時生效。
- **英文草稿命名修正**:中文名為「No Use」(不分大小寫)或空值的欄位,英文名一律採**原始欄名(小寫)**,不得產生 `unused_*` 等失真名稱;修正全量草稿並重新 seed(既有 confirmed 不覆寫)。

## Out of Scope

- 不動鏡像表實體結構 / 欄名(維持 v1.5.0 決議:語意只在 view / JSON 層)。
- 不做映射雙向同步:編輯一律寫 RDS 真身,自有 DB 副本維持單向重灌。
- 不由程式刪除 RDS 上既有 `_en` schema / view(走人工移除清單)。
- 不做全量複核轉 confirmed(仍由人工分批圈選)。
- 不處理其他既有遺留(殭屍 run、adminer 外露等,見 v1.4.0 遺留清單)。

## 對外承諾

- 快照同步期間,前端顯示階段化進度條;新端點 `GET /api/v1/datasets/{dataset}/snapshot/refresh/progress`(admin)。
- 語意化 view 一律落在 `<帳套schema>_view`;映射異動經管理頁「同步 view」按鈕即時生效,或於下一輪 ETL 同步自動生效。
- 新 sidebar 入口「語意映射管理」(admin-only):列表 / 篩選 / 編輯 / 轉態 / 觸發同步,對應 `/api/v1/semantic-mappings` 系列端點。
- 草稿英文名不再出現 `unused_*`;「No Use」/ 空值欄位的英文名 = 原始欄名小寫。

## 風險與相依

- 技術風險:改後綴後首輪重生需強制觸發(既有簽名快取須失效);舊 `_en` 與新 `_view` 在人工移除前並存,查詢者可能誤用舊 view(以人工移除清單 + 公告緩解)。
- 技術風險:管理頁編輯為系統首條「寫 RDS erp_metadata」的線上路徑,需 bind params、confirmed 保護與 admin 權限三重底線;與 mirror 寫入路徑互不干擾。
- 第三方依賴:無新增。
- 跨團隊阻塞:`_en` schema 實體移除需 DBA / 負責人執行人工清單。

## 驗收標準

- 後端 `uv run pytest` 全綠;前端 `npm run typecheck` + `npm run lint` 全綠。
- 手測:點快照同步 → 進度條顯示階段與百分比至完成。
- 手測:管理頁編輯一筆映射 → 轉 confirmed → 按「同步 view」→ RDS `<schema>_view` 出現 / 更新對應 view,`_en` 不再新增。
- 草稿 TSV 與 RDS draft 列查無 `unused` 開頭英文名;BMA_FILE 既有 confirmed 列未被覆寫。

## 決策記錄

- 2026-07-21:由 user 口述整理成本 propose(比照 v1.3.1 慣例)。四項範圍皆為 user 明示:進度條(補登)、`_view` 改名、映射管理獨立頁(明示「獨立 sidebar,不要顯示在 ETL 資料管理區塊」)、unused 命名修正(明示「No Use / 空 → 用原始 column_name」)。
- 2026-07-21:版號 **v1.5.1 為 user 裁定**,推翻 `05-version-bump.md`「新功能走 minor / patch 不寫 propose」規範;是否更新規範檔待 `/reflect-rules` 決議。
- 2026-07-21:view 位置經評估(併回原 schema vs 獨立 schema)後,user 裁定**維持獨立 schema、後綴 `_view`**(撞名風險 + 權限隔離 + BI 清單乾淨)。
- 程序註記:快照進度條於本 propose 建立前先行實作(AI 程序疏失,經 user 指正);本版以 task-001 補登並以驗收標準回補。
- unused 命名缺陷實錘:`semantic_draft.tsv` 中 287 筆「No Use」欄位被命名為 `unused_<尾碼>`,丟失原欄位識別。

## 變更紀錄

- 2026-07-21(拆解後):`_en` 改名方式由「產生器改後綴 + 強制重生 + 人工移除清單」改為「**user 手動 `ALTER SCHEMA ... RENAME` + 系統側只改落點**」(user 提議;RENAME 非 DROP,不觸毀滅性操作底線)。受影響 task:task-002(範圍縮小,估時 2 → 1 hr,移除人工移除清單交付物與強制重生機制);風險段「舊 `_en` 並存」與跨團隊阻塞「人工清單」隨之消滅。
- 2026-07-21(user 指示,實作期):快照同步進度條由頁內改為**全局**——新 `SnapshotProgress` 掛 (main) layout,與 mirror 的 `SyncProgress` 並列;文案區分「快照同步中(原始資料 / ETL 資料)」vs「ETL 同步中(手動 / 排程)」;`DatasetBrowser` 頁內進度條移除。受影響 task:001(範圍延伸)、006 無涉。
- 2026-07-21(user 指示,實作期):語意映射管理頁搜尋改用 ETL 區塊同款 `TableSearchCombobox`(資料表 / 欄位名稱,中英皆可);後端列表 keyword 比對加入 `table_name`。受影響 task:004 / 006(範圍延伸)。
- 2026-07-21(scan 級修正,隨版收口):ETL 資料管理「資料分類」出現 `erp_metadata` → 內省排除修正 + 快照殘留列軟刪(見 fixed.md #1);本機殭屍 run 收殮(見 fixed.md #2)。
