---
id: task-002
title: 變動偵測引擎(pg_stat_user_tables 讀取 + signature 比對)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/mirror.py
  - backend/tests/test_change_detection.py
estimated_hours: 3
---

## 目標

在 `mirror.py` 新增「零掃表變動偵測」能力:一句 query 讀來源 `pg_stat_user_tables` 取全表寫入計數器,並提供**無狀態純函式**判斷某表相對上次基準是否有變動(含計數器倒退保守處理、無基準視為變動)。**不改**既有 `mirror_table` / config-driven 引擎。

## 設計要點

- `mirror.py` 加常數 SQL(對 source engine,零掃表):
  ```sql
  SELECT schemaname AS schema, relname AS name, n_tup_ins, n_tup_upd, n_tup_del
  FROM pg_stat_user_tables
  ```
- `@dataclass(frozen=True) StatSignature`:`ins: int` / `upd: int` / `del_: int`(欄名避開關鍵字,對外仍映 `n_tup_del`)。
- `MirrorEngine.fetch_source_signatures() -> dict[tuple[str, str], StatSignature]`:讀 `pg_stat_user_tables`,回 `(schema, table) → StatSignature`;lazy 連線沿用 `_source_engine()`。系統 schema(pg_catalog/information_schema)天然不在 user_tables,無需過濾。
- **純函式** `is_table_changed(prev: StatSignature | None, current: StatSignature) -> bool`:
  - `prev is None`(首次/新表,對齊 propose「首次/新表基準建立」)→ `True`
  - 任一 `current.* > prev.*`(有新增/改/刪)→ `True`
  - 任一 `current.* < prev.*`(計數器倒退:DB 重啟/crash/`pg_stat_reset()`,對齊 propose「保守處理」)→ `True`
  - 三者皆相等 → `False`(跳過)
- 型別 / 機密 / 引號規範沿用檔頭既有慣例;`track_counts` 未開 → `pg_stat_user_tables` 回空 → 偵測不到任何表(task-004 需處理空結果,見該 task)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_change_detection.py -q` 全綠,涵蓋:
  - `is_table_changed(None, sig)` → True(無基準)
  - 任一計數器增加 → True;三者相等 → False
  - 任一計數器倒退(current < prev)→ True
- [x] `uv run python -c "from app.etl.mirror import is_table_changed, StatSignature; print(is_table_changed(None, StatSignature(0,0,0)), is_table_changed(StatSignature(5,5,5), StatSignature(5,5,5)), is_table_changed(StatSignature(5,5,5), StatSignature(4,5,5)))"` 印出 `True False True`
- [x] `grep -n "def mirror_table" backend/app/etl/mirror.py` 仍存在且 `git diff` 不改動其內文(僅新增偵測相關)
- [x] `uv run ruff check . && uv run mypy app` green

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/05-exceptions-and-logging.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
