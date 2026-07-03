from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EtlTable(BaseModel):
    """ETL 表設定:來源 schema/表 → 目標 schema/表 + 啟用狀態(source of truth 在自有 DB)。"""

    __tablename__ = "etl_tables"

    source_schema: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="來源 schema(如 DS)/ Source schema (e.g. DS)"
    )
    source_table: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="來源表名 / Source table name"
    )
    target_schema: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="目標 schema / Target schema"
    )
    target_table: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="目標表名 / Target table name"
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        comment="是否啟用(停用表不處理)/ Enabled flag (disabled tables are skipped)",
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="表用途描述 / Table description"
    )

    __table_args__ = (
        # 軟刪除後允許重建同來源表 → partial unique index
        Index(
            "uq_etl_tables_source",
            "source_schema",
            "source_table",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
