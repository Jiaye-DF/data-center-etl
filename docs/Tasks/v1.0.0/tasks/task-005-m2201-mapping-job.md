---
id: task-005
title: GAT_FILE/GAQ_FILE → M2201 對應轉換 job
status: done
parallel: true
depends_on: [task-002, task-003]
affected_files:
  - etl/jobs/m2201_job.py
  - etl/transforms/m2201.py
  - etl/config/mapping/m2201.yaml
  - etl/tests/test_transform_m2201.py
estimated_hours: 3
---

## 目標

實作核心對應 job:依來源 `DS.GAT_FILE`、`DS.GAQ_FILE` 既有欄位 / 表格名稱,對應轉換到 `M2201`,寫入 `erp_etl_hub_test`,並以 `GAQ_FILE` 描述作為每一欄位的 Comment。對應 propose 「DS GAT_FILE/GAQ_FILE 欄位對應於 M2201」+「每欄位必有 Comment(對應 GAQ_FILE)」。

## 範圍要點

- `jobs/m2201_job.py` 提供 `run(spark, config)`,供 `main.py` 動態派工;**不改** `main.py`。
- `transforms/m2201.py`:GAT_FILE/GAQ_FILE → M2201 的欄位對應與型別轉換;共用邏輯匯入 `transforms/common.py`(**不改** common.py)。
- `config/mapping/m2201.yaml`:來源→目標欄位對照表 + 每欄位 Comment(GAQ_FILE 來源)。
- 對應關係以 yaml 設定驅動,轉換程式讀 yaml 執行,**禁**把對照硬編在 py。

## Acceptance

- [x] `python -m py_compile etl/jobs/m2201_job.py etl/transforms/m2201.py` 通過(exit 0)
- [x] `python -c "import yaml,sys; d=yaml.safe_load(open('etl/config/mapping/m2201.yaml')); sys.exit(0 if d else 1)"` 成立(yaml 有效且非空)
- [x] `cd etl && python -m pytest tests/test_transform_m2201.py -q` 全綠;測試需涵蓋「GAT/GAQ 欄位→M2201 欄位對映正確」與「每個目標欄位皆帶 comment」
- [x] `python -c "import etl.jobs.m2201_job as j; print(hasattr(j,'run'))"` 印 `True`
- [x] `! grep -nE "^\\s*(GAT_FILE|GAQ_FILE|M2201)\\s*=" etl/transforms/m2201.py`(對照表不硬編於 py,走 yaml)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/00-overview/05-timezone.md`
