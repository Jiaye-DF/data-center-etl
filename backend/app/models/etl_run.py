from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EtlRun(BaseModel):
    """ETL 執行紀錄(一次執行):觸發方式 / 起訖時間 / 狀態 / 整體錯誤與逐表統計。"""

    __tablename__ = "etl_runs"

    trigger_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="觸發方式(schedule/manual)/ Trigger type (schedule/manual)",
    )
    schedule_pid: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("schedules.pid", name="fk_etl_runs_schedule"),
        nullable=True,
        comment="來源排程(手動觸發為 NULL)/ Source schedule (NULL when manual)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="執行狀態(pending/running/success/partial/failed)/ Run status",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, comment="開始時間(UTC+8)/ Started at (UTC+8)"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, comment="結束時間(UTC+8)/ Finished at (UTC+8)"
    )
    total_tables: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="處理表總數 / Total tables processed",
    )
    success_tables: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="成功表數 / Succeeded tables",
    )
    failed_tables: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
        comment="失敗表數 / Failed tables",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="整體錯誤訊息 / Overall error message"
    )

    __table_args__ = (
        CheckConstraint(
            "trigger_type IN ('schedule', 'manual')", name="ck_etl_runs_trigger_type"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'partial', 'failed')",
            name="ck_etl_runs_status",
        ),
        Index("idx_etl_runs_status", "status"),
        Index("idx_etl_runs_started_at", "started_at"),
    )
