"""v1.6.0 task-009:api_client_secrets 加 secret_encrypted(可逆加密明文,供 admin 檢視)。

只加欄不刪欄;既有列為 NULL = 舊密鑰無可檢視明文(前端顯示「輪替後可檢視」)。
downgrade 僅撤本次新增的該欄(CLAUDE.md 明定的 round-trip 必要例外,不動其他結構)。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v9"
down_revision: str | None = "v8"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "api_client_secrets"
_COLUMN = "secret_encrypted"


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(_TABLE):
        return False
    return any(col["name"] == _COLUMN for col in inspector.get_columns(_TABLE))


def upgrade() -> None:
    if not _has_column():
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.Text(),
                nullable=True,
                comment=(
                    "密鑰明文可逆加密(Fernet;NULL = 舊列無明文)"
                    "/ Reversibly encrypted secret (Fernet; NULL = legacy row)"
                ),
            ),
        )


def downgrade() -> None:
    if _has_column():
        op.drop_column(_TABLE, _COLUMN)
