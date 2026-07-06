---
id: task-003
title: signature repo 讀寫方法(讀基準 / 更新基準)
status: pending
parallel: true
depends_on: [task-001]
affected_files:
  - backend/app/repositories/rds_table_meta_repo.py
  - backend/tests/test_rds_table_meta_repo_v130.py
estimated_hours: 2
---

## 目標

`RdsTableMetaRepository` 加方法:讀取來源表計數器基準(供 task-004 比對)、同步成功後更新基準、讀取被排除的表集合(供 task-004 增量時略過)。沿用既有未刪除範圍與 `flush` 慣例;不動既有 `upsert_snapshot` / `list_by_schema` / `mark_*`。

## 設計要點

- 依賴 task-001 已加 `RdsTableMeta.last_stat_ins/last_stat_upd/last_stat_del` 與 `sync_excluded`。
- `get_signatures(dataset: Dataset) -> dict[tuple[str, str], tuple[int | None, int | None, int | None]]`:
  - 一次讀該 dataset(SOURCE)全表快照的 `(schema_name, table_name) → (last_stat_ins, last_stat_upd, last_stat_del)`(未刪除範圍);供 worker 批次比對(避免逐表 query)。
- `update_signature(dataset, schema_name, table_name, *, ins, upd, del_, actor_uid) -> None`:
  - `update(RdsTableMeta)` where dataset+schema+table+`is_deleted=False`,`values(last_stat_ins=ins, last_stat_upd=upd, last_stat_del=del_, updated_by=actor_uid, updated_at=_db_now())`;`flush()`。
  - 語意:記錄「本輪同步成功當下」的來源計數器,作為下輪比對基準(對齊 propose「同步狀態存放」)。
- `get_excluded_tables(dataset: Dataset) -> set[tuple[str, str]]`:
  - 讀該 dataset(SOURCE)`sync_excluded=True` 且未刪除的 `(schema_name, table_name)` 集合;供 task-004 增量同步略過被排除的表。
- 命名 / 型別對齊既有 repo 風格(`_db_now()`、未刪除過濾、`flush`)。

## Acceptance

- [ ] `cd backend && uv run pytest tests/test_rds_table_meta_repo_v130.py -q` 全綠,涵蓋:
  - 對已存在快照 `update_signature` 後,`get_signatures` 回該表 `(ins, upd, del_)` 正確值
  - 未曾設定基準的表 → `get_signatures` 回 `(None, None, None)`
  - 已軟刪除的快照不出現在 `get_signatures`
  - `sync_excluded=True` 的表出現在 `get_excluded_tables`,`False` / 已刪除者不出現
- [ ] `uv run python -c "import app.repositories.rds_table_meta_repo as m; d=dir(m.RdsTableMetaRepository); print('get_signatures' in d, 'update_signature' in d, 'get_excluded_tables' in d)"` 印出 `True True True`
- [ ] `git diff backend/app/repositories/rds_table_meta_repo.py` 僅新增方法(既有方法未改)
- [ ] `uv run ruff check . && uv run mypy app` green

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/07-testing.md`
