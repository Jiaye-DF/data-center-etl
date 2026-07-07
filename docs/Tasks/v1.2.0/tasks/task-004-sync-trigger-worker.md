---
id: task-004
title: 同步觸發端點 + worker task + sync_states 更新
status: done
parallel: true
depends_on: [task-001, task-002, task-003]
affected_files:
  - backend/app/api/v1/sync.py
  - backend/app/api/v1/__init__.py
  - backend/app/worker/tasks.py
  - backend/app/services/sync_service.py
  - backend/app/schemas/sync.py
  - backend/tests/test_sync_api.py
estimated_hours: 3
---

## 目標

提供「同步」動作(逐表 / 全量),經 worker 執行自動鏡像引擎(task-003),把 metadata 快照的 `last_synced_at` / `last_transformed_at` / `row_count` 更新(task-001 model / task-002 repo),並落既有執行紀錄(etl_runs / etl_run_logs,重用 DbRunStore)。

## 設計要點

- `worker/tasks.py`:**新增** taskiq task `mirror_sync`(參數:`schema` / `table` 可空 = 全量;`dataset` 固定 source→target)。流程:建 run(重用 DbRunStore)→ 逐表呼叫 `mirror.mirror_table` → 逐表寫 etl_run_logs → 更新 rds_table_meta(repo)→ 收尾 run。DS schema 優先。**禁**改動既有 `run_etl` task。
- `services/sync_service.py`:enqueue mirror_sync(逐表 / 全量);回 run 對應資訊。
- `api/v1/sync.py` + register 於 `api/v1/__init__.py`(prefix `/sync`):
  - `POST /sync/table`(require_admin,body: schema+table)→ enqueue 單表同步。
  - `POST /sync/all`(require_admin)→ enqueue 全量(DS 優先)。
- `schemas/sync.py`:請求 / 回應模型(ApiResponse 外殼)。
- 全量同步為大規模 RDS 寫入:worker 端分批、逐表 commit log;**task Acceptance 僅驗單表 / 少數表**,全量由 user 收口確認後觸發。

## Acceptance

- [x] `uv run pytest tests/test_sync_api.py` 全綠(mock enqueue:`/sync/table`、`/sync/all` 回 202/200 且 ApiResponse;viewer 呼叫回 403)
- [x] `curl -s -X POST -b <admin cookie> -H 'content-type: application/json' -d '{"schema":"DS","table":"AAA_FILE"}' localhost:8000/api/v1/sync/table | jq -e '.success == true'`
- [x] 單表同步實跑後:`etl_runs` 新增一筆且 status=success;`erp_etl_hub_test` 有 `DS.AAA_FILE` 資料 + 中文 COMMENT;`rds_table_meta` 該表 `last_synced_at` 非空
- [x] `uv run ruff check . && uv run mypy app` green
- [x] 既有 `run_etl` task 未動:`git diff app/worker/tasks.py` 僅為新增(不改既有 task 邏輯)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/00-overview/05-timezone.md`
