---
id: task-001
title: roles 表 + users 關聯欄位 + migration backfill(單一 migration 完成)
status: pending
parallel: false
depends_on: []
affected_files:
  - backend/app/models/role.py
  - backend/app/models/user.py
  - backend/app/models/__init__.py
  - backend/alembic/versions/v7_add_v141_roles.py
  - backend/tests/test_models_v141.py
  - docs/Tasks/v1.4.1/manual-removal-checklist.md
estimated_hours: 3
---

## 目標

新增 `roles` 表為角色唯一事實來源,`users` 加外鍵關聯並在**同一 migration** 內完成 backfill(建表 → seed → 加欄 → backfill),避免「有 user 無角色」中間態;既有 `users.role` 字串欄位與 `ck_users_role` 約束**原樣保留、標記 deprecated**,並產出人工移除清單。

## 規格

- `Role` model(`backend/app/models/role.py`,繼承 `BaseModel` 沿用 pid/uid/is_deleted 等基底欄位):
  - `code`:角色代碼,唯一(partial unique index on `is_deleted = false`,對齊 `users.username` 前例)
  - `name`:顯示名稱;`description`:描述(nullable)
  - `is_builtin`:系統內建標記(內建角色禁刪、禁改代碼 — 本版無角色 CRUD,此欄為未來 enforcement 地基,先入表)
- seed 內建兩筆:`admin`(管理員)/ `viewer`(檢視者),`is_builtin = true`;seed 的 `created_by` / `updated_by` 用全零 UUID 系統帳號(對齊 `audit_service.SYSTEM_ACTOR_UID` 約定)
- `users` 加關聯欄位(命名依 `04-databases/01-identifiers.md` 慣例,FK → `roles`;model 上建立 relationship 供守衛/回應取值)
- migration `v7_add_v141_roles.py`:
  - upgrade 順序:建 `roles` 表 → seed 兩筆 → `users` 加欄(nullable)→ backfill(依現行 `users.role` 字串值對應 roles.code)→ 收 NOT NULL
  - upgrade 以存在性 guard 可重入(失敗可重跑;對齊 v5 / v6 前例)
  - downgrade 為 no-op + 註記(依 CLAUDE.md 禁 DROP;對齊 v6 前例)
  - **禁**任何 `drop_table` / `drop_column` / DROP SQL
- `users.role` 欄位 comment 與程式註解標 deprecated(**不**移除、**不**改 `ck_users_role`)
- `docs/Tasks/v1.4.1/manual-removal-checklist.md`:列出 `users.role` 欄位 + `ck_users_role` 約束的人工移除步驟與前置條件(確認無程式讀取後才可移除)

## Acceptance

- [ ] `cd backend && uv run alembic upgrade head` 成功;之後 SQL 驗證(psql 或 pytest 內斷言):
  - `SELECT count(*) FROM roles WHERE code IN ('admin','viewer') AND is_builtin = true` = 2
  - users 關聯欄位無 NULL(count = 0)
  - `users.role` 舊欄位與 `ck_users_role` 約束仍存在
- [ ] `uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip 不炸(downgrade no-op 慣例)
- [ ] `uv run pytest tests/test_models_v141.py` 全綠(含 Role model 欄位、seed 存在、User 關聯可取角色 code)
- [ ] `uv run pytest` 全綠(既有測試不迴歸)
- [ ] `grep -i -E "drop_table|drop_column|DROP TABLE|DROP COLUMN" backend/alembic/versions/v7_add_v141_roles.py` 無輸出
- [ ] `[ -f docs/Tasks/v1.4.1/manual-removal-checklist.md ]` 且內容列出 `users.role` + `ck_users_role`
- [ ] `cd backend && uv run ruff check . && uv run mypy .` 全綠

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
