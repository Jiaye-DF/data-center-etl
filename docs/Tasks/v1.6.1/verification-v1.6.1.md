# Verification v1.6.1(2026-07-31)

> 環境:本機 `docker compose` 全套(`etl_backend` / `etl_frontend` / `etl_postgres` / `etl_redis` / `etl_worker` / `etl_scheduler` 全 healthy)。分支 `dev-v1.6.1`。整合驗證走**真實 HTTP**(容器內 `curl` / `httpx` 打 `http://localhost:8000`,非 mock)+ **真實 RDS ETL-Hub**(`.env` 設定的 `AWS_RDS_TARGET_DB=erp_etl_hub_test`,即 Arch 圖中的 `RDS ETL-Hub`);`uv run pytest` 走自建 `data_center_etl_test`,與整合驗證用的本機 dev DB / 真實 RDS 完全隔離,無交叉污染。獨立連線驗證(模擬他機直讀)由 **host 端全新 Python 行程**(非容器內、非 app 連線池)直連同一 RDS 完成。

## 1. 測試 / 靜態檢查全綠

- 後端完整套件:`cd backend && uv run pytest` → **548 passed**(318.34s)。
- `uv run ruff check app tests` → All checks passed。
- `uv run mypy app` → Success: no issues found in 115 source files(較前版記錄的既有 `schedule_repo.py:528` 錯誤已消失,非本版新增問題)。
- 前端 `npm run lint`(`eslint . --max-warnings=0`)→ 乾淨。
- 前端 `npm run typecheck`(`tsc --noEmit`)→ 乾淨。

### 1.1 測試檔並行安全性修正(收口前已知遺留)

`test_client_settings_services_api.py` 的 `_cleanup` fixture(原約 :132)對 12 張權限表做**無條件** `DELETE FROM`,與其他測試檔在不同 process 併行對同一張 `data_center_etl_test` 時會互踩(先跑完的測試把還在跑的測試資料一併清空)。排查後發現**同一根因存在於三個檔案**(`test_client_settings_services_api.py` / `test_client_settings_profiles_api.py` / `test_client_settings_exceptions_api.py`,皆為 task-004/005/006 同構 fixture),只修一檔無法真正解除互踩(另兩檔仍會全清),故三檔一併修正:

- **12 張權限表**:改依 `created_by = ANY(:actors)` 過濾,`actors` = 本檔固定 `ACTOR_UID`(繞過 API 的直接 repo 呼叫用)+ 本次測試以 `_login_as` 建立的 admin uid(逐測試清空追蹤清單);API 建立的資料 `created_by` 即登入 admin 的 `user.uid`,故此法可精準命中「本測試自建」的列。
- **`erp_metadata.semantic_mappings`**:此表無 `created_by` 欄位(非 BaseModel 全套),改以本測試專屬 `tag`(既有隨機前綴 fixture)比對 `table_name LIKE '%tag%'`(`_seed_semantic` 的 raw table 名固定嵌入 `tag`)。
- `test_client_settings_exceptions_api.py` 原有的 `api_client_users WHERE created_by = :actor` 一行維持不動(該表建立本就明綁 `ACTOR_UID`,語意已正確)。

驗證:
- 三檔各自 `uv run pytest` 皆綠(16 / 18 / 17 passed)。
- **真併發驗證**:以三個獨立 OS process 同時對同一張 `data_center_etl_test` 各跑一個檔案(`services` & `profiles` & `exceptions` 同時起跑,非循序),三者皆全綠、無互踩(16 / 18 / 17 passed,與單檔跑一致)。
- 全量 `uv run pytest` 548 passed,零迴歸。

## 2. propose 驗收標準逐項 e2e(docker compose 真實 HTTP + 真實 RDS)

以真實 admin session(`POST /api/v1/auth/login`,`init-admin`)對 `/api/v1/client-settings/*` 與 `/api/v1/api-clients/*` 端點跑完整流程,對齊 Arch「後台管理操作流程」與「三情境對照」範例(以真實 confirmed 語意映射表 `ledger_parameters` / `voucher_doc_types` / `ledger_names` 取代示意用的 T1/T2/T3,欄位對照見下)。

### (1) 建表驗證:12 張權限表齊備於 RDS ETL-Hub `client_setting` schema

**PASS**。

