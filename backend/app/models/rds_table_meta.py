from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Dataset(StrEnum):
    """RDS metadata 快照所屬資料集(來源 RDS / 目標 RDS)。"""

    SOURCE = "source"
    TARGET = "target"


class RdsTableMeta(BaseModel):
    """RDS 結構 metadata 快照:每筆代表 dataset+schema+table 的結構與同步狀態,
    供瀏覽頁改讀快照(禁即時 COUNT(*))、同步鏈記錄各階段時間。"""

    __tablename__ = "rds_table_meta"

    dataset: Mapped[Dataset] = mapped_column(
        String(20), nullable=False, comment="資料集(source=來源 RDS / target=目標 RDS)/ Dataset"
    )
    schema_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="schema 名稱 / Schema name"
    )
    table_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="表名稱 / Table name"
    )
    business_name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment=(
            "業務資料名稱(中文,快照時 JOIN GAT_FILE 落地,由 task-002 寫入)"
            "/ Business data name (snapshotted from GAT_FILE join)"
        ),
    )
    column_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="欄位數 / Column count",
    )
    row_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="列數(bounded 探測,> 1000 存 1001,禁 COUNT(*))/ Row count (bounded probe)",
    )
    snapshot_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="此筆 metadata 擷取時間(UTC+8)/ Snapshot captured at (UTC+8)",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="最近從 RDS 同步到 hub 的時間(UTC+8)/ Last synced to hub at (UTC+8)",
    )
    last_transformed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="最近套字典 COMMENT 的時間(UTC+8)/ Last transformed (comment applied) at (UTC+8)",
    )
    last_stat_ins: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment=(
            "上次同步時來源 n_tup_ins 基準(NULL=尚無基準,視為變動)"
            "/ Baseline n_tup_ins at last sync"
        ),
    )
    last_stat_upd: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment=(
            "上次同步時來源 n_tup_upd 基準(NULL=尚無基準,視為變動)"
            "/ Baseline n_tup_upd at last sync"
        ),
    )
    last_stat_del: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
        comment=(
            "上次同步時來源 n_tup_del 基準(NULL=尚無基準,視為變動)"
            "/ Baseline n_tup_del at last sync"
        ),
    )
    sync_excluded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment=(
            "逐表排除增量同步旗標(true=排除;false=納入,預設納入)"
            "/ Exclude table from incremental sync"
        ),
    )

    __table_args__ = (
        CheckConstraint(
            "dataset IN ('source', 'target')", name="ck_rds_table_meta_dataset"
        ),
        # 軟刪除後允許同 dataset+schema+table 重建快照 → partial unique index(供 upsert)
        Index(
            "uq_rds_table_meta_dataset_schema_table",
            "dataset",
            "schema_name",
            "table_name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
