# v1.5.0 端到端收口驗證紀錄

> worker: claude-I(task-009)
> 執行日期:2026-07-20
> 執行方式:`docker compose up -d --build` 完整環境(非 start-dev);目標 AWS RDS(`erp-oracle-test-pg.*.rds.amazonaws.com`)實測**可連線**(初次以 bash `/dev/tcp` 阻塞讀取誤判不可達,改用 `docker run postgres:18-alpine psql` 驗證後確認可連);故本次以**真實 RDS**(`erp_migration_test` / `erp_etl_hub_test`)走完全鏈路,非本地替代。逐條覆核 propose 對外承諾與 Acceptance,樣本表如下說明另行替換。

## 環境狀態

```
$ docker compose ps --format "table {{.Name}}\t{{.Status}}"
NAME            STATUS
etl_backend     Up 17 minutes (healthy)
etl_frontend    Up 17 minutes (healthy)
etl_postgres    Up 2 hours (healthy)
etl_redis       Up 2 hours (healthy)
etl_scheduler   Up 17 minutes (healthy)
etl_worker      Up 17 minutes (healthy)
```

全容器 healthy,無 unhealthy / restarting。**pass**

## 樣本表選擇說明(偏離前手交接建議)

前手交接建議樣本表 `GEN_FILE`(員工)。實測發現:目標 RDS(`erp_etl_hub_test`)僅有 `DS` / `M2201` 兩個帳套 schema(來源 `erp_migration_test` 另有 `G2203`/`S2202`/`F2204`,但目前僅 `DS`/`M2201` 已鏡像到 target),`GEN_FILE`/`GEM_FILE` 實體表位於 **`DS`** schema(779 / 409 列),`M2201` 無此實體表。但 `app/etl/view_generator.py::_list_target_schemas` 明確排除 `DS`(字典 schema,`DS_SCHEMA = "DS"`)不進 view 產生迴圈,若仍選 `GEN_FILE` 會導致**永遠無法產生語意化 view**,無法驗證 Acceptance 第 6 條。

改選 **`M2201.BMA_FILE`**(65 列 / 33 欄,task-002 文件自身範例即用此表)作為主樣本表;另用 **`M2201.AQE_FILE`** 驗證 B3(GAQ04/05 附加,見第 7 條)。已於下方紀錄改用原因,不影響驗收條目本身。

---

## 1. `docker compose up -d --build` 全服務 healthy

見上「環境狀態」。**pass**

## 2. 草稿匯入:`seed_semantic_mappings.py`

```
$ docker compose exec backend python scripts/seed_semantic_mappings.py --tsv /tmp/semantic_draft.tsv
seed 完成:新增 12280 / 更新 0 / 略過(已複核) 0

# 冪等重跑
$ docker compose exec backend python scripts/seed_semantic_mappings.py --tsv /tmp/semantic_draft.tsv
seed 完成:新增 0 / 更新 12280 / 略過(已複核) 0

# RDS 實測計數
$ psql ... -d erp_etl_hub_test -c "SELECT count(*), count(*) FILTER (WHERE status='draft'),
    count(*) FILTER (WHERE status='confirmed'), count(*) FILTER (WHERE column_name='')
    FROM erp_metadata.semantic_mappings;"
 count | draft | confirmed | table_level
-------+-------+-----------+-------------
 12280 | 12280 |         0 |         333
```

（`--tsv` 指向容器內路徑:image 未含 `docs/`,以 `docker cp` 把 TSV 送入容器 `/tmp/`,不影響腳本邏輯本身,腳本預設路徑於本機直跑 `backend/` 目錄時可正常解析 repo 內建路徑）

12,280 = 333 表層級 + 11,947 欄,與 Acceptance 數字一致;二次執行筆數不變、冪等成立。**pass**

## 3. 樣本複核:`--confirm-table BMA_FILE`

```
$ docker compose exec backend python scripts/seed_semantic_mappings.py --confirm-table BMA_FILE
複核轉態完成:BMA_FILE 共 34 列轉為 confirmed

$ psql ... -c "SELECT count(*) FILTER (WHERE status='confirmed') FROM erp_metadata.semantic_mappings WHERE table_name='BMA_FILE';"
 count
-------
    34
```