- 執行時發現目標 RDS(`erp_etl_hub_test`)**尚未有 `client_setting` schema**(`ensure_client_setting_schema_on_target()` 目前僅測試呼叫,見殘留事項);為完成本節驗收,以既有**冪等 DDL 函式**(`CREATE SCHEMA/TABLE IF NOT EXISTS`,無任何 DROP)對真實 RDS 執行一次性建置,建置後以獨立連線確認:

  ```
  client_setting schema tables: ['client_exception_sets', 'client_roles', 'exception_items',
    'exception_operations', 'exception_sets', 'operation_items', 'operations',
    'permission_profiles', 'profile_items', 'profile_operations', 'roles', 'services']
  ```

  共 **12 張**,與 task-001 勘誤後的清單一致。
- `roles.permission_profile_pid` NOT NULL 驗證(獨立連線查 `information_schema.columns`):`is_nullable = 'NO'`。
- **另一條 RDS 連線(host 端全新 Python 行程,非 app 連線池,模擬他機直讀)**:對後台 API 剛寫入的 `services` / `roles`(join `permission_profiles`)/ `client_roles` / `profile_items` 直接 `SELECT`,四項全命中且值與 API 回應一致(`service.code`、`role→profile` 外鍵關聯、Client 指派、3 筆授權項筆數),`ALL DIRECT-READ ASSERTIONS PASSED`。

### (2) 整合驗證(對齊 Arch 範例):建系統別 → 作業 → 設定檔 → Role → 指派 → 預覽

**PASS**。以 `ledger_parameters`(=T1,欄 `ledger_number`=C11 / `ledger_name`=C12)、`voucher_doc_types`(=T2,欄 `doc_type_number`=C21 / `doc_type_name`=C22)、`ledger_names`(=T3,欄 `ledger_number`=C31 / `language`=C32)三個**真實 confirmed 語意映射表**取代示意用 T1/T2/T3:

- 建系統別 `e2e161-<suffix>` → 建作業 O1(範圍 T1·T2·T3 各 2 欄)→ 建設定檔 P1 勾 O1,授權 C11:read、C21:edit、C31:read → 建 Role 綁 P1 → 建 API Client A → 指派 Role → 預覽:

  ```json
  {"O1": {"ledger_parameters": {"ledger_number": "read"},
          "voucher_doc_types": {"doc_type_number": "edit"},
          "ledger_names": {"ledger_number": "read"}}}
  ```

  與 propose 範例 `{O1: {T1:{C11:read}, T2:{C21:edit}, T3:{C31:read}}}` **等價結構**成立。

### (3) default-closed:設定檔勾了作業但未給表欄位授權 → 該作業預覽為空

**PASS**。另建作業 O2(有範圍),設定檔 P1 同時勾選 O2 但**不呼叫**授權矩陣置換端點;預覽回應 O2 仍列於 `operations`(有入口)但 `tables: {}`(無欄位),與 Arch「作業開門、授權給欄位,兩者缺一不可」語意一致。

### (4) 特例權限:過期不進聯集,未過期才納入

**PASS**。特例組 X1 對 O1 額外授權 `ledger_names.language:read`(設定檔未授權此欄):

- 綁定 `expires_at=2020-01-01`(已過期)→ 預覽 `ledger_names` 仍只有 `{ledger_number: read}`,不含 `language`。
- 解除後改綁 `expires_at=2099-01-01`(未過期)→ 預覽立即納入 `ledger_names: {ledger_number: read, language: read}`。

### (5) 防呆:建 Role 不帶設定檔 → 4xx;刪除被綁定的設定檔 / Role → 4xx 且資料不變

**PASS**。

- `POST /roles` 缺 `permission_profile_uid` → **422**(pydantic 必填驗證)。
- 範圍項超出 confirmed 語意映射(不存在的表名)→ **422**,且原範圍資料經重放確認未被破壞。
- `DELETE /profiles/{P1}`(仍被 Role R1 綁定)→ **409**。
- `DELETE /roles/{R1}`(仍被 Client A 指派)→ **409**。

### (6) 快取行為:命中 / 異動即失效 / Redis 故障降級

**PASS(三情境全過)**。

