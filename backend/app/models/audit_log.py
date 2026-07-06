from uuid import UUID

from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AuditLog(BaseModel):
    """稽核紀錄(append-only):登入成敗 / 設定變更 / 手動觸發等事件足跡。"""

    __tablename__ = "audit_logs"

    actor_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment=(
            "操作者(users.uid;登入失敗等匿名事件為 NULL)"
            "/ Actor (users.uid; NULL when anonymous)"
        ),
    )
    actor_username: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="操作者帳號(事件當下快照)/ Actor username snapshot",
    )
    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="事件類型(login_success / schedule_create ...)/ Audit action",
    )
    target_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="目標物件類型(etl_table / schedule / etl_run ...)/ Target object type",
    )
    target_uid: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="目標物件對外識別碼 / Target object uid",
    )
    detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="事件摘要(繁中;禁任何密碼 / token 內容)/ Event summary (no secrets)",
    )

    __table_args__ = (
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_action", "action"),
    )
