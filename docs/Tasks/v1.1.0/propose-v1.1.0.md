# Propose v1.1.0

> **草稿**:由 agent 依 user 口述整理,propose 由 user 認可後才生效(`01-propose/01-propose-format.md`);確認 / 修改後即可跑 `/propose-to-tasks`。

## 版本目標

把 v1.0.0 檔案驅動的 Glue ETL 演進為**後台可管理、可排程的容器化 ETL 平台**:提供管理後台(前後端)管理權限 / ETL 設定 / 排程 / 執行紀錄,排程到點由 worker 直連 RDS 執行 ETL。對資料團隊的價值:ETL 設定與排程從「改 yaml 檔 + 手動觸發」變成「後台操作」,不需碰程式與 AWS Console。

## In Scope

- **管理後台 backend(FastAPI)**:ETL 設定管理(job / table / mapping)、排程管理、手動觸發、執行紀錄與詳細 log 查詢、權限管理之 API。
- **管理後台 frontend(Next.js App Router + TypeScript)**:以**資料表為中心**的管理 UI —— **所有 Data Table 的 ETL 皆可於後台管理**:表清單(含來源 / 目標 / 啟用狀態)、逐表啟用 / 停用、mapping 與欄位 Comment 編輯、逐表最近執行狀態與 log 檢視。
- **詳細執行 Log**:每次執行(排程 / 手動)逐表記錄詳細資訊 —— 起訖時間、讀取 / 寫入筆數、耗時、成功 / 失敗、錯誤明細(含 stack trace);log 落自有 DB,後台可依 run / 表 / 狀態查詢。
- **自有 DB(PostgreSQL)**:存放使用者 / 角色權限、ETL 設定、排程定義、執行紀錄;設定的 **source of truth 在此 DB**(worker 執行時直接讀取)。
- **排程服務(taskiq + redis)**:scheduler 依 DB 排程定義到點派工,worker 執行 ETL;執行結果回寫執行紀錄。
- **ETL 容器內執行(不依賴 Glue / Spark)**:worker 直連來源 `erp_migration_test` 與目標 `erp_etl_hub_test`(RDS PostgreSQL)完成 DS 搬移與 GAT_FILE/GAQ_FILE → M2201 對應轉換;沿用 v1.0.0 的 mapping 規則與「每欄位必帶繁中 Comment」要求;容器化設計參考 `ERP-ETL-test`。
- **登入與權限(雙軌)**:接 DF-SSO 登入,**並**支援本地帳號密碼登入;初始管理員(init_admin)帳密由**環境變數**注入、首次啟動自動建立(禁寫入 repo / yaml);自有 DB 存本地帳號(密碼雜湊)與角色 / 權限對應;至少 admin(可改設定 / 排程)與 viewer(唯讀)兩種角色。
- **Docker 化**:所有 image 名稱一律 `etl_` prefix(如 `etl_frontend` / `etl_backend` / `etl_worker`);應用服務就 `frontend` / `backend` 兩個,加上排程(taskiq worker / scheduler)、redis 與自有 DB;docker-compose 本地可完整起跑。
- **可部署產物**:提供 Coolify 可用的 image(`etl_` prefix)與 env 範本;**實際部署由 user 人工執行**(含 AWS 雲端與 EC2 機器建立,不拆 task)。

## Out of Scope

- **AWS Glue / S3 腳本部署路線**:v1.0.0 的 `etl/`(Glue 版)保留不動、不再演進;本版 ETL 執行一律走容器。
- Oracle 來源直連(來源仍為 DMS 遷移後的 RDS PostgreSQL)。
- `DS` / `M2201` 以外的 ERP schema / 表格轉換。
- ETL 執行的水平擴充 / 分散式運算(單 worker 容器即可,資料量不需 Spark)。
- 通知 / 告警(執行失敗僅記錄於執行紀錄,不發信 / 不接 IM)。
- **Coolify 正式部署與 AWS 雲端 / EC2 機器建立**:由 user 人工執行,不拆 task;部署後的正式環境驗收(EC2 → RDS 實跑)亦由 user 自驗。

## 對外承諾

