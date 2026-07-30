"""v1.6.0 API Client 機器身分:api_client_users + api_client_secrets(task-001)。

與後台 users / 角色體系完全分離,不動既有任何表。只建表建索引;downgrade 對稱刪除
本次新建的兩張表(僅撤銷自己新增內容;此 drop_table 為 CLAUDE.md 明定的
round-trip 必要例外)。

down_revision 接續實際 head `v152`(v151_semantic_source_updated_by_uuid.py):task 檔
原述「接續 v7」係基於 v7 為最新的舊資訊,直接掛 v7 會造成多頭分支
(`04-databases/08-alembic.md` 明禁),故掛在真正的鏈尾。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v8"
down_revision: str | None = "v152"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    """BaseModel 必備欄位(pid / uid / is_deleted / created_at / updated_at /
    created_by / updated_by)。"""
    return [
        sa.Column(
            "pid",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="內部主鍵(禁對外)/ Internal primary key (never exposed)",
        ),
        sa.Column(
            "uid",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="對外識別碼(UUID)/ External unique identifier (UUID)",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="軟刪除旗標 / Soft-delete flag",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="建立時間(UTC+8)/ Created at (UTC+8)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新時間(UTC+8)/ Updated at (UTC+8)",
        ),
        sa.Column(
            "created_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="建立者(users.uid)/ Created by (users.uid)",
        ),
        sa.Column(
            "updated_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="最後更新者(users.uid)/ Updated by (users.uid)",
        ),
    ]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("api_client_users"):
        op.create_table(
            "api_client_users",
            *_base_columns(),
            sa.Column(
                "client_id",
                sa.String(length=100),
                nullable=False,
                comment="取 token 識別碼 / Client identifier for token issuance",
            ),
            sa.Column(
                "name",
                sa.String(length=255),
                nullable=False,
                comment="應用系統名稱 / Application name",
            ),
            sa.Column(
                "description",
                sa.Text(),
                nullable=True,
                comment="用途說明 / Usage description",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'enabled'"),
                comment="狀態(enabled / disabled)/ Status (enabled / disabled)",
            ),
            sa.Column(
                "rate_limit_per_minute",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("30"),
                comment="每分鐘請求上限 / Request limit per minute",
            ),
            sa.Column(
                "rate_limit_per_10min",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("200"),
                comment="每 10 分鐘請求上限 / Request limit per 10 minutes",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_api_client_users_uid"),
            sa.CheckConstraint(
                "status IN ('enabled', 'disabled')", name="ck_api_client_users_status"
            ),
            comment=(
                "API Client 機器身分(與後台 users 分離)"
                "/ API client machine identity (separate from admin users)"
            ),
        )
    # 軟刪除後允許重建同 client_id → partial unique index(比照 uq_users_username)
    op.create_index(
        "uq_api_client_users_client_id",
        "api_client_users",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )

    if not _has_table("api_client_secrets"):
        op.create_table(
            "api_client_secrets",
            *_base_columns(),
            sa.Column(
                "api_client_user_pid",
                sa.BigInteger(),
                nullable=False,
                comment=(
                    "所屬 API Client(api_client_users.pid)"
                    "/ Parent API client (api_client_users.pid)"
                ),
            ),
            sa.Column(
                "secret_hash",
                sa.Text(),
                nullable=False,
                comment="密鑰雜湊(bcrypt,禁明文)/ Secret hash (bcrypt only)",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'active'"),
                comment="狀態(active / retired)/ Status (active / retired)",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_api_client_secrets_uid"),
            sa.ForeignKeyConstraint(
                ["api_client_user_pid"],
                ["api_client_users.pid"],
                name="fk_api_client_secrets_api_client_user",
            ),
            sa.CheckConstraint(
                "status IN ('active', 'retired')", name="ck_api_client_secrets_status"
            ),
            comment=(
                "API Client 密鑰(雙鑰輪替,只存 bcrypt 雜湊)"
                "/ API client secrets (dual-key rotation, bcrypt hash only)"
            ),
        )
    op.create_index(
        "idx_api_client_secrets_api_client_user_pid",
        "api_client_secrets",
        ["api_client_user_pid"],
        if_not_exists=True,
    )


def downgrade() -> None:
    # 對稱刪除本次新建的兩張表(先子後父;不動既有表,見 CLAUDE.md round-trip 例外)
    if _has_table("api_client_secrets"):
        op.drop_table("api_client_secrets")
    if _has_table("api_client_users"):
        op.drop_table("api_client_users")