34 = 1(表層級)+ 33(欄)。**pass**

## 4. 觸發 ETL 同步 → 自有 DB 副本與 RDS 一致;轉換 cache 失效

```
$ curl -s -b cookies -X POST http://localhost:8000/api/v1/sync/table \
    -d '{"schema_name":"M2201","table":"BMA_FILE"}'
{"success":true,"data":{"task_id":"...","scope":"table"},"response_code":202}

$ curl -s -b cookies "http://localhost:8000/api/v1/runs?limit=1"
{"uid":"1c09b16f-...","status":"success","total_tables":1,"success_tables":1,"failed_tables":0}
```

筆數比對(RDS vs 自有 DB 副本):

```
RDS      : count=12280, confirmed(BMA_FILE)=34
自有 DB  : count=12280, confirmed(BMA_FILE)=34
```

抽樣列比對(`BMA_FILE` 表層級 + `BMA01` + `BMA07`):RDS 與自有 DB 副本三列內容(english_name/zh_name/status)**逐字元一致**。

轉換 cache / view 重生同一時點:worker log 顯示同步完成後即觸發

```
etl_worker  [INFO] app.etl.view_generator: view 重生完成:1 個 view
```

之後對同一 mapping 再次觸發同步(`AQE_FILE`,mapping 內容未變)驗證重生僅在異動時觸發:

```
etl_worker  [INFO] app.etl.view_generator: confirmed 映射內容未異動,略過 view 重生
```

`mirror_sync` 內同步完成後亦執行 `cache.delete_pattern("datasets:source:*")`(原始資料管理清單快取失效),第 5/8 條 API 讀到的皆為同步後最新快照,間接驗證快取已失效。**pass**

## 5. JSON API:key 轉英文、未複核表 404

```
$ curl -s -b cookies "http://localhost:8000/api/v1/datasets/source/tables/M2201/BMA_FILE/rows?limit=3"
{"success":true,"data":{"rows":[{"parent_item_number":"0103002001005","last_ecn_number":null,
  ...,"data_owner":"01431"}, ...],"total_returned":3,
  "columns":[{"english_name":"parent_item_number","zh_name":"主件料件編號"}, ...]}}

# 無 bma01 類魔術 key
$ curl -s -b cookies ".../M2201/BMA_FILE/rows?limit=3" | grep -o '"bma01"'; echo exit=$?
exit=1   # 無命中

# 未複核表(OBA_FILE,全 draft)→ 404
$ curl -s -b cookies ".../M2201/OBA_FILE/rows"
{"success":false,"data":null,"detail":"指定資料表不存在或尚未複核","response_code":404}

# 未登入 → 401
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/datasets/source/tables/M2201/BMA_FILE/rows
401
```

回傳 key 全為 confirmed 英文名、無魔術 key、未複核表 404、未登入 401。「未 confirmed 欄不出現」的欄位級混合案例(同表部分 draft/部分 confirmed)已由 `test_data_query_api.py`(第 9 條全套件內,280 passed 含此檔)覆蓋,e2e 未重複造混合案例(BMA_FILE 樣本表已整表複核,無混合可測)。**pass**

## 6. view:`M2201_en.bma_file` 存在,欄名英文,mapping 更新後重生

```
$ psql ... -d erp_etl_hub_test -c "\d \"M2201_en\".bma_file"
                     View "M2201_en.bma_file"
        Column       |            Type
---------------------+------------------------------
 parent_item_number  | character varying(40)
 last_ecn_number     | character varying(20)
 ...(33 欄,全英文別名)

$ psql ... -c "SELECT * FROM \"M2201_en\".bma_file LIMIT 1;"
 parent_item_number | ... | data_creation_department
 0201001001001      | ... | DB00
(1 row)
```

view 於第 4 條同步時同時重生(見上 log);第二次同步(mapping 未變)確認略過重生,滿足「mapping 更新後重跑,view 定義同步更新;未變動不重跑」。**pass**

## 7. comment 覆核(B1/B3)

DMS 前置實測**已達成**(與前手交接「大概率未加」預期不同,本次實測 `DS.GAE_FILE` 已在來源 RDS 存在):

