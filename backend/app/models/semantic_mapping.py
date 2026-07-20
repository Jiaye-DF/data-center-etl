from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class SemanticMapping(BaseModel):
    """RDS `erp_metadata.semantic_mappings` 單向同步副本(task-003,propose A5)。

    RDS 端為唯一事實來源;本表由 ETL 同步 job 末端整表重灌(DELETE + bulk INSERT,
    單交易),供 API / view 讀取(同 `rds_table_meta` 快照模式,不即時打 RDS)。
    **禁雙向同步**:本表不提供任何寫入 API。
    """

    __tablename__ = "semantic_mappings"

    table_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="ERP 表名 / ERP table name"
    )
    column_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        default="",
        server_default=text("''"),
        comment=(
            "ERP 欄名(空字串代表表層級映射)"
            "/ ERP column name ('' = table-level mapping)"
        ),
    )
    english_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="英文語意名稱 / Semantic English name"
    )
    zh_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="中文語意名稱 / Semantic Chinese name"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="draft",
        server_default=text("'draft'"),
        comment="審核狀態(draft/confirmed)/ Review status (draft/confirmed)",
    )
    source_updated_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment=(
            "RDS 來源端 updated_by 原始文字(非本表審計者 updated_by)"
            "/ Source-side updated_by (raw text, not this table's auditor)"
        ),
    )
    source_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="RDS 來源端 updated_at(UTC+8)/ Source-side updated_at (UTC+8)",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'confirmed')", name="ck_semantic_mappings_status"
        ),
        Index(
            "uq_semantic_mappings_table_name_column_name",
            "table_name",
            "column_name",
            unique=True,
        ),
    )
