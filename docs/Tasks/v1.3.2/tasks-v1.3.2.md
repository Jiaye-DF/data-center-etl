# Tasks v1.3.2

> 狀態:已完成 6/6(2026-07-07 落地;非先拆後做 —— 依 user 口述逐項確認後直接實作,本清單為**回溯記錄**)。驗證全綠:後端 205 passed、ruff 通過、mypy 無新增錯誤;前端 typecheck / lint 通過;已 `docker compose up -d --build` 且新端點回 401。
> 來源:`propose-v1.3.2.md`(scope 地板,禁動)
> 範圍:瀏覽 / 篩選體驗與營運可視性 —— ①ETL 資料頁欄位改「快照時間」②排程 / 原始資料進階篩選擴充(資料總筆數 / 排程時段 / 筆數區間 / schema 統計摘要)③總覽儀表板四塊(同步健康 / 待處理失敗表 / 下一班排程 / 資料規模+快照新鮮度)。全部**讀自有 DB、不打 RDS、未引入新套件**。
> 起點:`dev-v1.3/incremental-sync`(v1.3.1 已落地)。
> 對應 commit:task-001~004 於 `967400e`(併入執行紀錄頁 UI 一致化 —— 該 UI 調整**不屬** v1.3.2 propose scope,見拆解摘要);task-005~006 於 `8f00507`。已合併並推送 `development`(df-it + origin)。
> 關鍵約束:`row_count` bounded 探測封頂 1001 → 筆數區間 >1000 不精確、統計 / 儀表板**一律不做筆數加總**,改「表數分布 + 1000+ 桶」;cron 時段篩選僅每日純數字 cron 適用(`CASE` 回 NULL 排除其餘)。
> 執行環境:測試 DB 於 localhost:5435;後端 `uv run pytest`、前端 `npm run typecheck && npm run lint`;跑碼驗證 `docker compose up -d --build`(禁 start-dev)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | 資料瀏覽後端 — ETL 快照時間欄 + 筆數區間 + schema 統計摘要端點 | done | ✓ | — | `backend/app/schemas/rawdata.py` / `services/snapshot_service.py` / `api/v1/datasets.py` / `repositories/rds_table_meta_repo.py` |
| 002 | 排程進階篩選後端 — 資料總筆數 + 排程時段 + 批次一致 | done | ✓ | — | `backend/app/schemas/schedule.py` / `services/schedule_service.py` / `api/v1/schedules.py` / `repositories/schedule_repo.py` |
| 003 | 資料瀏覽前端 — 快照分欄 + 筆數區間 + 統計摘要區塊 | done | ✓ | 001 | `frontend/src/components/datasets/DatasetBrowser.tsx` / `lib/api/datasetApi.ts` |
| 004 | 排程前端 — 業務名欄改名 + 資料總筆數/排程時段篩選 + Segmented 抽共用 | done | ✓ | 002 | `frontend/src/components/schedules/ScheduleTableBrowser.tsx` / `lib/api/scheduleApi.ts` / `components/common/Segmented.tsx` |
| 005 | 總覽儀表板後端 — 聚合端點 `/dashboard/overview` + repo 聚合方法 | done | ✗ | 001, 002 | `backend/app/schemas/dashboard.py` / `services/dashboard_service.py` / `api/v1/dashboard.py` / `api/v1/__init__.py` / `repositories/run_repo.py` / `repositories/rds_table_meta_repo.py` / `repositories/schedule_repo.py` |
| 006 | 總覽儀表板前端 — dashboardApi + 改寫總覽頁(四塊 + 保留導覽卡) | done | ✓ | 005 | `frontend/src/lib/api/dashboardApi.ts` / `app/(main)/page.tsx` |

## 拆解摘要

- **總數**:6 個 task,預估 ~19 hr;後端 3(001、002、005)、前端 3(003、004、006)。
- **起手可認領(無依賴)**:**001、002**(後端,檔案不重疊,可同時開跑)。
- **依賴鏈**:
  - 資料瀏覽:`001`(後端 snapshot_at / 筆數區間 / summary 端點)→ `003`(前端串接 + 統計摘要區塊)
  - 排程篩選:`002`(後端 rows / 時段 + 批次一致)→ `004`(前端篩選 UI + 欄位改名 + Segmented 抽共用)
  - 儀表板:`005`(後端聚合端點 + repo 方法)→ `006`(前端總覽頁)
- **並行波次**:A=`001`/`002`;B=`003`/`004`;C=`005`(待 001+002);D=`006`。
- **同檔互鎖處理(避免衝突)**:
  1. `rds_table_meta_repo.py` 由 `001`(筆數區間 + `summary_by_schema`)先 own;`005` 於同檔追加 `dataset_scale` → `005` 標 `parallel: false` + `depends_on: 001` 序列化。
  2. `schedule_repo.py` 由 `002`(rows / 時段 filter)先 own;`005` 於同檔追加 `enabled_cron_exprs` → `005` `depends_on: 002` 序列化。
  3. `api/v1/__init__.py` 只由 `005` 動(掛 `dashboard` router,不碰其他 include)。
- **In Scope 映射**:①ETL 頁快照時間欄→001(後端 `TableSummary.snapshot_at`)+ 003(前端分欄)②排程篩選(資料總筆數 / 排程時段)→002 + 004 ③原始資料筆數區間 + 統計摘要→001(`/summary` 端點 + 筆數區間)+ 003(區間 UI + 摘要區塊)④排程「業務名」欄改名→004 ⑤總覽儀表板四塊→005(後端聚合)+ 006(前端)。
- **scope 外提醒(未偷渡進 task)**:commit `967400e` 併入的「執行紀錄頁 UI 一致化(移除排程名稱欄 / 明細改詞 / 狀態觸發改共用 Segmented)」**不在** v1.3.2 propose scope —— 為當次提交順帶,已於本清單註記,未列為 v1.3.2 task；如需正式納管請補進 propose 或列下版。

## 執行前置(orchestrator 提醒)

- **本版為回溯記錄**:6 個 task 皆 `done`,不需再認領實作;供 code review / changelog / 版本追溯用。
- **關鍵約束不可回頭破壞**:筆數一律不加總(bounded 1001 會失真);時段篩選僅每日純數字 cron;未引入新套件(cron 以 `split_part`+`CASE` 於 SQL 內運算)。
- **收口**:已 `docker compose up -d --build`;`/dashboard/overview`、`/datasets/{dataset}/summary`、排程新篩選參數皆上線(未帶 token 回 401)。已合併 `development` 並推 df-it + origin;Coolify 拉 `development` 即含 v1.3.2。
