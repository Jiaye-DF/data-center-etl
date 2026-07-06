"""v1.2.0 RDS 結構 metadata 快照表:rds_table_meta。

只建表建索引;downgrade 對稱刪除本次新建的表(僅撤銷自己新增內容,禁動既有表)。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v3"
down_revision: str | None = "v2"
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
    if not _has_table("rds_table_meta"):
        op.create_table(
            "rds_table_meta",
            *_base_columns(),
            sa.Column(
                "dataset",
                sa.String(length=20),
                nullable=False,
                comment="資料集(source=來源 RDS / target=目標 RDS)/ Dataset",
            ),
            sa.Column(
                "schema_name",
                sa.String(length=100),
                nullable=False,
                comment="schema 名稱 / Schema name",
            ),
            sa.Column(
                "table_name",
                sa.String(length=200),
                nullable=False,
                comment="表名稱 / Table name",
            ),
            sa.Column(
                "business_name",
                sa.String(length=200),
                nullable=True,
                comment=(
                    "業務資料名稱(中文,快照時 JOIN GAT_FILE 落地,由 task-002 寫入)"
                    "/ Business data name (snapshotted from GAT_FILE join)"
                ),
            ),
            sa.Column(
                "column_count",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="欄位數 / Column count",
            ),
            sa.Column(
                "row_count",
                sa.Integer(),
                server_default=sa.text("0"),
                nullable=False,
                comment="列數(bounded 探測,> 1000 存 1001,禁 COUNT(*))/ Row count (bounded probe)",
            ),
            sa.Column(
                "snapshot_at",
                sa.DateTime(),
                nullable=True,
                comment="此筆 metadata 擷取時間(UTC+8)/ Snapshot captured at (UTC+8)",
            ),
            sa.Column(
                "last_synced_at",
                sa.DateTime(),
                nullable=True,
                comment="最近從 RDS 同步到 hub 的時間(UTC+8)/ Last synced to hub at (UTC+8)",
            ),
            sa.Column(
                "last_transformed_at",
                sa.DateTime(),
                nullable=True,
                comment="最近套字典 COMMENT 的時間(UTC+8)/ Last transformed at (UTC+8)",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_rds_table_meta_uid"),
            sa.CheckConstraint(
                "dataset IN ('source', 'target')", name="ck_rds_table_meta_dataset"
            ),
            comment="RDS 結構 metadata 快照(欄位/列數/同步狀態)/ RDS structure metadata snapshot",
        )
    op.create_index(
        "uq_rds_table_meta_dataset_schema_table",
        "rds_table_meta",
        ["dataset", "schema_name", "table_name"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )


def downgrade() -> None:
    # 對稱刪除本次新建的表(禁 DROP 以外破壞;不動既有表,見 CLAUDE.md)
    if _has_table("rds_table_meta"):
        op.drop_table("rds_table_meta")
