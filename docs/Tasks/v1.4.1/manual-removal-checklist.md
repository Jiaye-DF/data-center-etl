# manual-removal-checklist —— 已作廢(roles 表設計整體回退)

> **2026-07-13 更新**:本清單原本規劃「移除 deprecated 的 `users.role` 字串欄位、
> 改以 `roles` 表 + `users.role_pid` FK 為角色唯一事實來源」。該設計已由使用者決議
> **整體回退**:不設 roles 表、不做外鍵關聯,角色回歸 `users.role` 字串。
> 本檔僅保留作歷史留痕,清單內容不再有效。

## 現行角色設計(取代本清單)

- 角色只有兩種:**`admin`** / **`member`**,定義於 `backend/app/core/roles.py`(單一事實來源)
- 儲存:`users.role`(`VARCHAR(20)`,`NOT NULL`,`DEFAULT 'member'`),由 CHECK 約束
  `ck_users_role: role IN ('admin', 'member')` 把關
- **無 `roles` 表、無外鍵關聯**;`GET /roles` 端點改回傳程式常數清單(供前端下拉)
- 新增角色的做法 = 改 `app/core/roles.py` + 開一支 migration 換 CHECK 約束

## 回退執行紀錄(2026-07-13,使用者明示決議)

| 項目 | 處置 |
| --- | --- |
| migration 鏈 | 刪除 v7(roles 表 + role_pid)、v8(role_pid NOT NULL)、以及本次期間新增的 v9 / v10;**鏈回到 v6**,其後新增單一支 `v7_role_admin_member.py`(viewer → member + CHECK 換 admin/member) |
| `roles` 表 | **DROP TABLE**(使用者明示授權;CLAUDE.md 預設禁 DROP,此為例外決議) |
| `users.role_pid` | DROP COLUMN(含 FK `fk_users_role`、index `idx_users_role_pid`) |
| `users.role` | 加回字串欄位,值由原 `role_pid → roles.code` 換算;既有 `viewer` 一律轉 `member` |
| 程式碼 | 刪除 `models/role.py`、`repositories/role_repo.py`、`tests/test_models_v141.py`;`resolve_role_code()` 改為直接讀 `user.role`;新增 `core/roles.py` |
| 前端 | `UserRole` 型別 `'admin' | 'member'`;`isViewer` → `isMember`;Header 角色標籤 `member: '成員'`;`RoleOption` 去除 `uid` / `is_builtin` |
| 備份 | 回退前 `pg_dump` 至 `.backup/roles-users-before-v6-rollback.sql`(users / roles / alembic_version 資料) |

驗證:本地 `docker compose up -d --build` 全服務 healthy;alembic `v6 → v7` 實跑成功;
後端測試 **229 passed**、ruff 全過;前端 typecheck / lint 全過;
實打 API 確認 `/auth/login`、`/roles`(回 admin / member)、`/users`、`PATCH /users/{uid}/role`
(自降防呆 403、未知角色 `viewer` → 404)行為正確。
