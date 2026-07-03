---
id: task-001
title: 自有 DB schema(models + migration)+ v1.1.0 後端依賴鎖版
status: done
parallel: true
depends_on: []
affected_files:
  - backend/app/models/user.py
  - backend/app/models/etl_table.py
  - backend/app/models/etl_mapping.py
  - backend/app/models/schedule.py
  - backend/app/models/etl_run.py
  - backend/app/models/etl_run_log.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/xxxx_add_v110_core_tables.py
  - backend/pyproject.toml
  - backend/uv.lock
  - backend/tests/test_models_v110.py
estimated_hours: 4
---

## 目標

建立 v1.1.0 全部自有 DB 資料表的 SQLAlchemy models 與 alembic migration:使用者(含角色)、ETL 表設定、mapping(含欄位 Comment)、排程定義、執行紀錄、逐表詳細 log。並**一次性**把 v1.1.0 後端新依賴(taskiq / taskiq-redis / bcrypt 等)鎖版進 `pyproject.toml`,後續 task **不再動** `pyproject.toml` / `uv.lock`(避免互鎖)。

## 範圍要點

- 資料表(名稱可依 `04-databases/01-identifiers.md` 調整):`users`(本地帳密雜湊 + `role`:admin/viewer,不做獨立 role 表)、`etl_tables`(來源/目標/啟用狀態)、`etl_mappings`(欄位對照 + comment)、`schedules`(cron 式定義 + 啟停)、`etl_runs`(一次執行:觸發方式/起訖/狀態)、`etl_run_logs`(**逐表**明細:筆數/耗時/狀態/錯誤含 stack trace)。
- 全表遵循 BaseModel 必備欄位 + 軟刪除(`04-databases/00-overview.md` / `02-soft-delete.md`);pid 內部 / uid 對外(`01-identifiers.md`);時間欄位對齊 `06-timezone.md`。
- 密碼欄只存雜湊(`03-passwords-and-pii.md`),本 task 只建欄位,登入邏輯屬 task-002。
- migration 只增不刪(**禁 DROP**,遵守 CLAUDE.md);downgrade 僅撤銷本次新增。
- 依賴新增全部附版號鎖定(`00-overview/01-versions.md`)。

## Acceptance

- [x] `cd backend && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip OK
- [x] `cd backend && uv run pytest tests/test_models_v110.py -q` 全綠(模型欄位/約束斷言)
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠
- [x] `grep -qE "taskiq" backend/pyproject.toml && grep -qE "bcrypt|passlib" backend/pyproject.toml` 成立(依賴已鎖入)
- [x] `! grep -iE "drop (table|column|schema|database)" backend/alembic/versions/*add_v110*` 成立(upgrade 段無 DROP;downgrade 撤銷除外)

## 必讀檔(Just-in-time)

- `docs/Design-Base/04-databases/00-overview.md`(BaseModel / 必備欄位,永遠讀)
- `docs/Design-Base/04-databases/01-identifiers.md`(pid / uid)
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
- `docs/Design-Base/04-databases/06-timezone.md` + `docs/Design-Base/00-overview/05-timezone.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/00-overview/01-versions.md`(依賴鎖版)