```
$ psql ... -d erp_migration_test -c
  "SELECT table_schema, table_name FROM information_schema.tables
   WHERE table_schema='DS' AND table_name='GAE_FILE';"
 table_schema | table_name
--------------+------------
 DS           | GAE_FILE
```

**B1 缺漏欄數統計**(verify SQL,對 M2201 有資料 333 表全量欄位、非僅樣本表;純字典查詢,免整批重灌 333 表資料):

```sql
WITH target_tables AS (SELECT unnest(ARRAY[...333 個表名...]) AS t),
m2201_cols AS (SELECT lower(table_name) tbl, lower(column_name) col
    FROM information_schema.columns
    WHERE table_schema='M2201' AND lower(table_name) IN (SELECT t FROM target_tables)),
gaq_zh AS (SELECT DISTINCT lower("GAQ01") col FROM "DS"."GAQ_FILE"
    WHERE "GAQ02" IN ('0','2') AND btrim("GAQ03") <> ''),
gae_zh AS (SELECT DISTINCT lower("GAE02") col FROM "DS"."GAE_FILE"
    WHERE "GAE03" IN ('0','2') AND btrim("GAE04") <> '')
SELECT (SELECT count(*) FROM m2201_cols) total_column_pairs,
       (SELECT count(*) FROM m2201_cols WHERE col IN (SELECT col FROM gaq_zh)) covered_by_gaq,
       (SELECT count(*) FROM m2201_cols WHERE col NOT IN (SELECT col FROM gaq_zh)) gaq_missing,
       (SELECT count(*) FROM m2201_cols WHERE col NOT IN (SELECT col FROM gaq_zh)
          AND col IN (SELECT col FROM gae_zh)) gaq_missing_covered_by_gae,
       (SELECT count(*) FROM m2201_cols WHERE col NOT IN (SELECT col FROM gaq_zh)
          AND col NOT IN (SELECT col FROM gae_zh)) still_missing_after_gae;
```

```
 total_column_pairs | covered_by_gaq | gaq_missing | gaq_missing_covered_by_gae | still_missing_after_gae
---------------------+----------------+-------------+-----------------------------+--------------------------
               11947 |          11756 |         191 |                         126 |                       65
```

與 `docs/ERP-Analyze/mapping-alignment.md` §3 靜態分析數字**完全吻合**(191 缺漏、126 可由 GAE 補、65 兩者皆無)。**同步後 comment 缺漏欄數 = 65,滿足 `≤65` 驗收標準。**

實際同步樣本佐證(`M2201.BMA_FILE`,COMMENT 已套用):`BMA01`→`主件品號`(GAQ 直接命中)、`BMA07`/`BMAICD01`/`BMA09`→空(TSV 標記「原名」,GAQ 與 GAE 皆無對應,屬上述 65 欄不可避免殘餵之一)。

**B3 GAQ04/05 附加**(另用 `M2201.AQE_FILE.AQE00` 驗證,因 `BMA_FILE` 33 欄皆無 GAQ04/05 值):

```
$ curl -s -b cookies -X POST http://localhost:8000/api/v1/sync/table -d '{"schema_name":"M2201","table":"AQE_FILE"}'

$ psql ... -c "SELECT col_description('\"M2201\".\"AQE_FILE\"'::regclass, attnum) FROM pg_attribute
   WHERE attrelid='\"M2201\".\"AQE_FILE\"'::regclass AND lower(attname)='aqe00';"
 代收付類別；0-代付 1-代收 2-收付對沖；For 內部帳戶
```

格式 `<中文名>；<GAQ04>；<GAQ05>`,與 GAQ03 重複值不附加(task-006 邏輯,單元測試 14/14 已覆蓋)。**pass(B1 前置已達成、缺漏數精確驗證;B3 real-data 驗證通過)**

## 8. 模組分類:資料集頁按模組篩選(API 等效驗證)

無頭環境無法操作瀏覽器下拉,依前手交接以 `?module=` curl 等效驗證:

