# Verification v1.5.2(2026-07-23)

> 環境:本機 docker compose 全套(etl_backend / etl_frontend / etl_postgres / etl_redis / etl_worker / etl_scheduler 全 healthy)。drift 情境(來源加欄 → 同步)一律用本機測試 DB(`data_center_etl_test`,port 5435,容器內網 `postgres:5432`)同時扮演 source / target,對齊 `backend/tests` 既有整合測試慣例;不對真實 AWS RDS 做任何 DDL / 寫入,真實 RDS(`erp_etl_hub_test`)僅唯讀 SELECT 抽查。分支 `dev-v1.5.2/schema-drift`。

## 1. 測試 / 靜態檢查全綠

- 後端完整套件:`cd backend && uv run pytest` → **339 passed**(修正 test isolation 後,見「發現與修正」)。
- `uv run ruff check app tests` → All checks passed。
- `uv run mypy app` → 僅既有 `app/repositories/schedule_repo.py:528`(`Result[Any]` 無 `rowcount`)一筆錯誤,非 v1.5.2 新增(對齊 v1.5.1 / v1.5.0 verification 既有記錄)。

### 發現與修正(task-004 範圍內的測試穩定性)

- 全套執行時發現 `tests/test_seed_semantic_mappings.py::test_seed_creates_draft_rows` 偶發失敗(斷言列數 3,實得 190/187):根因為共用本機測試 DB 存在其他測試檔案遺留的 schema(`AF_TEST` / `VG_TEST` / `IX_TEST` 等,因規範禁 DROP 只能 `CREATE ... IF NOT EXISTS` 累積跨執行殘留),且 task-003 掛接後 `mirror_sync` 測試(`test_mirror_sync_*.py`)會實跑 `autofill_semantic_mappings` 對整個測試 DB 做全 schema 掃描,連同遺留 schema 一併補 confirmed 列,污染本檔原本「先跑 → 表必為空」的隱性順序假設。
- 修正:`tests/test_seed_semantic_mappings.py` 的 `_clean_semantic_mappings` fixture 改為前後皆清空(對齊 `test_semantic_autofill.py` 既有模式),不再依賴執行順序。修正後全套重跑兩次(含 e2e 腳本操作後)皆 339 passed,零 flaky。
- 此修正僅動測試檔案(非 production code),不影響 task-001/002/003 之驗收範圍;根因屬既有「共用測試 DB 不可 DROP,長期累積 schema」設計已知取捨(v1.5.1 起即存在),task-003 的全 schema 掃描讓此弱點首次外顯為斷言失敗。**建議 reflect-rules 候選**:測試檔案凡有精確計數斷言者,一律「前後雙清」而非僅「後清」,避免依賴檔案執行順序。

## 2. 對 propose 驗收標準逐項(整合驗證 + 腳本化 e2e 重現)

> 統一腳本 `e2e_v152.py`(暫存,未入版控):在 `data_center_etl_test` 建來源測試表 `V152_E2E_R2.DEMO_FILE`(2 欄)→ mirror 首次同步 → 來源加 `COL_C` 欄補資料 → 再次 mirror 同步 → `autofill_semantic_mappings` → `refresh_semantic_copy_and_views`(副本重灌 + view 重生)→ ASGI 呼叫真實 FastAPI app 驗證 JSON 查詢與語意映射管理 API(PATCH 改名 + `POST /sync-views`)。全程呼叫**真實**(未 mock)v1.5.2 程式碼路徑(`write_mirror` / `autofill_semantic_mappings` / `refresh_semantic_copy_and_views` / `DataQueryService` / `SemanticAdminService`)。

### (1) 既有表 + 來源加欄 → 同步後目標表出現該欄且資料進入(task-001)

**PASS**。來源表原 2 欄(`COL_A`/`COL_B`)首次同步寫入 2 筆;來源 `ALTER TABLE ADD COLUMN "COL_C"` 補值後,再次呼叫 `write_mirror` 實測:

```
target_cols=['COL_A', 'COL_B', 'COL_C'], COL_C data=['C1', 'C2'], written2=2
```

目標表自動出現 `COL_C` 且資料完整寫入,無需人工介入。單元測試面另有 `backend/tests/test_mirror.py` 三情境(加欄補 / 目標殘欄不動 / 無 drift 無 ALTER)全綠佐證。

### (2) `semantic_mappings` 出現 confirmed 列(english=小寫原欄名/zh=字典值或空/updated_by=全零)(task-002)

**PASS**。`autofill_semantic_mappings` 對上述表實測:

```
補欄 2 / 補表層級 1 / 別名規避 0
COL_B: english_name=col_b, status=confirmed, updated_by=00000000-0000-0000-0000-000000000000
COL_C: english_name=col_c, status=confirmed, updated_by=00000000-0000-0000-0000-000000000000
表層級('') : english_name=demo_file, status=confirmed, updated_by=00000000-0000-0000-0000-000000000000
```

欄層級與表層級皆正確補列;`zh_name` 因測試表無 DS 字典對應,如預期落空字串(字典取值行為另有 `test_semantic_autofill.py::test_autofill_zh_name_from_dictionary_else_empty` 覆蓋)。

### (3) 同輪後該表 view 含新欄位;`/api/v1/data` JSON 查詢回應含新 key(task-003)

**PASS(a:view)**。`refresh_semantic_copy_and_views` 執行後(log:「view 重生完成:28 個 view」),`information_schema.columns` 實查 `V152_E2E_R2_view.demo_file`:

```
view_cols=['col_a_human_confirmed', 'col_b', 'col_c']
```

**PASS(b:JSON API)**。以 ASGI 呼叫真實 app(`GET /api/v1/datasets/target/tables/V152_E2E_R2/DEMO_FILE/rows`,admin 登入):

```
status=200
row_keys={'col_a_human_confirmed', 'col_b', 'col_c'}
rows=[{'col_a_human_confirmed': 'A1', 'col_b': 'B1', 'col_c': 'C1'}, {'col_a_human_confirmed': 'A2', 'col_b': 'B2', 'col_c': 'C2'}]
```

同一輪同步結束,view 與 JSON 查詢皆已涵蓋新欄位,無需二次同步。

### (4) 既有映射列不覆寫:抽 BMA_FILE confirmed 樣本,自動補列前後 diff 為空

**PASS(本機測試 DB,結構驗證)**:於 e2e 腳本插入一筆模擬「既有人工 confirmed」列(`COL_A` → `col_a_human_confirmed`,含自訂 `zh_name` / `updated_by`),`autofill_semantic_mappings` 執行前後 diff：

```
before=('col_a_human_confirmed', '人工複核值', 'confirmed', UUID('...'))
after =('col_a_human_confirmed', '人工複核值', 'confirmed', UUID('...'))
```

diff 為空,既有列未被覆寫。單元測試面另有 `test_semantic_autofill.py::test_plan_autofill_does_not_overwrite_existing_draft_or_confirmed`(draft / confirmed 皆涵蓋)佐證邏輯層。

**真實 RDS BMA_FILE 唯讀抽查(基準快照)**:連真實 `erp_etl_hub_test`(唯讀 SELECT,未執行任何寫入 / DDL)：

```sql
SELECT count(*) FROM erp_metadata.semantic_mappings
WHERE table_name='BMA_FILE' AND status='confirmed';
-- confirmed count: 34
```

與 v1.5.1 verification 記錄的基準值(34 筆 confirmed)一致,v1.5.2 程式碼尚未於真實 RDS 執行過同步,現況為未變動基準快照。**真實 RDS 上「v1.5.2 autofill 執行後 diff 為空」待部署後重跑同步時再比對本次快照確認**。

### (5) 手測:管理頁把自動列英文名改正式名 → 同步 view → view 欄名更新(42P16 重建路徑)

**API 面向 PASS**;**UI 操作待 user 人工複測**(比照 v1.5.1 慣例)。

- `PATCH /api/v1/semantic-mappings`(`COL_C` 英文名改為 `demo_col_c_renamed`)→ `200`。
- `POST /api/v1/semantic-mappings/sync-views` → 首次呼叫實測 `202`(worker 確實消費,見下方 worker log);因腳本間隔時間短於 AD-120 鎖 TTL(600s),同輪內連續第二次呼叫觸發互斥鎖回 `409`(**設計預期行為**,非缺陷 — 證明跨 process 互斥鎖正常運作,見下段佐證)。
- 直接呼叫 `refresh_semantic_copy_and_views`(等效驗證同步結果)後,`information_schema.columns` 實查 `V152_E2E_R2_view.demo_file`:

```
view_cols_after_rename=['col_a_human_confirmed', 'col_b', 'demo_col_c_renamed']
```

`col_c` 已不存在、`demo_col_c_renamed` 出現,42P16(欄位集合不相容 → 改走重建流程)路徑實測觸發且成功(log:`CREATE OR REPLACE VIEW 欄位集合不相容(42P16),改走重建流程`)。

**202/409 佐證**(`docker compose logs worker`):

```
etl_worker | ...T14:11:41.262+08:00 [INFO] taskiq.receiver.receiver: Executing task semantic_apply with ID: fc82...
```

Redis 實查 `data-center-etl:semantic-apply:lock` TTL ≈ 310s(尚未過期)確認該次 409 純屬鎖未釋放的正常互斥,非功能缺陷。

- **UI 待複測項**(user):語意映射管理頁點擊「改名」→「同步 view」按鈕實際操作流、載入狀態呈現。

## 3. 驗證期間 run log 無新增 ERROR

`docker compose logs backend worker --since 30m` 抽查(grep `\[ERROR\]|CRITICAL`,排除既有「未知來源型別」warning 雜訊):**無命中**,驗證期間無新增 ERROR 級訊息。

## 4. 驗證後回歸

- 清理 e2e 腳本產生的映射 / 快照列(`DELETE`,非 DROP;來源 / 目標測試 schema `V152_E2E*` 依既有測試慣例保留結構不刪)。
- `cd backend && uv run pytest` 全套重跑確認:**339 passed**,零 flaky。

## 殘留事項

1. **UI 人工複測**(user):語意映射管理頁「改英文名 → 同步 view」操作流、42P16 重建後前端顯示。
2. **真實 RDS 待部署後重跑**:項 (1)(2)(3) 之真實 AWS RDS(`erp_migration_test`/`erp_etl_hub_test`)端到端(本機測試 DB 已驗證邏輯與路徑一致);項 (4) 已記錄 BMA_FILE 34 筆 confirmed 部署前基準快照,待部署後首輪同步再核對 diff。
3. 既有 mypy 錯誤 `schedule_repo.py:528`(非本版新增)。
4. Reflect 候選:測試檔精確計數斷言應「前後雙清」而非「僅後清」,避免共用測試 DB 跨檔案執行順序污染(本次已修正 `test_seed_semantic_mappings.py` 一例,其餘檔案可抽查比照)。
