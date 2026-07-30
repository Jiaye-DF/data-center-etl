from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

SECRET_STATUS_ACTIVE = "active"
SECRET_STATUS_RETIRED = "retired"
SECRET_STATUS_CHECK_SQL = "status IN ('active', 'retired')"


class ApiClientSecret(BaseModel):
    """API Client 密鑰(單一密鑰制:同 client 恆一把 active,輪替即撤舊為 retired,不物理刪除)。"""

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
    # 驗證路徑用不可逆雜湊(bcrypt);明文檢視另走 secret_encrypted
    secret_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="密鑰雜湊(bcrypt,禁明文)/ Secret hash (bcrypt only)",
    )
    # user 裁定(2026-07-30):admin 需隨時檢視明文 → 額外存 Fernet 可逆加密值;
    # token 驗證仍只走 secret_hash。NULL = task-009 前核發的舊列,無明文可檢視。
    secret_encrypted: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "密鑰明文可逆加密(Fernet;NULL = 舊列無明文)"
            "/ Reversibly encrypted secret (Fernet; NULL = legacy row)"
        ),
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
        # 單一密鑰制 DB 兜底(AD-135):同 client 未刪除範圍恆最多一把 active
        Index(
            "uq_api_client_secrets_single_active",
            "api_client_user_pid",
            unique=True,
            postgresql_where=text("status = 'active' AND is_deleted = false"),
        ),
    )
