---
id: task-002
title: 英文草稿匯入 RDS semantic_mappings + 複核輔助腳本(A2)
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/scripts/seed_semantic_mappings.py
  - backend/tests/test_seed_semantic_mappings.py
estimated_hours: 3
---

## 目標

把已完成的全量英文草稿(`docs/ERP-Analyze/data/semantic_draft.tsv`:333 表+11,947 欄)匯入 RDS `erp_metadata.semantic_mappings`(`status='draft'`),並提供複核轉 `confirmed` 的腳本化路徑。**複核本身延後**(user 決議),本 task 只建機制。

## 內容

- 新增 `backend/scripts/seed_semantic_mappings.py`(對齊 `scripts/seed_etl_config.py` 風格):
  - 讀 TSV(`--tsv PATH`,預設 `docs/ERP-Analyze/data/semantic_draft.tsv`;encoding="utf-8"),欄位 `TABLE_NAME/COLUMN_NAME/EN_NAME/ZH_NAME/SRC`。
  - 逐列 upsert:不存在 → insert `status='draft'`;已存在且 `status='confirmed'` → **不覆寫**(保護人工複核成果);已存在 draft → 更新 english_name/zh_name。
  - 冪等重跑;結束輸出統計(新增/更新/略過 confirmed 數)。
  - 附 `--confirm-table <TABLE_NAME>` 參數:將該表全部列 `status` 轉 `confirmed`(複核用;驗收樣本表用)。
- TSV 呼叫端一律 bind params(`04-sql-safety.md`);先呼叫 task-001 的 `ensure_semantic_schema`。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_seed_semantic_mappings.py` 全綠(含:draft upsert、confirmed 不覆寫、`--confirm-table` 轉態、冪等重跑筆數不變)
- [x] `uv run ruff check scripts/seed_semantic_mappings.py` + mypy 全綠
- [x] dry-run 實測(測試 DB):對 3 列样本 TSV 跑兩次,semantic_mappings 恆為 3 列

## 必讀檔(Just-in-time)

- `docs/Design-Base/00-overview/00-overview.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/00-overview/05-timezone.md`
