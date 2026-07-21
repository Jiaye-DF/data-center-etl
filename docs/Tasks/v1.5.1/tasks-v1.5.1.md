# Tasks v1.5.1

> 狀態:全數完成(7/7,2026-07-21;UI 人工複測待 user,見 verification-v1.5.1.md)

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 快照同步進度條(後端進度回報 + 前端進度條;補登) | done | ✓ | — | `backend/app/etl/introspect.py` / `backend/app/services/snapshot_service.py` / `backend/app/api/v1/datasets.py` / `backend/app/schemas/rawdata.py` / `backend/tests/test_snapshot_refresh_progress.py` / `frontend/src/lib/api/datasetApi.ts` / `frontend/src/components/datasets/DatasetBrowser.tsx` 等 |
| 002 | view schema 後綴改 `_view`(系統側;RDS 由 user ALTER RENAME) | done | ✓ | — | `backend/app/etl/view_generator.py` / `backend/tests/test_view_generator.py` |
| 003 | 英文草稿 unused 命名修正 + 重新 seed | done | ✓ | — | `docs/ERP-Analyze/data/semantic_draft.tsv` |
| 004 | 語意映射管理後端 API(列表 / 編輯 / 轉態) | done | ✓ | — | `backend/app/api/v1/semantic_mappings.py` / `backend/app/services/semantic_admin_service.py` / `backend/app/schemas/semantic_mapping.py` / `backend/app/api/v1/__init__.py` / `backend/tests/test_semantic_mappings_api.py` |
| 005 | 「同步 view」觸發端點(副本重灌 + view 重生共用化) | done | ✗ | 004 | `backend/app/worker/tasks.py` / `backend/app/api/v1/semantic_mappings.py` / `backend/app/services/semantic_admin_service.py` / `backend/tests/test_semantic_mappings_api.py` |
| 006 | 前端語意映射管理頁 + sidebar 獨立入口 | done | ✗ | 004, 005 | `frontend/src/lib/api/semanticMappingApi.ts` / `frontend/src/app/(main)/semantic-mappings/page.tsx` / `frontend/src/components/semantic/SemanticMappingManager.tsx` / `frontend/src/components/layout/Sidebar.tsx` |
| 007 | e2e 驗證 + 收口文件 | done | ✗ | 001–006 | `docs/Tasks/v1.5.1/verification-v1.5.1.md` |

## 拆解摘要

- **總量**:7 個 task,預估 ~19 hr;001 已完成(補登),待執行 6。002 的 RDS 既有 schema 改名由 user 手動 `ALTER SCHEMA ... RENAME`(見 propose 變更紀錄)。
- **並行**:002 / 003 / 004 三者影響檔案不重疊,可同時起跑;005 與 004 共檔(`semantic_mappings.py` / `semantic_admin_service.py`)→ 序列化 depends 004;006 依賴後端完成;007 收尾。
- **關鍵路徑**:`004 → 005 → 006 → 007`(~13 hr);002 / 003 為旁路可並行消化。
- **同檔互鎖**:004 / 005 重疊 → 已序列化;其餘無重疊。
- **In Scope 對映**(無 orphan):進度條 → 001;`_view` 改名 → 002;映射管理頁 → 004+005+006;unused 修正 → 003;驗收 → 007。
- **跨 area 三段鏈**:後端 API(004+005)→ 前端串接(006)→ e2e(007)。
- **阻塞點**:005 的「同步 view」需先把 worker 收尾邏輯共用化,是唯一動 `worker/tasks.py` 的 task;003 需可連目標 RDS 的環境執行 re-seed。

## 執行前置(worker 認領前必讀)

- **分支**:`dev-v1.5.1/snapshot-progress`(001 已在此分支;002–007 沿用)。
- **跑法**:改碼後以 `docker compose up -d --build` 驗證,**禁** start-dev。
- 協議:認領 task 改 `status: in_progress` + 註記 worker;Acceptance 全過才標 done;commit 帶 `[task-NNN]`。
- 全數 done 後:`/scan-project` → 修 → `/reflect-rules`(含「patch 開 propose」升規候選)→ 收口。