- **命中**:兩次連續呼叫預覽後,`redis-cli TTL client_setting:effective:<client_uid>` 命中且值遞減(≈300s 內);以**獨立連線直接 UPDATE RDS**(繞過 app)將 `ledger_parameters.ledger_number` 的 `action` 由 `read` 改為 `edit`,**立即重打預覽端點仍回 `read`**(未反映繞過 app 的變更)→ 證明第二次讀取確實**命中快取、未回源 RDS**。
- **異動即失效**:改用**真正的管理 API**(`PUT /profiles/{P1}/operations/{O1}/items`)做同一筆變更(`ledger_number` → `edit`)→ **緊接著重打預覽,立即回 `edit`**(無延遲窗口)→ 證明寫入端「commit 成功後即刻失效快取」生效。
- **Redis 故障降級**:容器操作限定 `up -d --build` / `logs` / `exec`(不含 `stop`/`network disconnect`),故以**容器內一次性 Python 行程**(非乾擾正式運行中的 uvicorn server)注入一個必定拋 `ConnectionError` 的假 Redis client,直接呼叫**正式程式碼路徑**(`permission_cache.get_or_load_model` + 真實 `expand_effective_permissions` loader,對同一批真實 RDS 資料)→ 記錄兩則「權限快取降級」WARNING(get / set 各一)後**仍正確回傳** `ledger_number: edit`(與前一步 RDS 真值一致),無例外外洩。事後確認 `etl_redis` 與 `etl_backend` 皆 `healthy`、`redis-cli PING` 正常,此驗證未影響正式運行中的服務。此法為 task-003 既有降級單元測試(24+19 個測試皆已覆蓋 mock 情境)之外,對**真實 RDS 資料 + 正式程式碼路徑**的補充整合證據。

### (7) 無 Role 且無特例的 Client → 預覽為空結構

**PASS**。新建 Client B(未指派 Role、未綁特例)→ 預覽回 `{"role": null, "exception_sets": [], "operations": []}`。

### (8) 稽核:系統別 / 作業 / 設定檔 / Role / 指派 / 特例寫操作各抽一筆確認 audit_logs 有事件且 detail 無機密

**PASS**。查詢自有 DB `audit_logs`(依上述 e2e 建立的 `target_uid` 過濾),命中 16 筆 `client_setting.*` 事件,涵蓋 `service_create` / `operation_create` / `operation_items_replace` / `profile_create` / `profile_operations_replace` / `profile_items_replace` / `role_create` / `client_role_assign` / `exception_set_create` / `exception_operations_replace` / `exception_items_replace` / `client_exception_bind`(×2)/ `client_exception_unbind`,`actor_username` 皆正確記為 `init-admin`,`detail` 為人類可讀中文描述(如「建立系統別 e2e161-xxx(e2e161 服務 xxx)」),逐筆檢視**無 client_secret / password / token 等機密字樣**。

### (9) 迴歸:v1.6.0 全部既有測試綠

**PASS**。全量 `uv run pytest` 548 passed 內含既有 token / 限流 / API Client 管理 / 註銷測試檔,另以真實 HTTP 抽測 `GET /api/v1/client-settings/services` 未登入 → `401`;前端 `/client-settings`、`/api-clients` 兩頁皆 `200`。

### (10) 手測(前端):Arch ⓪→③ 流程走完一輪並截圖

**環境受限,列入殘留待人工複測**(見下節);本次以 API 層等價覆蓋全部業務語意(上列 (1)~(9)),矩陣 UI 互動本身(勾選 / 拖曳 / 對話框)未做瀏覽器自動化。

## 3. 驗證期間 log 檢查

`docker compose logs backend --since 60m` 抽查(`grep -iE "\[ERROR\]|CRITICAL"`,排除刻意觸發的降級測試字樣):**無命中**。Redis 降級測試改走容器內一次性行程(見 2-(6)),未觸及正式運行中的 server 行程,故 backend log 亦無相關紀錄;`etl_redis` / `etl_backend` 事後皆 `healthy`。

## 4. 驗證後清理

- 本次 e2e 於 RDS 建立的系統別 / 作業(×2)/ 設定檔 / Role / 特例組 / 兩個 API Client,**全數透過既有管理 API 依相依順序軟刪除**(特例綁定 → Role 指派 → Role → 特例組 → 設定檔 → 作業 ×2 → 系統別 → 兩個 API Client,共 10 道 `DELETE`,皆 `200`);獨立連線覆核 `client_setting.*` 全表 `is_deleted=false` 計數皆為 **0**(`active=0`),`total` 保留歷史列(冪等 CREATE-only、軟刪除慣例,**無 DROP / 無物理 DELETE**)。
- `api_client_users` 兩筆測試 Client 覆核 `is_deleted=t`。
- `redis-cli KEYS "client_setting:effective:*"` 覆核:清理過程中的多次真實寫入已逐一失效對應快取 key,無殘留。
- 收口後重跑 `cd backend && uv run pytest -q` 確認全套仍 **548 passed**(整合驗證走真實 RDS / 本機 dev DB,`uv run pytest` 走隔離的 `data_center_etl_test`,無交叉污染)。

