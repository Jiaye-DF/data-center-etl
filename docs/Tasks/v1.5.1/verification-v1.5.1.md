# Verification v1.5.1(2026-07-21)

> 環境:本機 docker compose 全套(etl_backend / etl_frontend / etl_postgres / etl_redis / etl_worker / etl_scheduler 全 healthy)+ 真實測試 RDS(`erp_etl_hub_test`)。分支 `dev-v1.5.1/snapshot-progress`。

## 對 propose 驗收標準逐條

### 1. 測試 / 靜態檢查全綠

- 後端完整套件:`pytest tests -q` → **308 passed**(含新增 `test_snapshot_refresh_progress.py` 5 例、`test_semantic_mappings_api.py` 9 例)。
- 後端 `ruff check app tests` → All checks passed;`mypy app` 僅既有 `schedule_repo.py:528`(rowcount)一錯,非本版引入。
- 前端 `npm run typecheck` + `npm run lint` → 全綠。

### 2. 快照同步進度條(task-001)

- 後端:`GET /datasets/{dataset}/snapshot/refresh/progress` 閒置回 `{"active":false,...}`(冒煙實測 200);refresh 過程四階段寫 Redis、結束清 key,由 pytest 覆蓋。
- 前端:`RefreshProgressBar` 於 isRefreshing 期間 2 秒輪詢;**UI 視覺待 user 手測**(點快照同步觀察進度條)。

### 3. `_view` schema 改名(task-002)+ 映射管理(task-004/005/006)

- RDS 實查(information_schema):`_en` schema 已不存在;`_view` 四個就位,view 完好:
  `F2204_view.bma_file / G2203_view.bma_file / M2201_view.bma_file / S2202_view.bma_file`
- `SELECT * FROM "M2201_view".bma_file LIMIT 1` 可查詢,欄位皆英文語意名(parent_item_number …)。
- API 冒煙(init-admin 登入,本機 compose → 真實 RDS):
  - `GET /semantic-mappings?page=1&page_size=2` → 200,total=12,280,items 為 RDS 真身資料。
  - `GET /semantic-mappings/tables` → 200,各表 draft/confirmed 計數。
  - `POST /semantic-mappings/sync-views` 連跑兩次 → `{"copied":12280,"regenerated":false,"created":0,"failed":0}`:副本整表重灌成功;confirmed 內容未異動 → 簽名命中略過重生(正確語意;view 已隨 user RENAME 就位)。
- 編輯 / 轉態 / 403 / 422 / 404 行為由 `test_semantic_mappings_api.py` 覆蓋(9 例全綠)。
- **UI 手測待 user**:管理頁(sidebar「語意層」分組)編輯 → 轉已複核 → 同步 view;member 帳號不可見;390px 寬度列表橫向捲動。

### 4. unused 命名修正(task-003)

- TSV:`grep -c "unused" semantic_draft.tsv` = **0**(修正前 287 筆 unused 前綴;實際改寫 290 筆,含空中文名列)。總列數 12,280 不變。
- re-seed 真實 RDS:`新增 0 / 更新 12246 / 略過(已複核)34`;重跑統計相同(冪等)。
- RDS 查證:`english_name LIKE 'unused%'` = 0 筆;`BMA_FILE` 34 筆 confirmed 未被覆寫;No Use 樣本(APT038→apt038 等)為欄名小寫。
- 例外:`FAT_FILE.FAT12`「NO USE 原因碼」為真語意欄位 → `no_use_reason_code`(draft,待複核)。

## 追加驗證(2026-07-21 下午,實作期 user 指示三項)

- **erp_metadata 排除(fixed #1)**:rebuild 後重觸發 target 快照同步(11:13:43–11:15:13,11,383 表)→ `GET /datasets/target/schemas` 僅回 DS / F2204 / G2203 / M2201 / S2202,`erp_metadata` 不再出現;`tests/test_introspect_exclusions.py` 綠。
- **全局快照進度條**:同步期間 `GET /datasets/target/snapshot/refresh/progress` 回 `{"active":true,"phase":"introspect","done":7481,"total":11383}`;`SnapshotProgress` 掛 layout 全頁可見,文案「快照同步中(原始資料 / ETL 資料)」與「ETL 同步中(手動 / 排程)」區分。
- **語意映射管理 Combobox**:改用 `TableSearchCombobox`(ETL 區塊同款);後端 keyword 加 `table_name`(中英四欄比對),`test_semantic_mappings_api.py` 9 例綠(含表名 / 中文關鍵字案例)。
- **殭屍 run 收殮(fixed #2)**:`etl_runs` pid=30 標 failed 後 `GET /runs/active` 回 null,全局 ETL 進度條消失。

## 殘留事項

1. **UI 人工複測**(user):快照同步進度條視覺、語意映射管理頁操作流、member 不可見、390px RWD。
2. 既有 mypy 錯誤 `schedule_repo.py:528`(非本版)。
3. 全數 commit 後走 `/scan-project` → `/reflect-rules`(升規候選:user 裁定「patch 開 propose」 vs `05-version-bump.md`)。
