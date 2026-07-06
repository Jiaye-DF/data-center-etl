---
id: task-001
title: DB schema:rds_table_meta 計數器 signature 欄 + migration
status: pending
parallel: true
depends_on: []
affected_files:
  - backend/app/models/rds_table_meta.py
  - backend/alembic/versions/v4_add_v130_sync_signature.py
  - backend/tests/test_models_v130.py
estimated_hours: 2
---

## 目標

為增量同步落地資料層:`rds_table_meta` 加「上次同步時該表的 `pg_stat_user_tables` 計數器基準」欄位(供下輪比對)+「是否排除於同步排程」旗標(可逐表排除)。單支 `v4` migration。**不動排程相關 schema**(排程單一化為同步,不引入 `job_type`;`schedules.etl_table_pid` 保留 NULL、禁 DROP)。

## 設計要點

- `models/rds_table_meta.py`:
  - 加三個 nullable 計數器基準欄(對齊 propose「last_stat_ins/last_stat_upd/last_stat_del 或等價」):
    - `last_stat_ins` / `last_stat_upd` / `last_stat_del`:`Mapped[int | None]`(`BigInteger`,nullable=True,`comment` 繁中+英),語意「上次同步成功時該來源表 `n_tup_ins/upd/del` 累計值」;NULL = 尚無基準(首次/新表 → task-004 視為變動)。
  - 加排除旗標(可逐表排除,對齊 propose ⑦「全表預設納入 + 可逐表排除」):
    - `sync_excluded`:`Mapped[bool]`(`Boolean`,nullable=False,`default=False`,`server_default=text("false")`,`comment` 繁中+英),語意「是否排除於夜間增量排程」;**預設 false = 預設納入**(新表自動納入)。
  - 只加欄,不動既有欄 / index / unique constraint。
- `alembic/versions/v4_add_v130_sync_signature.py`:`revision="v4"` / `down_revision="v3"`。
  - `upgrade`:對 `rds_table_meta` `op.add_column` 三個計數器欄(nullable)+ `sync_excluded`(`server_default=sa.text("false")`,nullable=False → 既有列自動回填 false),以存在性 guard(inspect columns)包住使 `upgrade` 可重入。
  - `downgrade`:**禁 DROP COLUMN**(CLAUDE.md)。前進式:欄位保留,不 DROP COLUMN(附註原因);如本次有新增 index/constraint 才對稱撤銷(本 task 未加)。
- 對齊 v3 風格:欄位 comment 雙語、guard 以 `sa.inspect(op.get_bind())`。

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` 成功;再次 `uv run alembic upgrade head` 冪等不報錯(可重入 guard)
- [ ] `uv run python -c "from app.models import RdsTableMeta; print(RdsTableMeta.last_stat_ins, RdsTableMeta.last_stat_upd, RdsTableMeta.last_stat_del, RdsTableMeta.sync_excluded)"` 無 AttributeError
- [ ] `uv run pytest tests/test_models_v130.py -q` 全綠(斷言四新欄存在;計數器欄可為 NULL、BigInteger;`sync_excluded` server_default=false、not null)
- [ ] `grep -n "drop_column" backend/alembic/versions/v4_add_v130_sync_signature.py` 無輸出(遵守禁 DROP COLUMN)
- [ ] `uv run ruff check . && uv run mypy app` green

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/06-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/03-backend/00-overview.md`
