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
        comment="指定單表(NULL 為全部啟用表)/ Target ETL table (NULL = all enabled tables)",
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
    )
