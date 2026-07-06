"""v1.1.x 稽核紀錄表:audit_logs(R-PII-003)。

只建表建索引;downgrade 一律不動(禁 DROP,見 CLAUDE.md)。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v2"
down_revision: str | None = "v1"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _base_columns() -> list[sa.Column]:
    """BaseModel 必備欄位(pid / uid / is_deleted / created_at / updated_at / created_by / updated_by)。"""
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
            comment="建立者(users.uid;匿名事件為系統帳號)/ Created by (users.uid)",
        ),
        sa.Column(
            "updated_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="最後更新者(users.uid;匿名事件為系統帳號)/ Updated by (users.uid)",
        ),
    ]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("audit_logs"):
        op.create_table(
            "audit_logs",
            *_base_columns(),
            sa.Column(
                "actor_uid",
                PG_UUID(as_uuid=True),
                nullable=True,
                comment=(
                    "操作者(users.uid;登入失敗等匿名事件為 NULL)"
                    "/ Actor (users.uid; NULL when anonymous)"
                ),
            ),
            sa.Column(
                "actor_username",
                sa.String(length=100),
                nullable=True,
                comment="操作者帳號(事件當下快照)/ Actor username snapshot",
            ),
            sa.Column(
                "action",
                sa.String(length=50),
                nullable=False,
                comment="事件類型(login_success / schedule_create ...)/ Audit action",
            ),
            sa.Column(
                "target_type",
                sa.String(length=50),
                nullable=True,
                comment="目標物件類型(etl_table / schedule / etl_run ...)/ Target object type",
            ),
            sa.Column(
                "target_uid",
                PG_UUID(as_uuid=True),
                nullable=True,
                comment="目標物件對外識別碼 / Target object uid",
            ),
            sa.Column(
                "detail",
                sa.Text(),
                nullable=True,
                comment="事件摘要(繁中;禁任何密碼 / token 內容)/ Event summary (no secrets)",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_audit_logs_uid"),
            comment="稽核紀錄(登入成敗 / 設定變更 / 觸發足跡,append-only)/ Audit logs",
        )
    op.create_index(
        "idx_audit_logs_created_at", "audit_logs", ["created_at"], if_not_exists=True
    )
    op.create_index("idx_audit_logs_action", "audit_logs", ["action"], if_not_exists=True)


def downgrade() -> None:
    # 禁 DROP(CLAUDE.md 毀滅性操作禁止):稽核表 downgrade 一律不動,保留資料與結構
    pass
