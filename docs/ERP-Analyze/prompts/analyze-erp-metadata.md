# Agent 執行 Prompt：解析鼎新 ERP Metadata 並產出關聯圖

> 本檔是交給 agent 直接執行的指令。任務來源見 [analyze-erp-metadata.md](analyze-erp-metadata.md)，連線資訊見 [../DB-INTO.md](../DB-INTO.md)。

## 角色

你是一位資料庫逆向工程工程師，專長為鼎新（Digiwin / 鼎新）ERP 的 Oracle 資料庫結構分析。

## 目標

解析鼎新 ERP 測試站資料庫，整理出 **Table 與 Column 的 metadata（含中文名稱／說明）以及資料表之間的對應關係**，最後產出一份關聯圖文件（同時輸出 Markdown 與 HTML）。

## 連線資訊

| 項目 | 值 |
| --- | --- |
| 類型 | Oracle |
| 主機 | `10.200.206.130:1521` |
| SID | `toptest` |
| 帳號 | `RO_M2201`（**唯讀**） |
| 密碼 | （不入 repo；見原 erp-data-analyze 專案 `DB-INFO.md` 或向 IT 索取） |

連線方式自選（擇一可用即可）：`python-oracledb` / `cx_Oracle` / `sqlplus` / `sqlcl`。
若環境缺驅動，先嘗試 `pip install oracledb`（thin mode 免裝 client）。

> ⚠️ 此帳號為唯讀。**禁止任何寫入操作**（INSERT / UPDATE / DELETE / DDL）。只下 `SELECT`。

## 已知條件（皆需先以查詢驗證，不可直接當作事實）

1. 推測僅以下 schema（owner）有資料：`DS`、`M2201`、`MDF`、`PATCHTEMP`、`SDF`。
   - 註：在 Oracle 中這些是 schema/owner，非獨立 database。
2. 推測 `DS.GAT_FILE` 的 `GAT01` 欄位存放的是其他 schema 的 Table 名稱（鼎新資料字典慣例）。
   - 也請一併確認是否存在欄位字典表（例如 `GAT_ITEM` 或類似 `GAT*` 系列），作為 column 中文名稱來源。

## 執行步驟

### 階段 0：連線與探索
1. 建立連線並確認可查詢系統檢視（`ALL_TABLES`、`ALL_TAB_COLUMNS`、`ALL_COL_COMMENTS`、`ALL_TAB_COMMENTS`、`ALL_CONSTRAINTS`、`ALL_CONS_COLUMNS`）。
2. 列出當前帳號可存取的所有 owner 與各 owner 的 table 數，記錄結果。

### 階段 1：驗證已知條件
1. **驗證有資料的 schema**：對清單中每個 owner 統計 table 數與（抽樣）資料列數，確認哪些真的有資料；同時找出清單外但其實有資料的 owner。
2. **驗證 GAT_FILE / GAT01**：
   - 確認 `DS.GAT_FILE` 是否存在、欄位結構為何、`GAT01` 取樣內容是否為「表名」。
   - 找出 `GAT_FILE` 中哪些欄位是表的中文名稱／說明。
   - 找出欄位層級的字典表（如 `GAT_ITEM`），確認其與 `GAT_FILE` 的關聯鍵與「欄位中文名」來源。
   - 將驗證結果（成立 / 不成立 / 修正後的事實）明確寫進輸出文件的「已知條件驗證」章節。

### 階段 2：蒐集 Metadata
1. **Table metadata**：每張表的 owner、表名、（字典表來源的）中文名稱／說明、資料列數。
2. **Column metadata**：每個欄位的表名、欄位名、資料型別、長度、是否可空、PK/UK/FK、（字典表或 `ALL_COL_COMMENTS` 來源的）中文名稱／說明。
3. 優先以鼎新資料字典表（`GAT_FILE` / `GAT_ITEM` 等）作為中文名稱來源；缺漏時退回 `ALL_*_COMMENTS`。

### 階段 3：建立關聯
1. 由 `ALL_CONSTRAINTS` / `ALL_CONS_COLUMNS` 取得正式外鍵關聯。
2. 由命名慣例與資料字典推導隱含關聯（鼎新多以共用代碼欄位關聯，未必有實體 FK）。
3. 標註關聯來源（實體 FK / 字典推導 / 命名慣例推導），並標示可信度。

### 階段 4：產出
產出至 `docs/output/`（不存在則建立）：
1. `erp-metadata.md`
2. `erp-metadata.html`

兩份內容一致，需包含：
- **總覽**：各 schema 的角色與 table 數摘要。
- **已知條件驗證**：逐項列出驗證結論。
- **關聯圖**：以 Mermaid `erDiagram`（或 `graph`）呈現「DB → Table → Column」與表間關聯；HTML 版以 Mermaid CDN 渲染為可視圖。
- **Table 清單**：表格欄位 = schema、表名、中文名/說明、列數。
- **Column 清單**：依表分組，欄位 = 欄位名、中文名/說明、型別、可空、鍵別（PK/FK…）。

## 約束與品質要求
- 全程唯讀，只下 `SELECT`；任何 query 失敗要記錄錯誤並繼續，最後彙整無法取得的部分。
- 區分「查詢得到的事實」與「推導／推測」，後者須明確標註。
- 大表統計列數請用 `COUNT(*)` 但避免全表掃描卡死時，可改以抽樣或 `NUM_ROWS`（取自統計資訊）並註明來源。
- 中文（繁體）撰寫輸出文件。
- 完成後回報：實際有資料的 schema、字典表驗證結論、產出檔案路徑、未能解析的部分。
