# Tasks v1.5.0

> 狀態:待認領(已完成 0/9)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | RDS erp_metadata schema + semantic_mappings 表冪等建置(A1) | done(worker: claude-A) | ✓ | — | `backend/app/etl/semantic_schema.py` / `backend/tests/test_semantic_schema.py` |
| 002 | 英文草稿匯入 RDS + 複核輔助腳本(A2) | done(worker: claude-C) | ✗ | 001 | `backend/scripts/seed_semantic_mappings.py` / `backend/tests/test_seed_semantic_mappings.py` |
| 003 | 自有 DB mapping 副本表 + 同步回流與 cache 失效(A5) | done(worker: claude-D) | ✗ | 001 | `backend/alembic/versions/v150_add_semantic_mappings_copy.py` / `backend/app/models/semantic_mapping.py` / `backend/app/models/__init__.py` / `backend/app/repositories/semantic_mapping_repo.py` / `backend/app/worker/tasks.py` / `backend/tests/test_semantic_mapping_sync.py` |
| 004 | 資料查詢 JSON API + confirmed 英文 key 轉換(A3) | done(worker: claude-E) | ✗ | 003 | `backend/app/api/v1/datasets.py` / `backend/app/services/data_query_service.py` / `backend/app/schemas/data_query.py` / `backend/tests/test_data_query_api.py` |
| 005 | 語意化 view 產生器 — 各帳套 `<schema>_en`(A4) | done(worker: claude-F) | ✗ | 003 | `backend/app/etl/view_generator.py` / `backend/tests/test_view_generator.py` |
| 006 | 字典擴充 — GAE fallback + GAQ04/05 選項值(B1+B3) | done(worker: claude-B) | ✓ | — | `backend/app/etl/dictionary.py` / `backend/tests/test_dictionary.py` |
| 007 | B2 後端 — 快照加 GAT06 模組欄位 + API 模組篩選 | done(worker: claude-G) | ✗ | 003, 004 | `backend/alembic/versions/v150_add_module_code_to_rds_table_meta.py` / `backend/app/models/rds_table_meta.py` / `backend/app/services/snapshot_service.py` / `backend/app/api/v1/datasets.py` / `backend/app/schemas/rawdata.py`(拆解誤植 dataset.py,實際檔名) / `backend/app/repositories/rds_table_meta_repo.py`(分層規則必經,worker 揭露補記) / `backend/app/etl/dictionary.py`(純新增 fetch_table_modules) / `backend/tests/test_snapshot_module_code.py` |
| 008 | B2 前端 — 資料集頁模組分類/篩選 UI | pending | ✗ | 007 | `frontend/src/lib/api/datasetApi.ts` / `frontend/src/components/datasets/DatasetBrowser.tsx` |
| 009 | 端到端收口驗證 — 樣本表複核鏈路 + 承諾覆核 | pending | ✗ | 002, 004, 005, 006, 007, 008 | `docs/Tasks/v1.5.0/verification-v1.5.0.md`(新) |

## 拆解摘要

- **總數**:9 個 task,預估 ~26 hr;後端 7(001–007)、前端 1(008)、e2e 收口 1(009)。
- **並行 / 序列**:起跑可並行 2(001、006 無依賴且不同檔);其餘依賴鏈:
  - 語意層主鏈:`001 → 003 → {004 ∥ 005} → 007 → 008 → 009`;`001 → 002`(草稿匯入,與 003 並行)。
  - 006(字典擴充)全程獨立,可與任何 task 並行。
- **同檔互鎖**:`datasets.py`(004、007)→ 007 depends 004;alembic head 鏈(003、007 各一支 migration)→ 007 depends 003;`worker/tasks.py` 僅 003 動(005 只提供函式本體,掛點由 003 預留)。
- **阻塞點**:001(erp_metadata 表是 A 線地基)、003(副本表 + worker 掛點,004/005/007 皆依賴)。
- **跨 area 三段鏈**(B2):後端 API(007)→ 前端串接(008)→ e2e(009)。
- **In Scope 映射**(無 orphan):A1→001;A2→002(+009 樣本複核);A3→004;A4→005;A5→003;B1→006;B2→007+008;B3→006。
- **拆解判讀(請 user 留意)**:
  1. **A3 需新增資料列查詢端點**:現行 datasets API 僅 schema/表層瀏覽,無回傳資料列的 JSON API;對外承諾「JSON 回英文 key」以 task-004 新端點 `GET /datasets/{dataset}/tables/{schema}/{table}/rows` 承載(併入既有 datasets 路由,不另開模組)。若你屬意的是其他對外供數介面,請回饋後調整 004。
  2. **目標 RDS 的 DDL 不走 alembic**(alembic 只管自有 DB):`erp_metadata` 建置走 001 的冪等模組,對齊 mirror 引擎模式。
  3. B1 的 DMS 加表(`DS.GAE_FILE`)為**人工前置**,006 以 graceful 設計不被阻塞;009 允許記錄「前置未成」不擋收口。
- **model 建議(派工參考,保守分級)**:004 = opus/high(對外 API 契約 + SQL 注入面最難);003、005、006、007 = sonnet/high;001、002、008、009 = sonnet/medium。

## 執行前置(worker 認領須知)

- **分支**:自 `main` 開功能分支;目前工作分支 `dev-v1.5.0` 已存在,worker 直接沿用。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev。
- 認領協議照 `01-propose/03-multi-agent-flow.md`:改 task 檔 `status: in_progress` + 本清單註記 worker id;Acceptance 全綠才標 done;commit 帶 `[task-NNN]`。
- 全部 done 後 orchestrator 收口:`/scan-project` → 補洞 → `/reflect-rules` → PR。
