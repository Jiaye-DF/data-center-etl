from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Schedule(BaseModel):
    """排程定義:cron 式時程 + 啟停;可指定單一 ETL 表或全部啟用表。"""

    __tablename__ = "schedules"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="排程名稱 / Schedule name"
    )
    cron_expr: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="cron 運算式(Asia/Taipei)/ Cron expression (Asia/Taipei)",
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        comment="是否啟用 / Enabled flag",
    )
    etl_table_pid: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("etl_tables.pid", name="fk_schedules_etl_table"),
        nullable=True,
        comment=(
            "指定單表(NULL 為全部啟用表)/ Target ETL table (NULL = all enabled tables)"
            "(deprecated:v1.3.1 起不使用,保留欄位待人工移除)"
        ),
    )
    source_schema: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment=(
            "來源表 schema(對應 rds_table_meta.schema_name)"
            "/ Source table schema (maps to rds_table_meta)"
        ),
    )
    source_table: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment=(
            "來源表名稱(對應 rds_table_meta.table_name)"
            "/ Source table name (maps to rds_table_meta)"
        ),
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="排程描述 / Schedule description"
    )

    __table_args__ = (
        # 軟刪除後允許重建同名排程 → partial unique index
        Index(
            "uq_schedules_name",
            "name",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        # v1.3.1 一表一排程:未刪除範圍內來源表唯一 → partial unique index
        Index(
            "uq_schedules_source_table",
            "source_schema",
            "source_table",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
