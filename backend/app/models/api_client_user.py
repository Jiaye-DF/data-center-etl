from sqlalchemy import CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

CLIENT_STATUS_ENABLED = "enabled"
CLIENT_STATUS_DISABLED = "disabled"
CLIENT_STATUS_CHECK_SQL = "status IN ('enabled', 'disabled')"

DEFAULT_RATE_LIMIT_PER_MINUTE = 30
DEFAULT_RATE_LIMIT_PER_10MIN = 200


class ApiClientUser(BaseModel):
    """API Client 機器身分(對外資料供應;與後台 users / 角色體系完全分離)。"""

    __tablename__ = "api_client_users"

    client_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="取 token 識別碼 / Client identifier for token issuance",
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="應用系統名稱 / Application name"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="用途說明 / Usage description"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=CLIENT_STATUS_ENABLED,
        server_default=CLIENT_STATUS_ENABLED,
        comment="狀態(enabled / disabled)/ Status (enabled / disabled)",
    )
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_RATE_LIMIT_PER_MINUTE,
        server_default=text(str(DEFAULT_RATE_LIMIT_PER_MINUTE)),
        comment="每分鐘請求上限 / Request limit per minute",
    )
    rate_limit_per_10min: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_RATE_LIMIT_PER_10MIN,
        server_default=text(str(DEFAULT_RATE_LIMIT_PER_10MIN)),
        comment="每 10 分鐘請求上限 / Request limit per 10 minutes",
    )

    __table_args__ = (
        CheckConstraint(CLIENT_STATUS_CHECK_SQL, name="ck_api_client_users_status"),
        # 軟刪除後允許重建同 client_id → 以 partial unique index 取代一般 unique
        Index(
            "uq_api_client_users_client_id",
            "client_id",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
