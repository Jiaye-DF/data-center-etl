# Tasks v1.4.0

> 狀態:進行中(已完成 2/6)
> 來源:`propose-v1.4.0.md`(scope 地板,禁動;2026-07-09 已補齊 6 項並經 user 批准)
> 範圍:①同輪表級平行同步(並行度 env 化,預設 2)②全域同步進度條(`GET /runs/active` + sticky bar)③AWS 式自動重新整理(純 UI 輪詢 + 統一控制元件)④runs 頁手動觸發 404 修復 ⑤RBAC 全面 admin-only + member 無權限說明頁。
> 起點:`dev-v1.4/parallel-sync` @ `6349a57`(已含 uvicorn workers / DB 池 env 化 fix;task-001 動相同 compose / env 檔,**必**以此為基底)。
> 關鍵約束:並行僅及單輪內表級(RDS 讀寫);自有 DB 的 run/log/meta 寫入序列化(單 session 禁跨協程併用);既有同步 API 契約不變;`POST /runs/trigger` 已移除勿復活;角色僅 admin/viewer 不新增;權限收緊之 major 判準已由 user 裁定破例走 minor(見 propose § 風險)。
> 執行環境:測試 DB localhost:5435(docker 起);後端 `uv run pytest`、前端 `npm run typecheck && npm run lint`;跑碼驗證 `docker compose up -d --build`(**禁 start-dev**)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 同輪表級平行同步(worker 併發 + SYNC_CONCURRENCY env) | in_progress(worker: claude-A) | ✓ | — | `backend/app/worker/tasks.py` / `backend/app/core/config.py` / `backend/tests/test_mirror_sync_parallel.py` / 3×`docker-compose*.yml` / 3×`.env*.example` |
| 002 | 進度後端 — create_run 帶 total_tables + `GET /runs/active` | pending | ✗ | 001, 003 | `backend/app/etl/engine.py` / `backend/app/worker/tasks.py` / `backend/app/api/v1/runs.py` / `backend/app/schemas/run.py` / `backend/app/repositories/run_repo.py` / `backend/tests/test_runs_api.py` |
| 003 | RBAC 後端 — 資料層端點全面 require_admin | done(worker: claude-B) | ✓ | — | `backend/app/api/v1/{datasets,schedules,runs,sync,dashboard,audit_logs}.py` / `backend/tests/{test_sync_api,test_runs_api,test_schedule_api_v131,test_snapshot_service,test_audit_log}.py` |
| 004 | RBAC 前端 — member 無權限頁 + 路由守衛 + 導覽隱藏 | done(worker: claude-C) | ✓ | — | `frontend/src/app/(main)/layout.tsx` / `frontend/src/app/(main)/no-access/page.tsx`(新) / `frontend/src/components/layout/Sidebar.tsx` |
| 005 | 進度前端 — 全域 SyncProgress sticky bar(輪詢 /runs/active) | pending | ✗ | 002, 004 | `frontend/src/components/sync/SyncProgress.tsx`(新) / `frontend/src/lib/api/runApi.ts` / `frontend/src/app/(main)/layout.tsx` |
| 006 | 自動刷新前端 — AutoRefreshControl 共用元件 + 各檢視輪詢 + 觸發 404 修復 | pending | ✗ | 005 | `frontend/src/components/common/AutoRefreshControl.tsx`(新) / `frontend/src/lib/api/runApi.ts` / `frontend/src/app/(main)/runs/page.tsx` / `frontend/src/app/(main)/runs/[uid]/page.tsx` / `frontend/src/components/runs/RunLogTable.tsx` / `frontend/src/components/datasets/DatasetBrowser.tsx` / `frontend/src/app/(main)/page.tsx` |

## 拆解摘要

- **總數**:6 個 task,預估 ~17.5 hr;後端 3(001、002、003)、前端 3(004、005、006)。
- **起手可認領(無依賴,檔案不重疊)**:**001、003、004** 三個可同時開跑。
- **依賴鏈**:
  - 平行同步:`001` 獨立收斂(worker + env + compose)。
  - 進度條:`002`(需 001 先定 tasks.py 併發形狀、003 先定 runs.py 權限)→ `005`(前端串接;另因與 004 同動 layout.tsx 而序列化)。
  - RBAC:`003`(後端 403)∥ `004`(前端導頁)— 功能對應但檔案無交集,可並行。
  - 自動刷新 + 觸發修復:`006`(最後;與 005 同動 runApi.ts 序列化)。
- **並行波次**:A = `001` / `003` / `004`(三路並行);B = `002`;C = `005`;D = `006`。
- **同檔互鎖處理**:
  1. `worker/tasks.py`:001(併發改寫)先 own → 002(create_run 傳 total_tables)`depends_on: 001`。
  2. `api/v1/runs.py`、`tests/test_runs_api.py`:003(require_admin)先 own → 002(新端點 + 測試)`depends_on: 003`。
  3. `app/(main)/layout.tsx`:004(守衛)先 own → 005(掛 SyncProgress)`depends_on: 004`。
  4. `lib/api/runApi.ts`:005(active query)先 own → 006(觸發修復)`depends_on: 005`。
- **In Scope 映射**:①平行同步→001 ②進度條→002+005 ③自動刷新→006 ④觸發修復→006 ⑤RBAC→003+004(無 orphan)。
- **跨 area 三段**:後端→前端各成鏈(002→005、003→004 功能對應);e2e 依 `05-CI/06-e2e.md` 專案預設 disabled,本版不拆 e2e task,以 propose「手動驗收清單」代替。
- **規範衝突註記**:RBAC 權限收緊依 `05-version-bump.md` 屬 major 判準;user 裁定內部後台破例走 v1.4.0(已記 propose § 風險與變更紀錄)。**提醒:若此類「內部系統權限收緊走 minor」要常態化,請把例外寫進 `05-version-bump.md`(走 /reflect-rules)。**
- **model 建議(派工參考,保守分級)**:001=opus/high(併發正確性最難);002、006=sonnet/high;003、004、005=sonnet/medium。

## 執行前置(worker 認領須知)

- 認領協議照 `01-propose/03-multi-agent-flow.md`:改 task 檔 `status: in_progress` + 本清單註記 worker id;Acceptance 全綠才標 done;commit 帶 `[task-NNN]`。
- 全部 done 後 orchestrator 收口:`/scan-project` → 補洞 → `/reflect-rules` → PR。
