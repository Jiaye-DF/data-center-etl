"""v1.3.1 一表一排程:schedules 加 source_schema / source_table + partial unique index。

新增 source_schema / source_table(對應 rds_table_meta 來源表),
建立 partial unique index uq_schedules_source_table(未刪除範圍內來源表唯一)。
etl_table_pid 標記 deprecated 但保留欄位。
upgrade 以欄位存在性 guard 可重入;downgrade 依 CLAUDE.md 禁 DROP COLUMN,前進式僅 drop_index。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v5"
down_revision: str | None = "v4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(col["name"] == column for col in columns)


def upgrade() -> None:
    if not _has_column("schedules", "source_schema"):
        op.add_column(
            "schedules",
            sa.Column(
                "source_schema",
                sa.String(length=100),
                nullable=True,
                comment=(
                    "來源表 schema(對應 rds_table_meta.schema_name)"
                    "/ Source table schema (maps to rds_table_meta)"
                ),
            ),
        )
    if not _has_column("schedules", "source_table"):
        op.add_column(
            "schedules",
            sa.Column(
                "source_table",
                sa.String(length=200),
                nullable=True,
                comment=(
                    "來源表名稱(對應 rds_table_meta.table_name)"
                    "/ Source table name (maps to rds_table_meta)"
                ),
            ),
        )
    op.create_index(
        "uq_schedules_source_table",
        "schedules",
        ["source_schema", "source_table"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )


def downgrade() -> None:
    # 依 CLAUDE.md 禁 DROP COLUMN,source_schema / source_table 欄位保留;
    # 前進式僅移除本次新增之 index(guard 存在性),upgrade 以欄位存在性 guard 可重入。
    op.drop_index(
        "uq_schedules_source_table",
        table_name="schedules",
        if_exists=True,
    )
