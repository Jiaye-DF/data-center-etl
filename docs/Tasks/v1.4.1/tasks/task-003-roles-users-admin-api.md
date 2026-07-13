---
id: task-003
title: 角色列表 API + 使用者清單 / 角色指派 API(admin only + 稽核 + 自降防呆)
status: done
parallel: false
depends_on: [task-002]
affected_files:
  - backend/app/api/v1/roles.py
  - backend/app/api/v1/users.py
  - backend/app/api/v1/__init__.py
  - backend/app/schemas/role.py
  - backend/app/schemas/user.py
  - backend/app/services/user_service.py
  - backend/app/repositories/role_repo.py
  - backend/app/repositories/user_repo.py
  - backend/app/models/user.py
  - backend/tests/conftest.py
  - backend/tests/test_users_api.py
estimated_hours: 4
---

## 目標

提供角色列表(已登入可讀)與使用者管理(admin only:清單 + 指派角色)後端 API;指派動作寫入既有稽核機制;admin 不可把自己降級(避免鎖死無 admin)。

> 依賴說明:與 task-002 同動 `user_repo.py`,且角色取值 helper 需先由 task-002 收斂 → 序列化。

## 規格

- `GET /api/v1/roles`(`require_login`,admin / viewer 皆可讀):回角色列表(`uid` / `code` / `name` / `description` / `is_builtin`),供前端下拉與後續權限整合
- `GET /api/v1/users`(`require_admin`):使用者清單 — `uid` / `username` / `display_name` / 登入來源(`provider`:有 `sso_subject` 為 `sso`,否則 `local`)/ 角色 code;分頁參數對齊既有清單 API 慣例(參 `audit_logs.py`);查詢須 eager load 角色關聯(禁 N+1)
- `PATCH /api/v1/users/{uid}/role`(`require_admin`):指派角色
  - body 帶目標角色 code;不存在的 code → 404 / 422(對齊既有錯誤慣例)
  - **自降防呆**:actor 對自己指派非 `admin` 角色 → 403(訊息明確:不可將自己降級)
  - dual-write:同步回寫 deprecated `users.role` 字串同值(與 task-002 建立路徑一致)
  - 稽核:`AuditService.log(action="role_assigned", target_type="user", target_uid=..., detail="舊角色 → 新角色")`,actor 為操作 admin
  - 指派後**不**發新 token / 不強制重登(守衛每請求讀 DB,下一請求即生效)
- 路由掛進 `api/v1/__init__.py`(`/roles`、`/users` prefix);response 一律 `ApiResponse` 殼
- service 層 `user_service.py` 承載清單 / 指派邏輯;repository 依 `02-soft-delete.md` 命名強制(排除 `is_deleted`)
- **承接 task-002 尾巴(fixed.md §3 / §4)**:
  - `models/user.py` 的 `role_pid` mapped_column 收緊 `nullable=False`(DB 已由 v8 收 NOT NULL,model 對齊;**只**動這一處,不重構其他欄位)
  - roles seed 冪等 fixture 中央化進 `tests/conftest.py`(admin / viewer 兩筆,存在即跳過),讓全新環境下所有共用測試 DB 的測試檔自立,不再依賴 dev DB 既有 seed

## Acceptance

- [x] `cd backend && uv run pytest tests/test_users_api.py` 全綠(8 個測試),含:
  - viewer `GET /api/v1/roles` 200;未登入 401
  - viewer `GET /api/v1/users` 403;admin 200 且每筆含 `username` / `display_name` / `provider` / 角色 code
  - admin `PATCH /api/v1/users/{uid}/role` 指派 viewer → admin 後,**該使用者下一請求呼叫寫入類 API 回 2xx**(即時生效);反向降回 viewer 後同請求 403
  - admin 對自己指派 `viewer` → 403
  - 指派成功後 `audit_logs` 可查到 `action = "role_assigned"` 且 `target_uid` 正確
  - 指派不存在的角色 code → 4xx(非 500,實測 404)
- [x] `uv run pytest` 全綠(239 個測試,全套不迴歸;含白名單外最小修正
      `test_models_v141.py` 一條斷言,見 fixed.md §5)
- [x] `curl -s -b <admin cookie> http://localhost:8000/api/v1/roles | jq -e '[.data.items[].code] | sort == ["admin","viewer"]'` 通過(`data` 為
      `{items:[...]}` 而非陣列,依 01-routing.md 外殼規範修正字面 jq path,見
      fixed.md §6;`docker compose up -d --build` 後對 dockerized 服務實測 PASS)
- [x] `cd backend && uv run ruff check . && uv run mypy .` 全綠(ruff 0 錯誤;
      mypy 42 個既有錯誤,與 HEAD 60b133b 基線一致,無新增)

## 必讀檔(Just-in-time)

- `docs/Design-Base/03-backend/00-overview.md`
- `docs/Design-Base/03-backend/01-routing.md`
- `docs/Design-Base/03-backend/02-auth.md`
- `docs/Design-Base/03-backend/03-async-and-tx.md`
- `docs/Design-Base/03-backend/07-testing.md`
- `docs/Design-Base/04-databases/02-soft-delete.md`
- `docs/Design-Base/04-databases/03-passwords-and-pii.md`
