# Tasks v1.3.1

> 狀態:已完成 9/9(2026-07-07 multi-agent 落地;收口清 v1.3.0 舊測試後全綠:後端 204 passed、前端 typecheck/lint/build 綠;未 commit)
> 來源:`propose-v1.3.1.md`(scope 地板,禁動)
> 範圍:修正 v1.3.0 排程模型 —— 改「**一表一排程**」(快照同步自動建立逐表排程,預設每天 00:00、預設停用)+ 排程管理頁本身即逐表檢視(對齊 `/sources`、`/sources-hub` 樣式)+ scheduler 依 cron 分組合併派 `mirror_sync(incremental=True, tables=[...])` + **移除**「排程涵蓋」頁與 v1.1 config ETL 遺留鏈路(**程式面下線,不產生任何 DROP migration**;實體 DROP 走人工移除清單)。
> 起點:`dev-v1.3/incremental-sync`(v1.3.0 已落地:增量 `mirror_sync`、Dialog 排程表單、友善 cron 工具、coverage 查詢邏輯可遷移)。**前置**:v1.3.0 收口(套 v4 migration、rebuild)已完成。
> 派工粒度(propose 已定案):同 cron 的啟用表**分組合併派一發** `mirror_sync`(一輪偵測、一筆 run、逐表明細);一表一發已否決。
> 「移除」定義(CLAUDE.md 毀滅性禁止):= **程式面完全下線**(model 欄位標 deprecated、API/UI/worker 不再讀寫)+ 人工移除清單(task-009);**禁**任何 DROP migration / DROP COLUMN。實體 DROP 由人類負責人備份後手動執行。
> 執行環境:測試 DB 於 localhost:5435(docker compose 已起);後端 `uv run pytest`、前端 `npm run typecheck && npm run lint && npm run build`;跑碼驗證 `docker compose up -d --build`(禁 start-dev)。

## 清單

| # | 標題 | 狀態 | 並行 | 依賴 | 影響檔案 |
| --- | --- | --- | --- | --- | --- |
| 001 | DB:`schedules` 加 `source_schema` / `source_table` + partial unique index + migration(`etl_table_pid` 標 deprecated) | pending | ✓ | — | `backend/app/models/schedule.py` / `alembic/versions/v5_add_v131_schedule_per_table.py` / `tests/test_models_v131.py` |
| 002 | `schedule_repo`:逐表讀寫(find/upsert/軟刪缺表)+ 逐表視角查詢(JOIN meta × 最新 run log)+ 批次啟停 | pending | ✓ | 001 | `backend/app/repositories/schedule_repo.py` / `tests/test_schedule_repo_v131.py` |
| 003 | 快照同步自動建排程 + 收斂(每表 upsert 逐表排程 / 缺表軟刪 / 軟刪 v1.3.0 全表舊排程) | pending | ✓ | 002 | `backend/app/services/snapshot_service.py` / `tests/test_snapshot_autoschedule_v131.py` |
| 004 | 排程/執行 API+service 重構(逐表列表 + 改 cron·啟停·描述 + 批次啟停;移除 create/delete 端點與 config-ETL 手動觸發) | pending | ✓ | 002 | `backend/app/schemas/schedule.py` / `services/schedule_service.py` / `api/v1/schedules.py` / `api/v1/runs.py` / `tests/test_schedule_api_v131.py` / `tests/test_runs_api.py` |
| 005 | scheduler 依 cron 分組派工 + worker/引擎 config-ETL 下線(移除 `run_etl`、停讀 `sync_excluded`、驗 `incremental+tables`) | pending | ✓ | 001 | `backend/app/worker/scheduler.py` / `worker/tasks.py` / `etl/engine.py` / `etl/__init__.py` / `tests/test_scheduler_v131.py` / `tests/test_mirror_sync_tables_v131.py` / `tests/test_worker.py` / `tests/test_etl_engine.py` |
| 006 | 移除後端「排程涵蓋」+ config-ETL 端點/service/repo + `api/v1/__init__.py` 收斂 | pending | ✓ | — | `backend/app/api/v1/__init__.py` / `api/v1/etl_tables.py`(del) / `api/v1/schedule_coverage.py`(del) / `services/etl_config_service.py`(del) / `services/schedule_coverage_service.py`(del) / `repositories/etl_config_repo.py`(del) / `repositories/schedule_coverage_repo.py`(del) / `schemas/schedule_coverage.py`(del) / `tests/test_etl_config_api.py`(del) / `tests/test_schedule_coverage_api.py`(del) |
| 007 | 前端排程管理頁改版(逐表 schema 分頁 + 表清單瀏覽器 + 進階篩選 + 啟停 toggle + 批次啟停 + 編輯 Dialog)+ `scheduleApi` 重構 | pending | ✓ | 004 | `frontend/src/app/(main)/schedules/page.tsx` / `components/schedules/ScheduleTableBrowser.tsx` / `components/schedules/ScheduleFormDialog.tsx` / `lib/api/scheduleApi.ts` |
| 008 | 移除前端「排程涵蓋」頁 + v1.1 config-ETL 頁 + Sidebar 連結 | pending | ✓ | 007 | `frontend/src/app/(main)/schedules/coverage/page.tsx`(del) / `components/schedules/ScheduleCoverageBrowser.tsx`(del) / `lib/api/scheduleCoverageApi.ts`(del) / `app/(main)/tables/page.tsx`(del) / `app/(main)/tables/[uid]/page.tsx`(del) / `components/tables/MappingEditor.tsx`(del) / `components/tables/TableList.tsx`(del) / `lib/api/etlConfigApi.ts`(del) / `components/layout/Sidebar.tsx` |
| 009 | 人工移除清單文件(待 DROP 的表 / 欄 + 備份指引) | pending | ✓ | — | `docs/Tasks/v1.3.1/manual-removal-checklist.md` |

