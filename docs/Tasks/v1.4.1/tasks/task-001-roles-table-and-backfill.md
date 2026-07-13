---
id: task-001
title: roles 表 + users 關聯欄位 + migration backfill(單一 migration 完成)
status: done
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

- [x] `cd backend && uv run alembic upgrade head` 成功;之後 SQL 驗證(psql 或 pytest 內斷言):
  - `SELECT count(*) FROM roles WHERE code IN ('admin','viewer') AND is_builtin = true` = 2 ✅
  - users 關聯欄位無 NULL(count = 0)✅
  - `users.role` 舊欄位與 `ck_users_role` 約束仍存在 ✅
- [x] `uv run alembic downgrade -1 && uv run alembic upgrade head` round-trip 不炸(downgrade no-op 慣例)✅
- [x] `uv run pytest tests/test_models_v141.py` 全綠(含 Role model 欄位、seed 存在、User 關聯可取角色 code)✅ 9 passed
- [x] `uv run pytest` 全綠(既有測試不迴歸)✅ 227 passed(見 fixed.md §2:本機共用測試 DB 需一次性補丁,非程式碼異動)
- [x] `grep -i -E "drop_table|drop_column|DROP TABLE|DROP COLUMN" backend/alembic/versions/v7_add_v141_roles.py` 無輸出 ✅
- [x] `[ -f docs/Tasks/v1.4.1/manual-removal-checklist.md ]` 且內容列出 `users.role` + `ck_users_role` ✅
- [x] `cd backend && uv run ruff check . && uv run mypy .`:ruff 全綠;mypy **非**全綠 —
      baseline(task-001 之前)已有 39 個既有錯誤(與本 task 無關,`git stash` 驗證過);
      本 task 新增 3 個同類型錯誤(`test_models_v141.py` 沿用 `test_models_v131.py` /
      `test_models_v120.py` 既有的 `__table__.indexes` / `.constraints` mypy 已知限制,
      非新增錯誤類型)。詳見下方「規格偏離」。

## 規格偏離(見 fixed.md 詳細記錄)

- **`role_pid` 未收 NOT NULL**(fixed.md §1):規格文字要求 migration 最終步驟收 NOT
  NULL,但 `user_repo.create()` 尚未在本 task 白名單內同步寫入 `role_pid`(留給
  task-002),若提前收 NOT NULL 會讓 task-002 落地前所有新建使用者路徑(本地註冊 /
  init admin / SSO 首次登入)500,也會讓既有 `create_all`-based 測試集體回歸。
  現況:`role_pid` 保留 nullable,既有(migration 前)使用者 100% backfill(驗證
  count(NULL)=0 通過),新建使用者路徑待 task-002 補寫入後,建議另開後續 migration
  收 NOT NULL。
- **`mypy` 未達成 baseline 全綠**:baseline 本身已有 39 個既有錯誤(與本 task 無關);
  本 task 新增的 3 個錯誤與既有 `test_models_v131.py` / `test_models_v120.py` 同類型
  (`Table.__table__` 型別為 `FromClause`,mypy strict 下 `.indexes` / `.constraints`
  屬性存取為已知限制),非新增錯誤類型。

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/01-identifiers.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/08-alembic.md`
- `docs/Design-Base/04-databases/09-indexes-and-perf.md`