```
# 先跑 snapshot refresh(module_code 來自 GAT06,隨 refresh 批次寫入快照)
$ curl -s -b cookies -X POST http://localhost:8000/api/v1/datasets/source/snapshot/refresh
{"success":true,"data":{"dataset":"source","table_count":11385,"snapshot_at":"..."}}

$ psql (自有 DB) -c "SELECT count(*), count(*) FILTER (WHERE module_code IS NOT NULL AND module_code<>'')
   FROM rds_table_meta WHERE dataset='source' AND schema_name='M2201' AND row_count>0;"
 count | with_module
-------+-------------
   333 |         314   -- 19 筆 module_code 為空(「未分類」候選,前端歸類)

$ curl -s -b cookies "http://localhost:8000/api/v1/datasets/source/tables?schema=M2201&module=AEC&page_size=10"
{"items":[{"name":"ECA_FILE","module_code":"AEC",...},{"name":"ECG_FILE","module_code":"AEC",...},
  {"name":"ECI_FILE","module_code":"AEC",...},{"name":"ECN_FILE","module_code":"AEC",...}],"total":4}

# 不帶 module(全部)
$ curl -s -b cookies "http://localhost:8000/api/v1/datasets/source/tables?schema=M2201&page_size=1" | grep -o '"total":[0-9]*'
"total":333
```

篩選 `module=AEC` 精準命中 4 表(皆為 AEC),移除篩選回復 333 表全量;`module_code` 為 `null` 的 19 表通過 API 原樣回傳 `null`,前端歸類為「未分類」(後端不做 null 特殊篩選,對齊 task-008 設計:「未分類」為前端過濾)。UI 下拉/切換視覺行為列入待人工複測。**pass(API 等效)**

## 9. 全套迴歸

### 後端

```
$ cd backend && uv run pytest -q
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
................................................................         [100%]
280 passed in 173.63s (0:02:53)

$ uv run ruff check .
All checks passed!

$ uv run mypy app
app\repositories\schedule_repo.py:528: error: "Result[Any]" has no attribute "rowcount"  [attr-defined]
Found 1 error in 1 file (checked 85 source files)
```

280 passed 與 task-007 收口基線一致;ruff 全綠;mypy 僅既有 baseline(`schedule_repo.py:528`,`docs-base` 標注勿修,非本版新增)。**pass**

### 前端

```
$ cd frontend && npm run lint
> eslint . --max-warnings=0
(無輸出,exit 0)

$ npm run typecheck
> tsc --noEmit
(無輸出,exit 0)

$ npm run build
▲ Next.js 16.2.7 (Turbopack)
✓ Compiled successfully in 14.8s
  Running TypeScript ... Finished TypeScript in 10.2s
✓ Generating static pages using 7 workers (11/11)
Route (app): / /_not-found /icon.svg /login /no-access /runs /runs/[uid]
             /schedules /sources /sources-hub /users
```

**pass**(lint / typecheck / build 三項全綠)

---

## 對外承諾覆核(propose-v1.5.0.md §對外承諾)

| # | 承諾 | 結果 | 說明 |
| --- | --- | --- | --- |
| 1 | 指定表 JSON API 回傳 key 一律 confirmed 英文名;未 confirmed 欄不出現 | ✅ | 第 5 條實測:`BMA_FILE` 回傳全英文 key、無 `bma01` magic key;未複核表 404。欄位級混合案例由 `test_data_query_api.py`(280 passed 內)覆蓋 |
| 2 | 各帳套提供 `<schema>_en` 語意化 view 供 SQL/BI 直查 | ✅ | 第 6 條實測:`M2201_en.bma_file` 存在,`SELECT * LIMIT 1` 回傳英文欄名可查。注意:`DS` schema(字典/共用表所在)本設計排除在 view 產生迴圈外,若消費端需要 `DS` 下的表(如本次改用理由所述 `GEN_FILE`/`GEM_FILE`)目前**無法**產生對應 view — 見下「遺留事項」 |
| 3 | mapping 異動於「下一次 ETL 同步完成後」生效(API 副本 + view 重生同一時點) | ✅ | 第 4 條實測:同步完成 log 同時輸出「view 重生完成」;第二次同步(mapping 未變)輸出「略過 view 重生」,證明「異動才重生」且與副本同步同一時點觸發 |
| 4 | comment 覆蓋:GAQ 缺漏 191 欄降至 ≤65(B1 前置達成時) | ✅ | 第 7 條:B1 前置(DMS 加 `DS.GAE_FILE`)**已達成**(與前手交接推測不同,本次實測確認);verify SQL 對 M2201 全量 333 表 11,947 欄實測:191 缺漏 → GAE 補 126 → 剩 65,精確等於驗收門檻 `≤65` |

