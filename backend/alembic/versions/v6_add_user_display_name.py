"""為 users 加 display_name(SSO 顯示姓名)。

SSO 使用者取中央 /api/auth/me 回傳之 name 落地本欄,僅供前端顯示(非授權依據);
本地帳號可為 NULL。upgrade 以欄位存在性 guard 可重入;
downgrade 依 CLAUDE.md 禁 DROP COLUMN,欄位保留、不前進式移除。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v6"
down_revision: str | None = "v5"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(col["name"] == column for col in columns)


def upgrade() -> None:
    if not _has_column("users", "display_name"):
        op.add_column(
            "users",
            sa.Column(
                "display_name",
                sa.String(length=255),
                nullable=True,
                comment="顯示名稱(SSO 姓名)/ Display name",
            ),
        )


def downgrade() -> None:
    # 依 CLAUDE.md 禁 DROP COLUMN,display_name 欄位保留(upgrade 以存在性 guard 可重入)。
    pass
