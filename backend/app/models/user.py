from sqlalchemy import CheckConstraint, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class User(BaseModel):
    """使用者(本地帳密 + 角色;SSO 使用者以 sso_subject 對應,無本地密碼)。"""

    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="登入帳號 / Login username"
    )
    # 顯示名稱:SSO 使用者取中央回傳之 name(僅供顯示,非授權依據);本地帳號可為 NULL
    display_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="顯示名稱(SSO 姓名)/ Display name"
    )
    # 只存不可逆雜湊(bcrypt),禁明文;SSO-only 使用者可為 NULL(登入邏輯屬 task-002)
    password_hash: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="密碼雜湊(bcrypt,禁明文)/ Password hash (bcrypt only)"
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="viewer",
        server_default="viewer",
        comment="角色(admin/viewer)/ Role (admin/viewer)",
    )
    sso_subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="DF-SSO 對外識別碼(獨立欄位,禁作主鍵)/ DF-SSO external subject id",
    )

    __table_args__ = (
        CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
        # 軟刪除後允許重建同帳號 → 以 partial unique index 取代一般 unique
        Index(
            "uq_users_username",
            "username",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_users_sso_subject",
            "sso_subject",
            unique=True,
            postgresql_where=text("is_deleted = false AND sso_subject IS NOT NULL"),
        ),
    )