四條**全數 ✅**,無 ⚠️ 項。

---

## 待人工瀏覽器複測清單

無頭環境無法操作瀏覽器,以下項目以 API 實測 + 程式碼審查佐證,尚未經真實瀏覽器點擊驗證:

1. **資料集頁模組下拉篩選 UI**(task-008):`frontend/src/components/datasets/DatasetBrowser.tsx` 模組下拉選單互動、切換「全部」復原、`module_code` 為 null 的表歸入「未分類」分組顯示 — 後端 API 行為已於第 8 條驗證(`?module=` 精準篩選、null 原樣回傳),UI 呈現待人工複測
2. **v1.4.1 遺留 UI 視覺 3 項**(角色回退後,尚未複測,延續前版待辦):Sidebar admin-only / member 直開 `/users` 導 no-access / 自己那列下拉停用

---

## 遺留事項

1. **`DS` schema 表無法產生語意化 view**:`view_generator._list_target_schemas` 設計上排除 `DS`(字典 schema)不進迴圈,但實測 `GEN_FILE`/`GEM_FILE` 等共用主檔實體表位於 `DS`(非 propose 原先假設的 `G2203`,`G2203` 目前僅存在於來源 `erp_migration_test`、尚未鏡像到 target `erp_etl_hub_test`)。若之後這類共用主檔的英文語意 view 有實際消費需求,需重新檢視 `DS` 排除規則(可能需改為「排除字典表清單」而非「排除整個 DS schema」),留待後續版本評估,不阻塞本版收口(本版驗收樣本已改用 `M2201.BMA_FILE` 迴避)
2. **`rows` 端點 admin-only**:現行 `datasets` 全端點僅 admin 可用(member 403),對外承諾「JSON API 回傳英文 key」若未來要開放給下游系統(非管理員)使用,需另議認證/授權模式(如 service token),本版僅供 admin 內部驗證用途,不擴權限
3. **module_code 未分類無後端 null 篩選**:task-008 設計「未分類」純前端過濾(對照 GAT06 缺漏 19/333 表);若未來清單量體變大需要伺服端分頁 + 未分類篩選,需補後端 `module=__unclassified__` 之類專用值,本版不做
4. **殭屍 run**(v1.4.0 既有遺留,本次驗證中觀察到,非本版引入):`GET /api/v1/runs` 可見 `2026-07-09 12:45` 一筆 `status=running`、`total_tables=4747` 的 run 至今未收尾,與本版無關,列入既有 v1.4.0 遺留待辦(見 propose 背景參考)
5. **多帳套(G2203/S2202/F2204)尚未鏡像至 target**:來源 `erp_migration_test` 已有 5 個帳套 schema,但 target `erp_etl_hub_test` 目前僅 `DS`/`M2201` 有實際鏡像資料;跨帳套 view 產生器邏輯已備妥(迴圈「target RDS 實際存在的 schema」),待其餘帳套實際同步後自動涵蓋,不需改碼

---

## 總結

| # | 驗證項 | 結果 |
| --- | --- | --- |
| 1 | `docker compose up -d --build` 全服務 healthy | pass |
| 2 | 草稿匯入(12,280 筆,冪等) | pass |
| 3 | 樣本複核(`--confirm-table BMA_FILE`,34 列) | pass |
| 4 | ETL 同步 → 自有 DB 副本一致 + cache 失效 | pass |
| 5 | JSON API 英文 key / 未複核 404 | pass |
| 6 | view `M2201_en.bma_file` | pass |
| 7 | comment 覆核(B1 前置已達成,缺漏數精確 = 65;B3 real-data 驗證) | pass |
| 8 | 模組分類篩選(API 等效) | pass |
| 9 | 全套迴歸(pytest 280 / ruff / mypy baseline;前端 lint/typecheck/build) | pass |

9 項全數 pass;對外承諾 4 條全數 ✅;`docker compose ps` 全容器 healthy。待人工複測 2 項(皆為 UI 視覺,非本版新增邏輯風險);遺留事項 5 項已記錄,均不阻塞本版收口。
