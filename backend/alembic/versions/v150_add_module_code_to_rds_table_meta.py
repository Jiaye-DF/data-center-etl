"""v1.5.0 B2 資料集頁模組分類:rds_table_meta 加 module_code(task-007,propose B2)。

快照內省時批量查 `DS.GAT_FILE.GAT06`(ERP 模組代碼,繁優先缺退簡)落地本欄,
供 datasets API 依模組分類/篩選。upgrade 以欄位存在性 guard 可重入;downgrade
drop_column 為本次新增欄位的 round-trip 必要例外(CLAUDE.md 明定),僅撤銷本次新增內容。
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "v151"
down_revision: str | None = "v150"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(col["name"] == column for col in columns)


def upgrade() -> None:
    if not _has_column("rds_table_meta", "module_code"):
        op.add_column(
            "rds_table_meta",
            sa.Column(
                "module_code",
                sa.Text(),
                nullable=True,
                comment=(
                    "ERP 模組代碼(GAT_FILE.GAT06,快照時 JOIN 落地;字典缺對應為 null)"
                    "/ ERP module code (GAT_FILE.GAT06; null if dictionary has no match)"
                ),
            ),
        )


def downgrade() -> None:
    # 對稱刪除本次新增欄位(round-trip 必要例外,僅撤銷本次新增內容;不動其他既有欄位)
    if _has_column("rds_table_meta", "module_code"):
        op.drop_column("rds_table_meta", "module_code")
