# 08-alembic — Migration 規範

> **何時讀**:寫 migration 才讀。

- 命名:`v{N}_{slug}.py` 或 `YYYY_MM_DD_HHMM-{slug}.py`(專案內統一)
- **禁**修改已合併到 main 的 migration → 建新 revision
- `down_revision` **必**正確;禁孤兒 / 多頭分支
- migration 須冪等:DDL 用 `IF NOT EXISTS` / `IF EXISTS`
- production 前 `alembic upgrade head` + `alembic downgrade -1` round-trip 驗證
- 一個 migration 只做一件事
