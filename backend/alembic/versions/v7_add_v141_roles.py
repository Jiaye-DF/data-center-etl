"""v1.4.1:roles 表(角色唯一事實來源)+ users.role_pid 關聯,同一 migration 內完成
建表 → seed(admin/viewer)→ users 加欄 → backfill,避免「有 user 無角色」中間態。

既有 users.role 字串欄位與 ck_users_role 約束原樣保留、標記 deprecated(人工移除步驟
見 docs/Tasks/v1.4.1/manual-removal-checklist.md)。

role_pid 暫**不**收 NOT NULL:建立使用者的唯一入口 UserRepository.create()
(task-002 才會改寫入 role_pid)不在本 task 檔白名單內,若此刻收 NOT NULL,
task-002 落地前所有新建使用者(本地帳密 / SSO 首次登入 / init admin)都會因
role_pid 違反 NOT NULL 而 500;既有 pytest 也會因 create_all 建出的測試 schema
同步套用 NOT NULL 而集體回歸失敗。偏離原規格文字,詳見 fixed.md。

upgrade 以存在性 guard 可重入(失敗可重跑);downgrade 依 CLAUDE.md 禁 DROP,no-op。
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "v7"
down_revision: str | None = "v6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# 同 app/services/audit_service.py 的 SYSTEM_ACTOR_UID 約定(migration 獨立於 app 模組,重複常數)
_SYSTEM_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")

_BUILTIN_ROLES = (
    # (code, name, description, uid)
    ("admin", "管理員", "系統管理員,擁有全部管理權限", UUID("00000000-0000-0000-0000-0000000000a1")),
    ("viewer", "檢視者", "唯讀檢視權限", UUID("00000000-0000-0000-0000-0000000000a2")),
)


def _base_columns() -> list[sa.Column]:
    """BaseModel 必備欄位(pid / uid / is_deleted / created_at / updated_at / created_by / updated_by)。"""
    return [
        sa.Column(
            "pid",
            sa.BigInteger(),
            autoincrement=True,
            nullable=False,
            comment="內部主鍵(禁對外)/ Internal primary key (never exposed)",
        ),
        sa.Column(
            "uid",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="對外識別碼(UUID)/ External unique identifier (UUID)",
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
            comment="軟刪除旗標 / Soft-delete flag",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="建立時間(UTC+8)/ Created at (UTC+8)",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
            comment="更新時間(UTC+8)/ Updated at (UTC+8)",
        ),
        sa.Column(
            "created_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="建立者(users.uid;系統動作為系統帳號)/ Created by (users.uid)",
        ),
        sa.Column(
            "updated_by",
            PG_UUID(as_uuid=True),
            nullable=False,
            comment="最後更新者(users.uid;系統動作為系統帳號)/ Updated by (users.uid)",
        ),
    ]


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    columns = sa.inspect(op.get_bind()).get_columns(table)
    return any(col["name"] == column for col in columns)


def _has_foreign_key(table: str, name: str) -> bool:
    fks = sa.inspect(op.get_bind()).get_foreign_keys(table)
    return any(fk["name"] == name for fk in fks)


def upgrade() -> None:
    bind = op.get_bind()

    # ── roles ──────────────────────────────────────────────
    if not _has_table("roles"):
        op.create_table(
            "roles",
            *_base_columns(),
            sa.Column(
                "code", sa.String(length=50), nullable=False, comment="角色代碼(唯一)/ Role code (unique)"
            ),
            sa.Column(
                "name", sa.String(length=100), nullable=False, comment="顯示名稱 / Display name"
            ),
            sa.Column("description", sa.Text(), nullable=True, comment="描述 / Description"),
            sa.Column(
                "is_builtin",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
                comment="系統內建標記(禁刪 / 禁改代碼)/ Built-in flag (no delete / no rename)",
            ),
            sa.PrimaryKeyConstraint("pid"),
            sa.UniqueConstraint("uid", name="uq_roles_uid"),
            comment="角色(角色唯一事實來源)/ Roles (single source of truth for roles)",
        )
    op.create_index(
        "uq_roles_code",
        "roles",
        ["code"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false"),
        if_not_exists=True,
    )

    # ── seed 內建角色(idempotent:code 已存在即略過)──────────
    roles_table = sa.table(
        "roles",
        sa.column("uid", PG_UUID(as_uuid=True)),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_builtin", sa.Boolean()),
        sa.column("created_by", PG_UUID(as_uuid=True)),
        sa.column("updated_by", PG_UUID(as_uuid=True)),
    )
    for code, name, description, seed_uid in _BUILTIN_ROLES:
        exists = bind.execute(
            sa.text("SELECT 1 FROM roles WHERE code = :code AND is_deleted = false"),
            {"code": code},
        ).scalar()
        if exists is None:
            bind.execute(
                roles_table.insert().values(
                    uid=seed_uid,
                    code=code,
                    name=name,
                    description=description,
                    is_builtin=True,
                    created_by=_SYSTEM_ACTOR_UID,
                    updated_by=_SYSTEM_ACTOR_UID,
                )
            )

    # ── users.role_pid(nullable;理由見檔頭 docstring / fixed.md)────
    if not _has_column("users", "role_pid"):
        op.add_column(
            "users",
            sa.Column(
                "role_pid",
                sa.BigInteger(),
                nullable=True,
                comment=(
                    "角色(roles.pid;v1.4.1 起 source of truth,建立/指派寫入邏輯屬 task-002/003,"
                    "落地前暫不收 NOT NULL)/ Role (roles.pid; source of truth, not yet NOT NULL)"
                ),
            ),
        )
    if not _has_foreign_key("users", "fk_users_role"):
        op.create_foreign_key("fk_users_role", "users", "roles", ["role_pid"], ["pid"])
    op.create_index("idx_users_role_pid", "users", ["role_pid"], if_not_exists=True)

    # ── backfill:依現行 users.role 字串值對應 roles.code(僅補未設值列,重跑安全)─
    bind.execute(
        sa.text(
            "UPDATE users SET role_pid = roles.pid "
            "FROM roles "
            "WHERE users.role_pid IS NULL "
            "AND roles.code = users.role "
            "AND roles.is_deleted = false"
        )
    )


def downgrade() -> None:
    # 依 CLAUDE.md 禁 DROP:roles 表 / users.role_pid 欄位、索引、外鍵皆保留;
    # upgrade 以存在性 guard 可重入,round-trip 安全。
    pass
