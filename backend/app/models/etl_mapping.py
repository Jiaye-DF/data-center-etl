from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EtlMapping(BaseModel):
    """ETL 欄位對照:來源欄 → 目標欄 + 型別轉換 + 欄位 Comment(供 COMMENT ON COLUMN)。"""

    __tablename__ = "etl_mappings"

    etl_table_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("etl_tables.pid", name="fk_etl_mappings_etl_table"),
        nullable=False,
        comment="所屬 ETL 表(etl_tables.pid)/ Parent ETL table (etl_tables.pid)",
    )
    source_column: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="來源欄名 / Source column name"
    )
    target_column: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="目標欄名 / Target column name"
    )
    transform_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="型別轉換規則(str/int/float,NULL 為不轉換)/ Transform rule (str/int/float)",
    )
    comment: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="欄位說明(產生 COMMENT ON COLUMN,契約非空)/ Column comment (must be non-empty)",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="欄位排序 / Column sort order",
    )

    __table_args__ = (
        # 同一 ETL 表內目標欄唯一(軟刪除後可重建)
        Index(
            "uq_etl_mappings_table_target",
            "etl_table_pid",
            "target_column",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("idx_etl_mappings_etl_table_pid", "etl_table_pid"),
    )