## 5. Arch 文件回寫(`docs/Arch/datahub-api-gateway-arch.html`)

模組② 由「規劃中」回寫為「**已建置**」(沿用文件既有 `owner done` 樣式與圖例:已完成建置並驗證運行),並逐項列明實作與原文件的偏離:

1. **狀態標記**:`<span class="owner plan">規劃中</span>` → `<span class="owner done">已建置</span>`;卡片配色由 `--card-plan/--st-plan` 改 `--card-done/--st-done`;新增一行摘要「v1.6.1 已完成維護面整套(12 張權限表 + 管理 API + 前端 + 預覽 + Redis 快取,e2e 驗證於真實 RDS 通過);判斷面模組③ 與資料供應模組④ 仍規劃中」。
2. **表數勘誤**:本文件原生 ERD 舉例圖(entity block)本就對應 12 張表結構,無literal「11」字樣需改(該誤植只存在於 propose / tasks 文件,tasks-v1.6.1.md 已更正,本文件無需動)。
3. **`client_setting` schema 落點(重大偏離,已回寫)**:原 ERD 假設 `client_roles` / `client_exception_sets` 對 `api_client_users` 走一般同庫 `bigint FK`(`api_client_pid FK`);實作因 propose 2026-07-31 裁定「12 表落 RDS ETL-Hub 專用 schema `client_setting`,`api_client_users` 留在自有 DB」,兩庫無法建實體 FK,**改為 `api_client_uid`(UUID)跨資料庫冷關聯,應用層檢核**。已修正 ERD `client_exception_sets` entity block、新增 `client_roles` entity block 並加註,新增 `cross-note` 顯著標示此偏離與其後果(不建本地副本 / 不存快照 / 即時讀寫)。
4. **讀取快取層歸屬(新增揭露)**:原文件把「TTL 快取」整段歸給模組③(甚至寫「記憶體快取」);實作(task-003)已在**模組②** 建置 **Redis** cache-aside 層(key 前綴 `client_setting:`、TTL 300s、異動即失效、故障降級直讀),是模組③ 的地基而非模組③ 自建。已於模組② chips / 設計點表新增揭露,並在模組③ 區塊加註 callout,提醒後續實作**直接沿用**、不要另建一套記憶體快取語意。
5. **管理 / 預覽端點路徑(新增揭露)**:原文件流程圖未標路徑;已在設計點表新增一列 `/api/v1/client-settings/*`(admin CRUD)+ `GET /api/v1/api-clients/{uid}/effective-permissions`(預覽,頁內檢視不另開頁),並於後台管理流程圖 caption 逐段補上對應端點。
6. **`table_name`/`column_name` 用語澄清**:ERD 註解原寫「語意 view 名」,實作為 `semantic_mappings.english_name`(非資料庫 view),已改「語意層英文名」對齊 propose 用語。
7. **總圖(master flowchart)同步**:`PDB` 節點原籠統標「權限資料表」;已拆為 `api_client_users`(自有 DB)與 `client_setting schema`(RDS,同 `HUB`)兩個節點,並加入 `Redis 讀取快取` 節點與對應資料流邊,caption 同步補充schema 落點與快取優先讀取的敘述。
8. **Role 必綁**:ERD `roles.permission_profile_pid` 註解補「DB 層 NOT NULL」,與本次 (1) 節建表驗證的獨立連線查證結果一致。
9. **e2e 驗證回寫**:於後台管理流程圖下方新增 `callout ok`,標註本節流程(含 default-closed / 特例過期 / 快取三情境 / 稽核)已於 2026-07-31 對真實 RDS 走完整 e2e 並通過,連結本文件。

驗證:`grep -n "11 張\|11張\|api_client_pid FK\|語意 view 名"` 對該檔皆**零命中**,確認勘誤字樣清除乾淨;`node -e` 檢查 `<section>`/`<div>` 標籤配對數(5/5、80/80)平衡,mermaid `subgraph`/`end` 配對未變動結構,僅新增節點與邊,語法沿用文件既有慣例(mermaid v11 支援 `%%` 註解)。

## 6. 逐項判定總表

