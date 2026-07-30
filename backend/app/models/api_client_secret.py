from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

SECRET_STATUS_ACTIVE = "active"
SECRET_STATUS_RETIRED = "retired"
SECRET_STATUS_CHECK_SQL = "status IN ('active', 'retired')"


class ApiClientSecret(BaseModel):
    """API Client 密鑰(雙鑰輪替:新鑰上線後舊鑰改 retired,不物理刪除)。"""

    __tablename__ = "api_client_secrets"

    api_client_user_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("api_client_users.pid", name="fk_api_client_secrets_api_client_user"),
        nullable=False,
        comment=(
            "所屬 API Client(api_client_users.pid)"
            "/ Parent API client (api_client_users.pid)"
        ),
    )
    # 只存不可逆雜湊(bcrypt),禁明文(比照 users.password_hash)
    secret_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="密鑰雜湊(bcrypt,禁明文)/ Secret hash (bcrypt only)",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=SECRET_STATUS_ACTIVE,
        server_default=SECRET_STATUS_ACTIVE,
        comment="狀態(active / retired)/ Status (active / retired)",
    )

    __table_args__ = (
        CheckConstraint(SECRET_STATUS_CHECK_SQL, name="ck_api_client_secrets_status"),
        Index("idx_api_client_secrets_api_client_user_pid", "api_client_user_pid"),
    )
