# ERP-Analyze — 來源系統資料庫逆向分析

本目錄整併自獨立分析專案 `erp-data-analyze`（2026-07-20 搬入），內容為 **ERP（鼎新 TIPTOP GP / Oracle）**、**BPM（EFGP / MS SQL Server）**、**HRM（HRMDB / MS SQL Server）** 三套來源系統的 metadata 逆向分析：表/欄位中文名、字典結構、程式(畫面)對應與關聯推導。

本專案 ETL 的中文 comment 來源（`backend/app/etl/dictionary.py` 查 `DS.GAT_FILE` / `DS.GAQ_FILE`）即以此分析為事實依據；對照驗證見 [mapping-alignment.md](mapping-alignment.md)。

## 目錄導覽

| 路徑 | 內容 | 版控 |
| --- | --- | --- |
| `mapping-alignment.md` | **DS 字典 ↔ 本專案 mapping 對照與驗證**（本次整合主文件） | ✅ |
| `prompts/` | 三份分析任務 prompt（交給 agent 執行的原始指令） | ✅ |
| `output/*.md` | 三份分析報告（ERP / BPM / HRM） | ✅ |
| `output/*.html` | 同內容的 HTML 版（ERP 版 9.3MB，含互動目錄） | ❌ gitignore |
| `data/` | 原始查詢 dump（TSV + 查詢錯誤 .err，約 18MB），報告由此產生 | ❌ gitignore |
| `tools/` | 報告產生器與查詢工具（見下） | ✅ |

> `output/*.html` 與 `data/` 為本地保留、不進版控（對齊 `docs/Arch/ai-data-hub.html` 先例）；clone 後若需要，可依下節工具重新產生，或向持有者索取。

## 工具說明（`tools/`）

| 檔案 | 用途 |
| --- | --- |
| `java/Q.java` / `Q2.java` / `q.sh` | Oracle 唯讀查詢小工具（stdin 收 SQL、stdout 吐 TSV）；`Q2` 讀 `db.properties`（複製 `db.properties.example` 填值，**該檔已 gitignore**） |
| `java/generate.py` | 讀 `data/*.tsv` 產出 `erp-metadata.md/html`（初版） |
| `_gen_screen.py` | 讀 `data/*.tsv` 產出 `erp-metadata.md/html`（現行版：DS 字典 ↔ M2201 ↔ 畫面整合） |
| `_gen.py` | 連線 MS SQL Server 抽取 metadata 並產出 `bpm/hrm-metadata.md/html` |
| `_fmtscan.py` | 掃描 EFGP 大文字欄位格式（XML/HTML/JSON/BASE64 判別） |

## 機密聲明

- 原專案的 `DB-INFO.md` 與 `_java/db.properties`（含明碼帳密）**未搬入、不得進 repo**；連線帳密向 IT 索取。
- 工具中的密碼一律改走環境變數：`_gen.py` / `_fmtscan.py` 讀 `MSSQL_SA_PASSWORD`；`Q.java` 讀 `ERP_DB_USER` / `ERP_DB_PASSWORD`；`Q2.java` 讀本地 `db.properties`。
- 所有工具與分析全程唯讀（只下 `SELECT`），對應 prompt 內有明確約束。

## 分析報告快覽（ERP）

- 資料庫：Oracle 11g `toptest`，字元集 AL32UTF8；每家公司/帳套一個 schema（同構），全域字典在 `DS`。
- 核心字典鏈：表中文名 `GAT_FILE`、欄位中文名 `GAQ_FILE`、程式主檔 `ZZ_FILE`、程式名稱 `GAZ_FILE`、程式↔表 `ZR_FILE`、畫面欄位標籤 `GAE_FILE`、邏輯 PK/FK `GAU_FILE`。
- 主要分析帳套 `M2201`：有資料 333 表、11,947 欄；**無任何實體 FK**，關聯靠字典與命名慣例推導。

詳見 `output/erp-metadata.md`（§2 已知條件驗證、§3.1 核心字典表）。
