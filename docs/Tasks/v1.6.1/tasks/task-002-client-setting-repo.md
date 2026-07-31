---
id: task-002
title: 權限資料存取層 repository(RDS 直讀寫 + 綁定防呆查詢)
status: done
parallel: false
depends_on: [task-001]
affected_files:
  - backend/app/repositories/client_setting_repo.py
  - backend/tests/test_client_setting_repo.py
estimated_hours: 3.5
model: opus
effort: medium
---

## 目標

建立權限階層的資料存取層:對 RDS `client_setting` schema 直接讀寫(不落自有 DB、無快照),含各表 CRUD、軟刪過濾、與刪除防呆所需的綁定計數查詢。

## 實作要點

- Session 管理比照 `semantic_mapping_repo.py` / `semantic_admin_service.py` 前例(RDS engine + async_sessionmaker;engine 建立失敗不得洩漏連線)。
- 讀取一律過濾 `is_deleted`;刪除一律軟刪(`04-databases/02-soft-delete.md` 命名強制)。
- 防呆查詢:`count_operations_by_service`、`count_profiles_referencing_operation`、`count_roles_by_profile`、`count_clients_by_role`、`count_active_bindings_by_exception_set`(未過期)——供 service 層擋 409。
- 批次置換(`operation_items` / `profile_operations` / `profile_items` / `exception_*`):同交易「軟刪舊集合 + 插入新集合」;移除作業時連動清該作業底下授權項。
- `client_roles` 指派為冪等置換(先軟刪既有再插新);`client_exception_sets` 含 `expires_at`。

## Acceptance

- [ ] `uv run pytest tests/test_client_setting_repo.py` 全綠(真實測試 DB:CRUD round-trip、軟刪不再出現、批次置換原子性、綁定計數正確、client_roles 置換後恆 ≤ 1 筆有效)
- [ ] `uv run ruff check app tests` + `uv run mypy app` 無新增錯誤

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/04-databases/00-overview.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/04-sql-safety.md`
- `docs/Design-Base/04-databases/07-connection.md`
