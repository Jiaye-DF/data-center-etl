---
id: task-002
title: view schema 後綴改 `_view`(系統側;RDS 既有 schema 由 user ALTER RENAME)
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/etl/view_generator.py
  - backend/tests/test_view_generator.py
estimated_hours: 1
---

## 目標

語意化 view 落點從 `<schema>_en` 改為 `<schema>_view`。**RDS 既有 4 個 `_en` schema 由 user 手動 `ALTER SCHEMA ... RENAME TO ..._view`**(非 DROP,view 隨 schema 平移;見 propose 變更紀錄 2026-07-21);本 task 只改系統側,確保之後產生 / 重生的 view 一律落在 `_view`。

## 內容

- `VIEW_SCHEMA_SUFFIX` 改 `"_view"`。
- 帳套 schema 內省排除條件改排除 `%_view`(既有 `%_en` 排除可一併保留,防莫名殘留;二者皆非帳套 schema)。
- 產生器行為不變:只 `CREATE SCHEMA IF NOT EXISTS` + `CREATE OR REPLACE VIEW`;42P16 才 DROP VIEW 重建;不產生任何對 `_en` 的操作。
- user 已 RENAME 的情境下,view 已存在於 `_view` schema,簽名未變動而略過重生是**正確行為**(不需強制重生機制)。

## Acceptance

- [x] `cd backend && uv run pytest tests/test_view_generator.py` 全綠(含:view 落在 `<schema>_view`、`_view` / `_en` schema 皆不被列為帳套 schema)
- [x] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤
- [x] `grep -n "_view" backend/app/etl/view_generator.py` 含後綴常數;無任何以 `_en` 為落點的產生邏輯

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
