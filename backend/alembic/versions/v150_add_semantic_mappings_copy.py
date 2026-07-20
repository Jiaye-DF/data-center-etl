"""v1.5.0 語意映射副本表:semantic_mappings(task-003,propose A5)。

RDS `erp_metadata.semantic_mappings` 為唯一事實來源;本表為自有 DB 副本(單向同步,
不走 alembic 管理來源那張)。只建表建索引;downgrade 對稱刪除本次新建的表
(僅撤銷自己新增內容,禁動既有表;此 drop_table 為 CLAUDE.md 明定的 round-trip 必要例外)。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v150"
down_revision: str | None = "v7"
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
    if not _has_table("semantic_mappings"):
        op.create_table(
            "semantic_mappings",
            *_base_columns(),
            sa.Column(
                "table_name",
                sa.String(length=200),
                nullable=False,
                comment="ERP 表名 / ERP table name",
            ),
            sa.Column(
                "column_name",
                sa.String(length=200),
                nullable=False,
                server_default=sa.text("''"),
                comment=(
                    "ERP 欄名(空字串代表表層級映射)"
                    "/ ERP column name ('' = table-level mapping)"
                ),
            ),
            sa.Column(
                "english_name",
                sa.String(length=200),
                nullable=False,
                comment="英文語意名稱 / Semantic English name",
            ),
            sa.Column(
                "zh_name",
                sa.String(length=200),
                nullable=True,
                comment="中文語意名稱 / Semantic Chinese name",
            ),
            sa.Column(
                "status",
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'draft'"),
                comment="審核狀態(draft/confirmed)/ Review status (draft/confirmed)",
            ),
            sa.Column(
                "source_updated_by",
                sa.String(length=100),
                nullable=True,
                comment=(
                    "RDS 來源端 updated_by 原始文字(非本表審計者 updated_by)"
                    "/ Source-side updated_by (raw text, not this table's auditor)"
                ),
            ),
            sa.Column(
                "source_updated_at",
                sa.DateTime(),
                nullable=True,
                comment="RDS 來源端 updated_at(UTC+8)/ Source-side updated_at (UTC+8)",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_semantic_mappings_uid"),
            sa.CheckConstraint(
                "status IN ('draft', 'confirmed')", name="ck_semantic_mappings_status"
            ),
            comment=(
                "RDS 語意映射副本(單向同步,唯讀)"
                "/ Semantic mapping RDS mirror (one-way sync, read-only)"
            ),
        )
    op.create_index(
        "uq_semantic_mappings_table_name_column_name",
        "semantic_mappings",
        ["table_name", "column_name"],
        unique=True,
        if_not_exists=True,
    )


def downgrade() -> None:
    # 對稱刪除本次新建的表(禁 DROP 以外破壞;不動既有表,見 CLAUDE.md round-trip 例外)
    if _has_table("semantic_mappings"):
        op.drop_table("semantic_mappings")