## 拆解摘要

- **總數**:9 個 task,預估 ~25 hr;後端 6(001–006)、前端 2(007–008)、文件 1(009)。
- **起手可認領(無依賴)**:**001、006、009**(檔案不重疊,可同時開跑)。
- **依賴鏈**:
  - 資料層:`001`(schedules 逐表欄 + migration)→ `002`(repo 逐表讀寫 / 視角查詢 / 批次)→ `003`(快照自動建排程)、`004`(排程 API/service 重構)
  - 派工:`001` → `005`(scheduler 依 cron 分組 + worker/引擎 config-ETL 下線)
  - 前端:`004` → `007`(排程管理頁改版)→ `008`(移除舊頁 + 連結;`008` 待 `007` 移除 `etlConfigApi` 引用後才刪該檔)
- **並行波次**:A=`001`/`006`/`009`;B=`002`/`005`;C=`003`/`004`;D=`007`;E=`008`。
- **同檔互鎖處理(避免衝突)**:
  1. `worker/tasks.py` + `etl/engine.py` 的 config-ETL 下線(移除 `run_etl` task/pipeline)**全歸 005**;006 不碰 worker/engine(只刪 API/service/repo 層)。
  2. `schedule_service.py`(含 `ScheduleService` + `RunService`)**全歸 004**;004 一併移除 `RunService.trigger_manual`(config-ETL 手動觸發)與 `api/v1/runs.py` 對應端點,保留 runs 清單/明細/logs(執行紀錄頁沿用)。
  3. `api/v1/__init__.py` **只由 006 動**(移除 schedule_coverage + etl_tables include;不動 schedules/runs/sync)。
  4. `Sidebar.tsx` **只由 008 動**(移除「排程涵蓋」連結)。
  5. coverage 查詢邏輯由 002「遷移沿用」寫進 `schedule_repo.py`;006 刪 `schedule_coverage_repo.py`——002 只讀該檔為參考、寫在自己的檔,無互鎖。
- **「移除」= 程式面下線,零 DROP**:001/005/006 皆**禁** DROP TABLE / DROP COLUMN；`etl_table_pid`、`sync_excluded`、`etl_tables`、`etl_mappings` 欄位/表**保留**、標 deprecated,實體移除列入 009 人工清單,由人類手動執行。
- **In Scope 映射**:①一表一排程模型→001,002 ②快照自動建排程→003 ③既有資料收斂(backfill/舊排程軟刪/`sync_excluded` 廢止)→003(建/軟刪),005(停讀 sync_excluded)④派工依表分組→005 ⑤移除排程涵蓋頁→006(後端),008(前端)⑥移除 config-ETL 遺留→005(run_etl task/engine),006(etl_tables API/service/repo),004(RunService 手動觸發 + runs 端點),008(前端 /tables)⑦「移除」定義→009(人工清單)+ 貫穿 001/005/006 的 no-DROP 約束 ⑧排程管理頁 UI 改版→007 ⑨排程管理 API 重構→004 ⑩人工全量同步保底(沿用)→005 Acceptance(`incremental=False` 行為不變)。

## 執行前置(orchestrator 提醒)

- **禁 DROP(CLAUDE.md)**:全版本**不得**產生任何 DROP migration / DROP COLUMN;001 migration 只 `add_column`(nullable + partial unique index),downgrade 前進式不 DROP COLUMN。
- **RDS 寫入不可逆**:005/003 的驗收以 fake / 少數表 / 測試 DB 驗證;**全量首輪同步不在任何 task 內自動觸發**,由 user 收口確認後手動執行。
- **收口(全 task done 後)**:`docker compose up -d --build` → 對測試 DB 驗「快照同步 → 每表一排程(停用)/ 啟用某表調近期 cron → 到點僅該表同步 / 同 cron 多表合併一 run」→ `/scan-project` → 有調規走 `/reflect-rules`。人工移除清單交付 user。
