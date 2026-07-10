"""v1.4.1:users.role_pid 收 NOT NULL(承接 v7 / fixed.md §1)。

v7 因建立使用者路徑(UserRepository.create)當時尚未寫入 role_pid 而暫留 nullable;
task-002 已補齊所有建立路徑的關聯寫入,本 migration 先 backfill 殘餘 NULL
(防 v7 之後、v8 之前新建的使用者),再收 NOT NULL。

backfill 後仍有 NULL(users.role 字串無對應 roles.code)→ 直接炸,禁默默收約束失敗。
upgrade 以存在性 guard 可重入(已 NOT NULL 即略過);downgrade 依 CLAUDE.md 禁 DROP,no-op。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v8"
down_revision: str | None = "v7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _role_pid_is_nullable() -> bool:
    columns = sa.inspect(op.get_bind()).get_columns("users")
    column = next(col for col in columns if col["name"] == "role_pid")
    return bool(column["nullable"])


def upgrade() -> None:
    bind = op.get_bind()

    # ── backfill 殘餘 NULL(v7 之後、v8 之前新建的使用者;重跑安全)────────
    bind.execute(
        sa.text(
            "UPDATE users SET role_pid = roles.pid "
            "FROM roles "
            "WHERE users.role_pid IS NULL "
            "AND roles.code = users.role "
            "AND roles.is_deleted = false"
        )
    )

    # ── fail-fast:仍有 NULL 代表 role 字串無對應角色,炸得明確 ─────────────
    remaining = bind.execute(
        sa.text("SELECT count(*) FROM users WHERE role_pid IS NULL")
    ).scalar()
    if remaining:
        raise RuntimeError(
            f"users.role_pid 仍有 {remaining} 筆 NULL(role 字串無對應 roles.code),"
            "請先修正資料再重跑 migration"
        )

    # ── 收 NOT NULL(可重入:已 NOT NULL 即略過)──────────────────────────
    if _role_pid_is_nullable():
        op.alter_column(
            "users",
            "role_pid",
            existing_type=sa.BigInteger(),
            nullable=False,
        )


def downgrade() -> None:
    # 依 CLAUDE.md 禁 DROP / 對齊 v7 慣例:no-op(NOT NULL 保留);
    # upgrade 以存在性 guard 可重入,round-trip 安全。
    pass
