from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class Role(BaseModel):
    """角色(角色唯一事實來源):code 唯一,is_builtin 標記系統內建角色
    (禁刪、禁改代碼 — 本版無角色 CRUD,此欄為未來 enforcement 地基)。"""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="角色代碼(唯一)/ Role code (unique)"
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="顯示名稱 / Display name"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="描述 / Description"
    )
    is_builtin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="系統內建標記(禁刪 / 禁改代碼)/ Built-in flag (no delete / no rename)",
    )

    __table_args__ = (
        # 軟刪除後允許重建同代碼 → partial unique index(對齊 users.username 前例)
        Index(
            "uq_roles_code",
            "code",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
    )
