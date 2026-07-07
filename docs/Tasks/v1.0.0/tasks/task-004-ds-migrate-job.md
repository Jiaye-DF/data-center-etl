---
id: task-004
title: DS schema 搬移 job
status: done
parallel: true
depends_on: [task-002, task-003]
affected_files:
  - etl/jobs/ds_migrate_job.py
  - etl/transforms/ds.py
  - etl/config/mapping/ds.yaml
  - etl/tests/test_transform_ds.py
estimated_hours: 3
---

## 目標

實作 `DS` schema 整份搬移 job:讀來源 `erp_migration_test.DS`(reader,task-002)→ 套 `transforms/ds.py` 轉換 → 寫入 `erp_etl_hub_test`(writer + Comment,task-003),表名沿用原始 `table_name`。對應 propose「DS 也需要移動一份過去」。

## 範圍要點

- `jobs/ds_migrate_job.py` 提供 `run(spark, config)`,供 `main.py` 動態派工;**不改** `main.py`。
- `transforms/ds.py`:DS 專屬轉換(型別 / null / 欄位正規化),共用邏輯匯入 `transforms/common.py`(**不改** common.py)。
- `config/mapping/ds.yaml`:DS 表格 / 欄位對照 + 欄位 Comment(GAQ_FILE 來源);供 writer 產生 `COMMENT ON COLUMN`。
- 每一目標欄位都要有 Comment 來源;缺的在 yaml 補齊或明確標記待補。

## Acceptance

- [x] `python -m py_compile etl/jobs/ds_migrate_job.py etl/transforms/ds.py` 通過(exit 0)
- [x] `python -c "import yaml,sys; d=yaml.safe_load(open('etl/config/mapping/ds.yaml')); sys.exit(0 if d else 1)"` 成立(yaml 有效且非空)
- [x] `cd etl && python -m pytest tests/test_transform_ds.py -q` 全綠(對 `transforms/ds.py` 純轉換函式做單元測試)
- [x] `python -c "import etl.jobs.ds_migrate_job as j; print(hasattr(j,'run'))"` 印 `True`
- [x] 人工/grep 檢查:`ds.yaml` 中每個 mapping 欄位皆有 `comment` 欄(`! grep -nE '^\\s*-\\s' etl/config/mapping/ds.yaml` 之對照,或以測試斷言 mapping 每欄具 comment)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/00-overview/05-timezone.md`
