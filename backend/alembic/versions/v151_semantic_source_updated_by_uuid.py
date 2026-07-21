"""v1.5.1 fixed #3:semantic_mappings 副本 source_updated_by 由 String 轉 UUID。

對齊 `04-databases/00-overview.md` 必備欄位型別約束(updated_by 族 UUID);
RDS 真身端同步由 `ensure_semantic_schema` 冪等轉型。既有非 UUID 文字(工具標記等)
轉 NULL 即可 — 本表為單向重灌副本,下一輪同步會以 RDS 真身(已轉 UUID)全量覆蓋。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "v152"
down_revision: str | None = "v151"
branch_labels: str | None = None
depends_on: str | None = None

_UUID_REGEX = "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


def upgrade() -> None:
    op.execute(
        sa.text(
            f"""
            ALTER TABLE semantic_mappings
                ALTER COLUMN source_updated_by TYPE uuid
                    USING (CASE
                        WHEN source_updated_by ~ '{_UUID_REGEX}'
                            THEN source_updated_by::uuid
                        ELSE NULL
                    END)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "ALTER TABLE semantic_mappings"
            " ALTER COLUMN source_updated_by TYPE VARCHAR(100)"
            " USING (source_updated_by::text)"
        )
    )
