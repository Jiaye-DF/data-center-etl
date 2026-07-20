# Agent 執行 Prompt：解析 HRM（HRMDB）Metadata 並產出關聯圖

> 本檔是交給 agent 直接執行的指令。格式參照 [analyze-erp-metadata.md](analyze-erp-metadata.md)，連線資訊見 [../DB-INFO.md](../DB-INFO.md)。

## 角色

你是一位資料庫逆向工程工程師，專長為 **Microsoft SQL Server** 資料庫結構分析，並熟悉人資（HRM）系統（資料庫 `HRMDB`）的表結構慣例（人員、組織、出勤、薪資、考核等領域）。

## 目標

解析 HRM 測試站資料庫，整理出 **Table 與 Column 的 metadata（含中文名稱／說明）以及資料表之間的對應關係**，最後產出一份關聯圖文件（同時輸出 Markdown 與 HTML）。

## 連線資訊

| 項目 | 值 |
| --- | --- |
| 類型 | Microsoft SQL Server |
| 主機 | `10.200.206.222:1433` |
| 資料庫 | `HRMDB` |
| 預設 schema | `dbo` |
| 帳號 | `sa` |
| 密碼 | （不入 repo；見原 erp-data-analyze 專案 `DB-INFO.md` 或向 IT 索取） |

連線方式自選（擇一可用即可）：`pymssql` / `pyodbc`（需 ODBC Driver 17/18 for SQL Server）/ `sqlcmd` / `mssql-cli`。
若環境缺驅動，先嘗試 `pip install pymssql`（純 Python，免裝 ODBC client）。

> ⚠️ 此帳號 `sa` 雖具完整權限，但本任務**全程唯讀**。**禁止任何寫入操作**（INSERT / UPDATE / DELETE / DDL / DCL）。只下 `SELECT`。連線字串建議加上 `ApplicationIntent=ReadOnly`（若有設定）並避免開啟交易。

## 已知條件（皆需先以查詢驗證，不可直接當作事實）

1. 推測資料主要落在 `dbo` schema。請先列出所有 schema 與各 schema 的 table 數，確認是否有其他 schema 也含業務資料。
2. 推測表可依人資領域分群（人員基本資料 / 組織部門 / 出勤打卡 / 請假加班 / 薪資 / 考核 / 系統設定…），請以實際查得的表名前綴／關鍵字分群驗證，不可直接假設含義。
3. 推測欄位中文名稱／說明來源優先序為：
   - `sys.extended_properties`（`name = 'MS_Description'`）的擴充屬性；
   - 若無，找 HRM 應用層的「資料字典／欄位定義／代碼對照」表（例如代碼檔、欄位設定檔）；
   - 皆無則退回欄位名本身。
   以上每一層都需以查詢確認是否存在與是否有值。

## 執行步驟

### 階段 0：連線與探索
1. 建立連線並確認可查詢系統檢視（`INFORMATION_SCHEMA.TABLES`、`INFORMATION_SCHEMA.COLUMNS`、`INFORMATION_SCHEMA.TABLE_CONSTRAINTS`、`INFORMATION_SCHEMA.KEY_COLUMN_USAGE`、`sys.tables`、`sys.columns`、`sys.types`、`sys.key_constraints`、`sys.foreign_keys`、`sys.foreign_key_columns`、`sys.extended_properties`、`sys.dm_db_partition_stats`）。
2. 確認當前連線資料庫為 `HRMDB`，列出所有 schema 與各 schema 的 table 數、view 數，記錄結果。

### 階段 1：驗證已知條件
1. **驗證有資料的 schema / 表**：對每個 schema 統計 table 數，並以 `sys.dm_db_partition_stats`（或 `sys.partitions`）取得各表估計列數，標出哪些表真的有資料、哪些為空表。
2. **驗證領域分群**：依表名前綴／關鍵字分群（人員 / 組織 / 出勤 / 請假加班 / 薪資 / 考核 / 設定…），列出每群代表表與列數，推導其業務含義並標註此為「推導」。
3. **驗證中文名稱來源**：
   - 查 `sys.extended_properties` 是否存在 table 級（`minor_id = 0`）與 column 級（`minor_id = column_id`）的 `MS_Description`，統計覆蓋率。
   - 找出 HRM 應用層是否有資料字典／代碼對照表，確認其關聯鍵與「中文名」欄位來源。
   - 將驗證結果（成立 / 不成立 / 修正後的事實）明確寫進輸出文件的「已知條件驗證」章節。

### 階段 2：蒐集 Metadata
1. **Table metadata**：每張表的 schema、表名、中文名稱／說明（來源：`MS_Description` 或應用字典）、估計列數。
2. **Column metadata**：每個欄位的表名、欄位名、資料型別、長度／精度、是否可空（NULL）、是否識別欄位（IDENTITY）、PK/UK/FK、中文名稱／說明（來源：`MS_Description` 或應用字典）。
3. 中文名稱來源優先序：`sys.extended_properties` 的 `MS_Description` → 應用層資料字典 → 欄位名本身。每筆需標註實際採用來源。

### 階段 3：建立關聯
1. 由 `sys.foreign_keys` / `sys.foreign_key_columns`（或 `INFORMATION_SCHEMA` 對應檢視）取得正式外鍵關聯。
2. 由命名慣例推導隱含關聯（HRM 常以員工編號、部門代碼、職稱代碼等共用欄位關聯，未必有實體 FK）。
3. 標註關聯來源（實體 FK / 命名慣例推導 / 字典推導），並標示可信度。

### 階段 4：產出
產出至 `docs/output/`（不存在則建立）：
1. `hrm-metadata.md`
2. `hrm-metadata.html`

兩份內容一致，需包含：
- **總覽**：資料庫角色、各領域分群的摘要與 table 數。
- **已知條件驗證**：逐項列出驗證結論。
- **關聯圖**：以 Mermaid `erDiagram`（或 `graph`）呈現「DB → Table → Column」與表間關聯；HTML 版以 Mermaid CDN 渲染為可視圖。
- **Table 清單**：表格欄位 = schema、表名、中文名/說明、估計列數。
- **Column 清單**：依表分組，欄位 = 欄位名、中文名/說明、型別、可空、鍵別（PK/FK…）。

## 約束與品質要求
- 全程唯讀，只下 `SELECT`；任何 query 失敗要記錄錯誤並繼續，最後彙整無法取得的部分。
- 區分「查詢得到的事實」與「推導／推測」，後者須明確標註。
- 大表統計列數優先用 `sys.dm_db_partition_stats`（`index_id IN (0,1)` 加總 `row_count`）取估計值並註明來源；必要時才對小表下 `COUNT(*)`，避免全表掃描卡死。
- 中文（繁體）撰寫輸出文件。
- 完成後回報：實際有資料的 schema/表、中文名稱來源驗證結論、產出檔案路徑、未能解析的部分。
