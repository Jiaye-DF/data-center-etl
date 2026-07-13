"""角色收斂為 admin / member(單表字串,無 roles 表、無外鍵關聯)。

決議(使用者明示):不採 roles 表 + FK 設計;角色只有 admin、member 兩種,直接以字串
存於 users.role。原 v1.4.1 的 roles 表 / users.role_pid 路線已整批回退(migration
鏈退回 v6,本支為其後的唯一角色調整)。

本 migration:
- 舊 check(admin / viewer)換成 admin / member
- 既有 viewer 使用者一律改為 member
- 新建使用者預設角色由 viewer 改為 member

upgrade 以存在性 guard 可重入。downgrade 依 CLAUDE.md 禁 DROP:僅還原 check /
default 的定義(不刪欄位、不刪資料),member 值一併換回 viewer。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v7"
down_revision: str | None = "v6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_CK_NAME = "ck_users_role"


def _has_check_constraint(table: str, name: str) -> bool:
    constraints = sa.inspect(op.get_bind()).get_check_constraints(table)
    return any(c["name"] == name for c in constraints)


def upgrade() -> None:
    bind = op.get_bind()

    # 先卸舊 check,否則 viewer → member 的 UPDATE 會被舊約束擋下
    if _has_check_constraint("users", _CK_NAME):
        op.drop_constraint(_CK_NAME, "users", type_="check")

    bind.execute(sa.text("UPDATE users SET role = 'member' WHERE role = 'viewer'"))
    op.alter_column("users", "role", existing_type=sa.String(length=20), server_default="member")
    op.create_check_constraint(_CK_NAME, "users", "role IN ('admin', 'member')")


def downgrade() -> None:
    bind = op.get_bind()

    if _has_check_constraint("users", _CK_NAME):
        op.drop_constraint(_CK_NAME, "users", type_="check")

    bind.execute(sa.text("UPDATE users SET role = 'viewer' WHERE role = 'member'"))
    op.alter_column("users", "role", existing_type=sa.String(length=20), server_default="viewer")
    op.create_check_constraint(_CK_NAME, "users", "role IN ('admin', 'viewer')")
