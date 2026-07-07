---
id: task-005
title: scheduler 依 cron 分組派工 + worker/引擎 config-ETL 下線
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/worker/scheduler.py
  - backend/app/worker/tasks.py
  - backend/app/etl/engine.py
  - backend/app/etl/__init__.py
  - backend/tests/test_scheduler_v131.py
  - backend/tests/test_mirror_sync_tables_v131.py
  - backend/tests/test_worker.py
  - backend/tests/test_etl_engine.py
estimated_hours: 4
---

## 目標

scheduler 改為讀「啟用且有 source_table 的排程」→ **依 `cron_expr` 分組**,同 cron 合併派一發 `mirror_sync(incremental=True, tables=[...], trigger_type="schedule")`;同時把 v1.1 config-ETL 於 worker/引擎層**程式面下線**(移除 `run_etl` task 與 config pipeline),並讓 `mirror_sync` **停讀 `sync_excluded`**(改由排程 `is_enabled` 決定)。

## 內容

- `worker/scheduler.py`:`DbScheduleSource` 讀 `is_enabled AND is_deleted=false AND source_table IS NOT NULL` 的排程;`build_scheduled_tasks` 依 `cron_expr` 分組,每組派一 `ScheduledTask(task_name="mirror_sync", kwargs={"incremental": True, "tables": [<該組表>], "schema": <schema>, "trigger_type": "schedule"}, cron=<cron>, cron_offset=CRON_OFFSET_TAIPEI, schedule_id=f"cron-<hash/序>")`。注意 `mirror_sync` 的 `tables` 需搭配 `schema`——若一組跨多 schema,需按 (schema) 再分組派多發(對齊 `_resolve_sync_targets(schema, tables)` 的「同 schema」限制)。
- `worker/tasks.py`:
  - `mirror_sync`:**移除** incremental 模式對 `list_excluded` / `sync_excluded` 的讀取(排除語意由「排程未啟用 → 不在 scheduler 派工的 tables 內」取代);其餘偵測/skip/更新基準邏輯保留。驗證 `incremental=True` + `tables=[...]` 偵測範圍正確限縮於指定表。
  - **移除** `run_etl` `@broker.task` 與其 helper（`load_configs` 等僅供 run_etl 者）;保留 `mirror_sync` 與其共用的 `RunStateTracker` / `make_store` 等。
- `etl/engine.py`:移除 `run_etl` pipeline 與 `load_table_configs`（config-ETL 專用);**保留** `mirror_sync` 仍用到的共用原語（`DbRunStore` / `RunStore` / `EtlTableConfig` / `mask_secrets` 等)。`etl/__init__.py` 移除 `run_etl` re-export（若有）。
- 測試:更新 `test_worker.py`（移除 run_etl 相關 case）、`test_etl_engine.py`（移除 run_etl pipeline case,保留共用原語 case);新 `test_scheduler_v131.py`（依 cron 分組派 mirror_sync tables）、`test_mirror_sync_tables_v131.py`（incremental+tables 只偵測/同步指定表;incremental=False 全量不受影響 = 人工全量保底）。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_scheduler_v131.py tests/test_mirror_sync_tables_v131.py tests/test_worker.py tests/test_etl_engine.py -q` 全綠
- [ ] `cd backend && uv run ruff check app/worker/scheduler.py app/worker/tasks.py app/etl/engine.py app/etl/__init__.py` 全綠
- [ ] `grep -rn "run_etl" app/worker/ app/etl/` 無命中（`run_etl` 於 worker/引擎層零引用）
- [ ] `grep -rn "sync_excluded\|list_excluded" app/worker/tasks.py` 無命中（mirror_sync 停讀排除旗標）
- [ ] test 斷言:同 cron 的 3 張啟用表 → 單一 `mirror_sync` 派工其 `tables` 含該 3 表;`incremental=False` 全量同步行為與 v1.3.0 一致（不看偵測與排程啟停）

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/03-backend/08-performance.md`
