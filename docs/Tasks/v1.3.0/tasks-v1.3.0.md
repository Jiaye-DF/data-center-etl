# Tasks v1.3.0

> 狀態:全部完成(已完成 9/9)
> 來源:`propose-v1.3.0.md`(scope 地板,禁動)
> 範圍:增量同步 —— `pg_stat_user_tables` 寫入計數器變動偵測 + 只灌變動表整批覆蓋 + 修排程接線(排程單一化改派 `mirror_sync` 增量)+ 排程管理 Dialog 化 + 依表檢視(全表預設納入 + 可逐表排除)。
> 起點:`dev-v1.3/incremental-sync`(v1.2.0 已落地:`mirror_sync` / `mirror.py` / `rds_table_meta` / 排程友善 UI)。既有 config-driven 引擎(`etl/{engine,reader,writer,comments}.py`)與 `run_etl` task 為 v1.1 遺留、**與同步無關,擺著不動**。
> **核心模型(user 確認)**:同步只有**一個操作** = `mirror_sync`(增量);**兩種觸發條件**,以既有 `etl_runs.trigger_type` 區分:**taskiq 自動**(半夜到點,`trigger_type="schedule"`)與**人工手動**(taskiq 故障時自己補,`trigger_type="manual"`,走既有「全量同步」/手動觸發)。**不分舊/新排程、不引入 `job_type`**。
> 執行環境註記:各 task Acceptance 指令為 bash 語法;本機為 Windows,worker 以 **Git Bash** 或 PowerShell 對應執行。單元/整合測試以 fake / monkeypatch 免連 RDS(對齊 v1.2);跑碼驗證走 `docker compose up -d --build`(禁 start-dev)。RDS 連線走 `.env` `AWS_RDS_*`(未進 git)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | DB schema:`rds_table_meta` 計數器 signature 欄 + 排除旗標 + migration | done | ✓ | — | `backend/app/models/rds_table_meta.py` / `alembic/versions/v4_add_v130_sync_signature.py` / `tests/test_models_v130.py` |
| 002 | 變動偵測引擎(`pg_stat_user_tables` 讀取 + signature 比對) | done | ✓ | — | `backend/app/etl/mirror.py` / `tests/test_change_detection.py` |
| 003 | signature repo 讀寫方法(讀/更新基準 + 讀排除清單) | done | ✓ | 001 | `backend/app/repositories/rds_table_meta_repo.py` / `tests/test_rds_table_meta_repo_v130.py` |
| 004 | 增量同步整合(`mirror_sync` 偵測→略過排除表→只灌變動表→skip log→更新基準) | done | ✓ | 002,003 | `backend/app/worker/tasks.py` / `tests/test_mirror_sync_incremental.py` |
| 005 | 排程接線修正(`scheduler.py` 排程一律派 `mirror_sync` 增量) | done | ✓ | 004 | `backend/app/worker/scheduler.py` / `tests/test_scheduler_v130.py` |
| 006 | 排程列表加上次執行結果 + sync 語意(移除逐表選擇,`etl_table_pid` 強制 NULL) | done | ✓ | — | `backend/app/schemas/schedule.py` / `services/schedule_service.py` / `repositories/schedule_repo.py` / `api/v1/schedules.py` / `tests/test_schedule_lastrun_api.py` |
| 007 | 依表檢視 coverage API(全表 × 啟用排程 × 上次結果 + 逐表排除 toggle) | done | ✓ | 001 | `backend/app/schemas/schedule_coverage.py` / `services/schedule_coverage_service.py` / `repositories/schedule_coverage_repo.py` / `api/v1/schedule_coverage.py` / `api/v1/__init__.py` / `tests/test_schedule_coverage_api.py` |
| 008 | 前端 排程管理 Dialog 化 + 固定全表增量 + 列表顯示行為/上次結果 | done | ✓ | 006 | `frontend/src/app/(main)/schedules/page.tsx` / `components/schedules/ScheduleFormDialog.tsx` / `lib/api/scheduleApi.ts` |
| 009 | 前端 依表檢視頁(schema 分頁 + 表清單 + 排程/結果/下次執行 + 篩選) | done | ✓ | 007 | `frontend/src/app/(main)/schedules/coverage/page.tsx` / `components/schedules/ScheduleCoverageBrowser.tsx` / `lib/api/scheduleCoverageApi.ts` / `utils/cron.ts` / `components/layout/Sidebar.tsx` |

## 拆解摘要

