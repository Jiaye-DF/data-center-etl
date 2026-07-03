# Propose v1.0.0

## 版本目標

建立一套以 framework 方式設計的 ERP ETL 系統:把已由 DMS 遷移到 RDS PostgreSQL 的 ERP 來源資料(`DS` / `M2201` schema),經 AWS Glue (PySpark) 轉換後落地到集中的 `erp_etl_hub_test` DB,並提供後台可調整的 ETL 腳本 / 設定管理。對資料團隊的價值:ETL 邏輯以設定驅動、可維護、可從後台調整,不需每次改程式。

## In Scope

- **ETL framework 骨架**:建立 Glue Job 可執行的 framework 目錄結構(`main.py` 入口 / `config` 設定層 / `jobs` 作業層 / `common` 共用 reader·writer·logger·utils / `transforms` 轉換層),腳本部署於 S3 Bucket。
- **目標 DB 建置**:在 RDS 建立 `erp_etl_hub_test` DB,作為所有轉換後資料的落地處;表格沿用原始 `table_name`。
- **DS schema 資料搬移**:將來源 `DS` schema 完整搬移一份到目標 `erp_etl_hub_test`。
- **GAT_FILE / GAQ_FILE → M2201 欄位對應轉換**:依 `DS.GAT_FILE`、`DS.GAQ_FILE` 既有欄位 / 表格名稱,對應轉換到 `M2201`,以 `config/mapping/*.yaml` 設定驅動。
- **欄位 Comment 套用**:目標 DB 每一個欄位都必須帶 Comment,內容來源對應 `GAQ_FILE`。
- **設定以檔案驅動**:job / table / mapping 設定全部落在 `etl/config/*.yaml`,可版本控管;本版 ETL 為獨立 `etl/` 專案,**完全不動本專案前端 / 後端**。

## Out of Scope

- 正式生產環境部署(本版只針對測試 DB:來源 `erp_migration_test`、目標 `erp_etl_hub_test`)。
- Oracle 來源直連(來源資料已由 DMS 遷移至 RDS PostgreSQL,不在本版重做遷移)。
- `DS` / `M2201` 以外的 ERP schema / 表格轉換。
- 後台觸發 / 排程 Glue Job 執行(本版只做設定管理,不做觸發與排程)。
- **ETL 腳本 / 設定管理後台**(後端 API + 前端頁面):本版**不做**,不新增 / 不修改本專案 `backend/` `frontend/`;ETL 設定以 `etl/config/*.yaml` 檔管理。留待後續版本。

## 對外承諾

- ETL 執行後,`erp_etl_hub_test` 產生對應 `M2201` 的表格,表格沿用原始 `table_name`,且每個欄位皆帶 Comment(對應 `GAQ_FILE`)。
- `erp_etl_hub_test` 內含一份由來源 `DS` schema 搬移過來的資料。
- ETL 為獨立 `etl/` 目錄,job / table / mapping 設定以 `etl/config/*.yaml` 檔完成,不依賴本專案前後端。

## 風險與相依

- **技術風險**:PySpark 轉換型別 / 欄位對應(GAT_FILE·GAQ_FILE → M2201)需與實際欄位定義逐一比對,mapping 錯誤會造成資料落錯欄位。
- **第三方依賴**:AWS Glue(執行環境)、AWS S3(腳本存放)、AWS RDS PostgreSQL(來源與目標 DB)。
- **前置相依**:來源 `erp_migration_test` DB(含 `DS` / `M2201` schema)須已由 DMS 遷移完成並可讀。
- **資料相依**:欄位 Comment 來源需 `GAQ_FILE` 欄位描述齊全;缺描述的欄位需 user 補齊對應表。

## 驗收標準

- `erp_etl_hub_test` DB 建立成功,含由 `DS` 搬移的資料。
- ETL 執行後於 `erp_etl_hub_test` 產生對應 `M2201` 的表格,表名沿用原始 `table_name`。
- 目標表格每一欄位皆有 Comment(可用 `information_schema` / `pg_description` 查詢驗證非空)。
- ETL framework 目錄結構齊全且 Glue Job 可從 S3 讀取 `main.py` 成功執行一次。
- 本專案 `backend/` 與 `frontend/` 無任何異動(`git diff --stat` 不含 `backend/` `frontend/` 路徑)。

## 變更紀錄

- 2026-07-03:移除「ETL 腳本管理後台(前後端)」In Scope 條目,改列 Out of Scope(本版 ETL 為獨立 `etl/`,不動本專案前後端;設定以 `etl/config/*.yaml` 檔管理)。理由:user 指示本次 MVP ETL 完全不觸及本專案前端 / 後端。

---

## 背景參考(非 scope,供拆 task 對照)

> 以下為實作背景,不作為 scope 條目;實際目錄 / 檔名由 task 決定。

### 設施

- AWS Glue(PySpark 執行環境)
- AWS RDS(PostgreSQL,來源 `erp_migration_test` / 目標 `erp_etl_hub_test`)
- AWS S3(ETL 腳本存放)

### Glue framework 參考結構

```
glue-etl-framework/
├── main.py                  # Glue Job 入口
├── config/
│   ├── job_config.yaml
│   ├── table_config.yaml
│   └── mapping/
│       ├── customer.yaml
│       ├── order.yaml
│       └── inventory.yaml
├── jobs/
│   ├── customer_job.py
│   ├── order_job.py
│   └── inventory_job.py
├── common/
│   ├── reader.py
│   ├── writer.py
│   ├── logger.py
│   └── utils.py
└── transforms/
    ├── common.py
    ├── customer.py
    └── order.py
```

### ETL 方向補充

- 來源 `DS.GAT_FILE`、`DS.GAQ_FILE` 的欄位 / 表格名稱,對應到 `M2201`。
- 來源 DB `erp_migration_test` 已由 DMS 遷移,含 `DS` 與 `M2201` schema。
- 目標 DB `erp_etl_hub_test` 存放所有轉換後資料;表名沿用原始 `table_name`。
- 每個欄位一定要有 Comment(對應 `GAQ_FILE`)。
- `DS` 需另搬移一份到目標 DB。
