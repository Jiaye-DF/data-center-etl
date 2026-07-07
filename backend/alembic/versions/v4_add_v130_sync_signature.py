"""v1.3.0 增量同步基準 + 逐表排除旗標:rds_table_meta 加四欄。

新增 last_stat_ins/upd/del(來源 pg_stat_user_tables 計數器基準,供增量偵測)
與 sync_excluded(逐表排除增量同步旗標)。
upgrade 以欄位存在性 guard 可重入;downgrade 依 CLAUDE.md 禁 DROP COLUMN,前進式 no-op。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v4"
down_revision: str | None = "v3"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(col["name"] == column for col in columns)


def upgrade() -> None:
    if not _has_column("rds_table_meta", "last_stat_ins"):
        op.add_column(
            "rds_table_meta",
            sa.Column(
                "last_stat_ins",
                sa.BigInteger(),
                nullable=True,
                comment=(
                    "上次同步時來源 n_tup_ins 基準(NULL=尚無基準,視為變動)"
                    "/ Baseline n_tup_ins at last sync"
                ),
            ),
        )
    if not _has_column("rds_table_meta", "last_stat_upd"):
        op.add_column(
            "rds_table_meta",
            sa.Column(
                "last_stat_upd",
                sa.BigInteger(),
                nullable=True,
                comment=(
                    "上次同步時來源 n_tup_upd 基準(NULL=尚無基準,視為變動)"
                    "/ Baseline n_tup_upd at last sync"
                ),
            ),
        )
    if not _has_column("rds_table_meta", "last_stat_del"):
        op.add_column(
            "rds_table_meta",
            sa.Column(
                "last_stat_del",
                sa.BigInteger(),
                nullable=True,
                comment=(
                    "上次同步時來源 n_tup_del 基準(NULL=尚無基準,視為變動)"
                    "/ Baseline n_tup_del at last sync"
                ),
            ),
        )
    if not _has_column("rds_table_meta", "sync_excluded"):
        op.add_column(
            "rds_table_meta",
            sa.Column(
                "sync_excluded",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
                comment=(
                    "逐表排除增量同步旗標(true=排除;false=納入,預設納入)"
                    "/ Exclude table from incremental sync"
                ),
            ),
        )


def downgrade() -> None:
    # 依 CLAUDE.md 禁 DROP COLUMN,欄位保留;upgrade 以欄位存在性 guard 可重入。
    # 本次未新增 index/constraint,故 downgrade 為安全 no-op(前進式)。
    pass
