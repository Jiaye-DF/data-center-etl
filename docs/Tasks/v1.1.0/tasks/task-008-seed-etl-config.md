---
id: task-008
title: v1.0.0 mapping 設定匯入自有 DB(seed)
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/scripts/seed_etl_config.py
  - backend/tests/test_seed_etl_config.py
estimated_hours: 2
---

## 目標

把 v1.0.0 的 `etl/config/mapping/*.yaml`(DS / M2201 對照與欄位 Comment)匯入自有 DB(`etl_tables` / `etl_mappings`)作為初始資料,讓後台開站即有完整納管表清單。來源 yaml **唯讀**,不改 `etl/` 任何檔。

## 範圍要點

- `seed_etl_config.py`:讀 `etl/config/mapping/ds.yaml`、`m2201.yaml`(路徑可參數化)→ 寫入 DB;**冪等**(重跑不重複建、既有資料不覆寫,除非帶 `--force-update`)。
- yaml 以 `encoding="utf-8"` 開啟(繁中 comment;參 `docs/Tasks/v1.0.0/fixed.md § 2` 的 cp950 教訓)。
- 匯入時驗證每欄位有 comment,缺值列警告清單(不中斷,後台可補)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_seed_etl_config.py -q` 全綠(匯入筆數正確、冪等重跑不重複、繁中 comment 正確落庫)
- [ ] `git diff --stat` 不含 `etl/` 路徑(來源唯讀)
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Tasks/v1.0.0/fixed.md`(§1–2:yaml 編碼教訓)