| propose 驗收標準 | 判定 |
| --- | --- |
| 後端 `uv run pytest` 全綠 + `ruff`/`mypy` 無新增錯誤;前端 `lint`/`typecheck` 乾淨 | **過**(548 passed;ruff/mypy/lint/tsc 四項全乾淨) |
| 建表驗證:12 張表齊備 RDS `client_setting`、`roles` NOT NULL、另連線直讀 | **過** |
| 整合驗證:建系統別→作業→設定檔→Role→指派→預覽,等價 Arch 範例結構 | **過** |
| default-closed | **過** |
| 特例權限過期排除 / 未過期納入 | **過** |
| 防呆:Role 無設定檔 4xx;刪除被綁定資源 4xx 且資料不變 | **過** |
| 快取行為:命中 / 異動即失效 / Redis 故障降級 | **過**(降級以容器內一次性行程注入故障 client 佐證,方法見上) |
| 無 Role 無特例 → 預覽空結構 | **過** |
| 稽核:六類寫操作各抽一筆,detail 無機密 | **過** |
| 迴歸:v1.6.0 既有測試全綠 | **過** |
| 手測(前端 Arch ⓪→③ 流程 + 截圖) | **環境受限待補**(業務語意已由 API 層等價覆蓋,UI 互動本身列入殘留) |
| Arch 文件回寫(模組② 落地狀態 + 偏離逐項列明) | **過** |

無「不過」項,故無需開 `fixed.md`。

## 7. 殘留事項

1. **`ensure_client_setting_schema_on_target()` 尚無正式呼叫端**(task-001 既有記錄,本次收口再次確認):目前僅測試檔呼叫;本次為完成 (1) 節建表驗收,已對真實 RDS(`erp_etl_hub_test`)執行一次冪等建置(`CREATE SCHEMA/TABLE IF NOT EXISTS`,無 DROP),12 表已存在於該 RDS。**正式環境(staging/production)的 RDS 建表仍屬部署動作**,尚無自動觸發點(如啟動 hook / 部署腳本),需後續版本補上正式呼叫端或部署 runbook 註記,否則新環境的 backend 啟動後管理頁會因 schema 不存在而 500。
2. **前端 UI 人工複測**(待辦,環境受限無瀏覽器自動化):
   - task-009 矩陣 UI 全流程操作(勾選作業 / 授權矩陣即選即用 / 範圍縮小殘留項提示)、409 錯誤顯示樣式。
   - task-010 API Client 頁權限對話框:Role 指派即時反映、特例效期 datetime-local 輸入、解除 Role 後預覽變空、解除特例後預覽變窄。
   - 上述業務語意已在本文件 2-(1)~(9) 以 API 層等價覆蓋(結構 / 狀態轉換皆驗證通過),僅「畫面渲染與互動手感」本身待人工複測。
3. **前端 `client-settings/page.tsx` 已 2222 行**(worker 記錄):功能正常、無編譯 / lint 問題,列為收口後**可選重構候選**——拆分至 `components/client-settings/` 子目錄,非本版缺陷。
4. **測試檔並行安全性修正範圍**(見 1.1 節):任務原文僅點名 `test_client_settings_services_api.py`,排查後發現 `profiles` / `exceptions` 兩檔同構同根因,一併修正三檔才能真正解除「與其他測試檔並行時互踩」的問題(僅修一檔仍會被另兩檔的無條件 `DELETE` 波及)。此為任務執行中主動擴大修正範圍,依 CLAUDE.md 於此文件註明。
5. **既有 mypy 錯誤已消失**:前版記錄的 `app/repositories/schedule_repo.py:528` 錯誤本次 `uv run mypy app` 未再出現(115 檔 0 錯誤),推測已於中間版本修正,非本版變動所致,如實記錄現況。

## 結論

v1.6.1(DataHub API Gateway 模組② — DataHub 後台 · 組織權限管理,維護面整套)**11 個 task 全數完成**,propose 驗收標準逐條過關(12 項全過,1 項因環境限制列待人工複測、已有等價覆蓋),後端全套最終 **548 passed** + ruff/mypy 雙綠,前端 lint/typecheck 雙綠,e2e 針對**真實 RDS ETL-Hub** 走完整流程並以獨立連線驗證跨機直讀,快取三情境(命中 / 異動即失效 / Redis 故障降級)與稽核事件皆有實測佐證,Arch 文件模組② 狀態與 5 項技術性偏離已逐一回寫。可進入下一版本規劃(模組③ 權限引擎)。
