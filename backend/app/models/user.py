from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel
from app.models.role import Role


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
        comment=(
            "角色字串(deprecated:v1.4.1 起 source of truth 改為 role_pid → roles 表,"
            "本欄保留供相容,人工移除步驟見 docs/Tasks/v1.4.1/manual-removal-checklist.md)"
            "/ Role string (deprecated; superseded by role_pid → roles table)"
        ),
    )
    # v1.4.1 起 source of truth;建立(task-002)/ 指派(task-003)寫入邏輯已落地,
    # DB 端已由 v8 migration 收 NOT NULL,model 端同步收緊(fixed.md §3 後續)
    role_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("roles.pid", name="fk_users_role"),
        nullable=False,
        comment=(
            "角色(roles.pid;v1.4.1 起 source of truth)"
            "/ Role (roles.pid; source of truth from v1.4.1)"
        ),
    )
    sso_subject: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="DF-SSO 對外識別碼(獨立欄位,禁作主鍵)/ DF-SSO external subject id",
    )

    # lazy="joined":async session 下避免隱式 lazy load(MissingGreenlet),
    # role_pid 又是每次授權判斷都需要的高頻欄位,直接併入主查詢的 JOIN
    role_ref: Mapped[Role | None] = relationship(Role, lazy="joined")

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
        Index("idx_users_role_pid", "role_pid"),
    )