- 後台登入後可:檢視**所有 Data Table** 的 ETL 狀態並逐表管理(啟停 / mapping / Comment)、建立 / 啟停排程、手動觸發一次執行、查詢執行紀錄與**逐表詳細 log**(狀態 / 起訖時間 / 讀寫筆數 / 耗時 / 錯誤明細)。
- 排程到點自動執行 ETL,結果(成功 / 失敗)可於後台查得;目標 `erp_etl_hub_test` 資料與 v1.0.0 相同承諾:表名沿用原始 `table_name`、每欄位帶繁中 Comment。
- 權限控管:viewer 角色無法改設定 / 排程(API 拒絕 + 前端隱藏)。
- 所有 docker image 以 `etl_` 開頭;docker-compose 一鍵本地起跑。
- 交付 Coolify 可部署的 image(`etl_` prefix)與 env 範本;user 人工部署於 EC2 後,worker 可實際寫入 RDS 完成一次 ETL(由 user 自驗)。

## 風險與相依

- **技術棧註記**:taskiq / redis / docker image 產製不在鎖定棧與 design-base 規範內,經 user 明示採用;正式化規範走 `/reflect-rules` 補。
- **技術風險**:ETL 由 PySpark 改純 Python 執行,需重新驗證大表效能與 Oracle→PG 遺留型別對應;v1.0.0 `etl/` 的轉換 / Comment 邏輯移植時需保持行為一致。
- **網路相依**:EC2(Coolify)→ RDS 的 Security Group / VPC 放行需 AWS 端先設定完成;本地開發連不到 RDS 時以 docker PG 替身驗證(參考 `ERP-ETL-test`)。
- **第三方依賴**:Coolify(部署)、AWS EC2 / RDS、redis(taskiq broker)。
- **前置相依**:來源 `erp_migration_test` 可讀;DF-SSO 登入器可用(SSO 不可用時仍可以本地帳密登入,不阻塞後台使用)。

## 驗收標準

- `docker compose up` 後 frontend / backend / worker / scheduler / redis / 自有 DB 全部健康(healthcheck 通過)。
- `docker images` 清單中本專案 image 全部 `etl_` prefix。
- 後台建立一筆排程(近期時間)→ 到點 worker 自動執行 → 執行紀錄出現於後台且狀態為成功,目標 DB 有資料落地。
- 手動觸發一次 ETL 成功,`erp_etl_hub_test`(或本地替身 DB)產生 M2201 對應表 + DS 搬移資料,且每欄位 Comment 非空(沿用 `etl/scripts/verify_target_db.sql` 驗證)。
- 該次執行於後台可查**逐表詳細 log**:每張處理過的表皆有起訖時間 / 讀寫筆數 / 耗時 / 狀態;製造一次失敗(如錯誤連線)後,log 含錯誤明細(stack trace 非空)。
- 後台表清單頁列出所有納管 Data Table;停用其中一表後再執行,該表不被處理且 log 可證。
- viewer 角色呼叫設定 / 排程之寫入 API 回 403。
- 以環境變數注入的 init_admin 帳密可完成本地登入取得 admin 權限;缺 init_admin 環境變數時啟動 fail-fast(不以預設帳密起服務);DF-SSO 登入流程可完成並對應到既有角色。
- (user 人工驗收)Coolify 部署於 EC2 後:服務 health endpoint 回 200,且於正式環境成功執行一次 ETL 寫入 RDS。
- v1.0.0 `etl/`(Glue 版)無異動(`git diff --stat` 不含 `etl/` 既有檔案的修改)。

## 變更紀錄

- 2026-07-03:Coolify 正式部署與 AWS 雲端 / EC2 建立改為 **user 人工執行**,自 In Scope 移除、列 Out of Scope;對應移除 task-013(部署收口),系統面交付止於 task-012(image + compose + env 範本)。理由:user 指示部署與機器建立親自處理。

---

## 背景參考(非 scope,供拆 task 對照)

- **容器化設計參考**:`C:/Users/jiaye.he/Desktop/df-projects/ERP-ETL-test`(docker-compose:postgres + etl 容器 + 選用 pgAdmin;config yaml 掛 volume;`.env.docker` 環境變數範本)。
- **轉換規則來源**:v1.0.0 `etl/config/mapping/*.yaml`(DS / M2201 對照與欄位 Comment)與 `etl/transforms/*`;本版把這些設定遷入自有 DB 作為初始資料。
- **服務組成(構想)**:`frontend`(Next.js)/ `backend`(FastAPI)/ taskiq worker + scheduler / `redis` / 自有 PostgreSQL;image 名 `etl_frontend`、`etl_backend`、`etl_worker` 等。
- **部署**:Coolify on EC2;環境變數分層遵循 `docs/Design-Base/00-overview/03-env-layers.md` 與 `06-Coolify-CD/`。
