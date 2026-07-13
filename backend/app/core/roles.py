"""角色定義(單一事實來源)。

角色不設表、不做外鍵關聯:僅 admin / member 兩種,以字串存於 `users.role`
並由 CHECK 約束 `ck_users_role` 把關。新增角色 = 改本檔 + 一支 migration 換 CHECK。
"""

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"

DEFAULT_ROLE = ROLE_MEMBER

# (code, name, description) — 供 /roles 端點與前端下拉使用
ROLES: tuple[tuple[str, str, str], ...] = (
    (ROLE_ADMIN, "管理員", "系統管理員,擁有全部管理權限"),
    (ROLE_MEMBER, "成員", "一般成員,唯讀檢視權限"),
)

ROLE_CODES: frozenset[str] = frozenset(code for code, _, _ in ROLES)

# 與 migration 內的 CHECK 定義一致(改這裡務必同步開 migration)
ROLE_CHECK_SQL = "role IN ('admin', 'member')"