- **總數**:9 個 task,預估 ~28 hr;後端 7(001–007)、前端 2(008–009)。
- **起手可認領(無依賴)**:**task-001、002、006**(檔案不重疊,可同時開跑)。
- **依賴鏈**:
  - 資料層:`001`(rds_table_meta 計數器欄 + 排除旗標 + migration)→ `003`(repo 讀寫新欄)、`007`(coverage 用 `sync_excluded`)
  - 偵測引擎:`002`(mirror 讀 pg_stat + 純比對函式)獨立 → 併入 `004`
  - 增量整合:`002,003 → 004`(worker 串偵測 + repo 基準 + 略過排除表)
  - 排程接線:`004 → 005`(scheduler 一律派 `mirror_sync(incremental=True)`)
  - 排程列表 API:`006`(獨立;既有 etl_runs 補上次結果)→ 前端 `008`
  - 依表檢視:`001 → 007`(coverage + 排除 toggle)→ 前端 `009`
- **並行性**:全 task `affected_files` **互不重疊** → 全部 `parallel: true`。`api/v1/__init__.py` 只由 007 動(掛 coverage router);`utils/cron.ts` 只由 009 動(加下次執行推算);`schedule_service.py` / `schedules.py` 只由 006 動;`sync_excluded` 寫入由 007 的 `schedule_coverage_repo` 負責(不動 003 的 `rds_table_meta_repo`)。
- **阻塞點**:004(需 002+003);005(需 004);001 前置 003 與 007。
- **關鍵設計約束(避免同檔互鎖)**:
  1. **排程單一化為 sync**:`scheduler.py`(005)對所有啟用排程一律派 `mirror_sync(incremental=True)`,**不加 `job_type` 欄**;`run_etl` 保留手動 fallback,`scheduler` 不再派它。既有 `schedules.etl_table_pid` 保留 NULL(禁 DROP COLUMN),sync 排程不使用。
  2. **coverage 走全新檔**(`schedule_coverage_*`),不動 006 的 `schedule_service.py` / `schedules.py`;僅 007 動 `api/v1/__init__.py`。
  3. **偵測引擎為 mirror.py 純新增**(讀 `pg_stat_user_tables` + 無狀態比對函式),不改既有 `mirror_table` / config-driven 引擎。
  4. **增量旗標走 `mirror_sync(incremental=...)`**:預設 `False`(= 現行全量覆蓋,人工「全量同步」/`sync_all` 語意不變);排程派工帶 `True`。`sync_service.py` / `sync.py` / `schemas/sync.py` **不動**。
  5. **下次執行由前端 `utils/cron.ts` 推算**(既有 friendly cron 工具),coverage / 排程列表 API 回原始 cron + 上次結果,不引入後端 cron 依賴。
- **In Scope 映射**:①變動偵測→002,004 ②計數器倒退保守→002(比對函式),004 ③增量引擎→004 ④signature 存放→001,003 ⑤排程接線修正(單一化)→005 ⑥排程 UI/model 連動(Dialog 硬需求 + 移除逐表 + 顯示做什麼/上次結果)→006,008 ⑦依表檢視+全表預設納入+**可逐表排除**→001(排除旗標),004(增量略過排除表),007(排除 toggle),009(排除 UI)⑧人工全量覆蓋保底→004(`incremental=False`,忽略偵測與排除;UI 沿用既有全量同步鈕,無新前端 task)⑨首次/新表基準→002(無基準→視為變動),004。

## 決策點

1. **「可逐表排除」**(propose In Scope ⑦標「(決策點)」)—— **已定案(user 確認:可以)**:本版**納入**逐表排除。`rds_table_meta.sync_excluded` 旗標(001,預設 false=納入)+ 增量同步略過被排除表(004,僅 `incremental=True`;人工全量忽略排除)+ coverage 排除 toggle API(007)+ 依表檢視排除 UI(009)。**新表預設納入**(旗標 default false)。

## 執行前置(orchestrator 提醒)

- **RDS 寫入屬對外不可逆動作**:task-004 首次/倒退→整批覆蓋為大規模 RDS 寫入;各 task Acceptance 以 fake / 少數表驗證,**全量首輪同步不在任何 task 內自動執行**,由 user 收口確認後手動觸發(對齊 propose 風險區「首次上線大量整灌」)。
- **毀滅性禁止(CLAUDE.md)**:task-001 migration **禁 DROP COLUMN**;新增欄位為 nullable,`downgrade` 採前進式(僅撤銷本次新增之 index/constraint,欄位存在性 guard 使 `upgrade` 可重入),不 DROP COLUMN。task-004 沿用 `mirror.py` TRUNCATE + 重灌(禁 DROP TABLE)。既有 `schedules.etl_table_pid` 保留(禁 DROP COLUMN),sync 排程一律 NULL。
- **收口(全 task done 後由 orchestrator)**:小規模對 RDS 驗增量(改動幾張表 → 只灌變動 / 未動 skip;排除某表 → 增量不灌該表)→ `/scan-project` → 有調規走 `/reflect-rules`。
