---
id: task-003
title: common/writer — 目標寫入 + erp_etl_hub_test bootstrap + 欄位 Comment
status: done
parallel: true
depends_on: [task-001]
affected_files:
  - etl/common/writer.py
  - etl/common/ddl.py
  - etl/scripts/bootstrap_target_db.sql
  - etl/tests/test_ddl.py
estimated_hours: 3
---

## 目標

實作目標端寫入:`common/writer.py` 把 DataFrame 落地到 `erp_etl_hub_test`(表名沿用原始 `table_name`);`common/ddl.py` 依 GAQ 欄位描述**為每一欄位產生 `COMMENT ON COLUMN`**;`scripts/bootstrap_target_db.sql` 提供目標 DB / schema 的一次性建置(僅 CREATE,**禁** DROP)。

## 範圍要點

- `writer.py`:`write_table(df, schema, table, comments: dict)`(或等價),寫入後套用欄位 Comment。
- `ddl.py`:純函式 `build_column_comments(table, comments) -> list[str]`,對表中**每一欄位**產生 `COMMENT ON COLUMN`;缺描述的欄位需明確報錯或標記(不可靜默略過)。
- Comment 內容來源為 mapping yaml(GAQ_FILE 對照),由 004/005 提供;本 task 只做**機制**。
- `bootstrap_target_db.sql`:`CREATE DATABASE` / `CREATE SCHEMA IF NOT EXISTS` 等,**只增不刪**(遵守 CLAUDE.md 毀滅性操作禁止)。
- 識別字 / SQL 安全對齊 `04-databases/04-sql-safety.md`。

## Acceptance

- [x] `python -m py_compile etl/common/writer.py etl/common/ddl.py` 通過(exit 0)
- [x] `cd etl && python -m pytest tests/test_ddl.py -q` 全綠;測試需涵蓋「N 欄位 → 產生 N 條 `COMMENT ON COLUMN`」與「缺 comment 欄位會 raise/標記」
- [x] `python -c "import etl.common.ddl as d; print(hasattr(d,'build_column_comments'))"` 印 `True`
- [x] `! grep -iE "drop (database|schema|table|column)" etl/scripts/bootstrap_target_db.sql`(bootstrap 無任何 DROP)
- [x] `grep -qi "create" etl/scripts/bootstrap_target_db.sql`(含建置語句)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`(DB 風格地板)
- `docs/Design-Base/04-databases/01-identifiers.md`(識別字規範)
- `docs/Design-Base/04-databases/04-sql-safety.md`(SQL 安全)
- `docs/Design-Base/04-databases/06-timezone.md`(時間欄位一致)
