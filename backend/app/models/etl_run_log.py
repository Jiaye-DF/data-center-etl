from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EtlRunLog(BaseModel):
    """ETL 逐表明細 log:每表一筆(筆數 / 耗時 / 狀態 / 錯誤含 stack trace)。"""

    __tablename__ = "etl_run_logs"

    etl_run_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("etl_runs.pid", name="fk_etl_run_logs_etl_run"),
        nullable=False,
        comment="所屬執行(etl_runs.pid)/ Parent run (etl_runs.pid)",
    )
    etl_table_pid: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("etl_tables.pid", name="fk_etl_run_logs_etl_table"),
        nullable=True,
        comment="對應 ETL 表(設定被刪時保留 log 為 NULL)/ ETL table ref (nullable)",
    )
    source_schema: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="來源 schema(執行當下快照)/ Source schema snapshot",
    )
    source_table: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="來源表名(執行當下快照)/ Source table snapshot",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        comment="逐表狀態(pending/running/success/failed/skipped)/ Per-table status",
    )
    row_count: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="處理筆數 / Rows processed"
    )
    duration_ms: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, comment="耗時(毫秒)/ Duration in milliseconds"
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, comment="開始時間(UTC+8)/ Started at (UTC+8)"
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True, comment="結束時間(UTC+8)/ Finished at (UTC+8)"
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="錯誤訊息 / Error message"
    )
    error_stack: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="錯誤 stack trace / Error stack trace"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped')",
            name="ck_etl_run_logs_status",
        ),
        Index("idx_etl_run_logs_etl_run_pid", "etl_run_pid"),
        Index("idx_etl_run_logs_etl_table_pid", "etl_table_pid"),
    )
