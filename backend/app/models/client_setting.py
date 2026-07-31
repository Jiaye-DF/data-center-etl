"""RDS ETL-Hub `client_setting` schema 權限階層 ORM models(v1.6.1 task-001)。

權限設定是「給多台機器共讀的資料交換面」,唯一真身在 **RDS ETL-Hub** 的專用 schema
`client_setting`(propose v1.6.1 決策記錄);自有 DB 不新增任何權限表、不建本地副本。
表結構的建置由 `app.etl.client_setting_schema` 以冪等 DDL 負責(不走 alembic)。

**why 另立 `ClientSettingBase`**:自有 DB 的 `app.core.db.Base` 其 metadata 會被
`Base.metadata.create_all`(測試 conftest)與 alembic autogenerate 掃到;若共用同一個
metadata,這 12 張 RDS 表會被一併建進自有 DB,違反「自有 DB 不新增權限表」。故本模組
使用獨立的 declarative base 與獨立 metadata,與自有 DB 完全隔離。

跨庫關聯:API Client 本體(`api_client_users`)在自有 DB,RDS 端一律以 `api_client_uid`
(UUID)冷關聯,**不建跨庫 FK**。

時間欄位:一律 naive `timestamp` 存 UTC+8(`04-databases/06-timezone.md`,RDS 端
datetime2 等價慣例),禁 timestamptz;DB 端 DEFAULT 由 DDL 以
`now() AT TIME ZONE 'Asia/Taipei'` 轉出本地 naive 值。
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

CLIENT_SETTING_SCHEMA = "client_setting"

# 權限項動作:edit = 新增 / 更新 / 刪除(刪除一律軟刪除)
ACTION_READ = "read"
ACTION_EDIT = "edit"
ACTION_CHECK_SQL = "action IN ('read', 'edit')"

# 權限項的欄位萬用值:代表該表全欄位
ALL_COLUMNS = "*"

# 審計欄位無值時的系統帳號(對齊 semantic_mappings 前例)
ZERO_UUID = "00000000-0000-0000-0000-000000000000"

_SOFT_DELETE_WHERE = text("is_deleted = false")

# 12 張權限表(FK 依賴由淺至深;測試清理 / 批次操作依此反序處理子表在先)
CLIENT_SETTING_TABLES: tuple[str, ...] = (
    "services",
    "operations",
    "operation_items",
    "permission_profiles",
    "profile_operations",
    "profile_items",
    "roles",
    "client_roles",
    "exception_sets",
    "exception_operations",
    "exception_items",
    "client_exception_sets",
)


class ClientSettingBase(DeclarativeBase):
    """RDS `client_setting` 專用 declarative base(獨立 metadata,與自有 DB 隔離)。"""


def _uid_column(column_name: str) -> Mapped[UUID]:
    """對外識別碼欄位:Python 屬性統一為 `uid`,DB 欄名依 ERD 為 `<table>_uid`。"""
    return mapped_column(
        column_name,
        PG_UUID(as_uuid=True),
        nullable=False,
        unique=True,
        default=uuid4,
        comment="對外識別碼 / External identifier",
    )


class ClientSettingBaseModel(ClientSettingBase):
    """BaseModel 共通欄位(`04-databases/00-overview.md`);`uid` 由各表自行宣告欄名。"""

    __abstract__ = True

    pid: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="內部主鍵(禁對外暴露)/ Internal primary key (never exposed)",
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="軟刪除旗標 / Soft delete flag",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("(now() AT TIME ZONE 'Asia/Taipei')"),
        comment="建立時間(UTC+8)/ Created at (UTC+8)",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=text("(now() AT TIME ZONE 'Asia/Taipei')"),
        comment="更新時間(UTC+8)/ Updated at (UTC+8)",
    )
    created_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text(f"'{ZERO_UUID}'"),
        comment="建立者 / Created by",
    )
    updated_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        server_default=text(f"'{ZERO_UUID}'"),
        comment="最後更新者 / Updated by",
    )


class Service(ClientSettingBaseModel):
    """系統別:作業的分類容器,對應資料 API 路由 `{service}` 分段。"""

    __tablename__ = "services"

    uid: Mapped[UUID] = _uid_column("service_uid")
    code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="系統別代碼(erp / crm / hrm…)/ Service code",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="系統別名稱 / Service name"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="說明 / Description"
    )

    __table_args__ = (
        Index(
            "uq_services_code",
            "code",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class Operation(ClientSettingBaseModel):
    """作業:查詢入口,歸屬一個系統別;範圍由 `operation_items` 定義。"""

    __tablename__ = "operations"

    uid: Mapped[UUID] = _uid_column("operation_uid")
    service_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{CLIENT_SETTING_SCHEMA}.services.pid", name="fk_operations_service"),
        nullable=False,
        comment="歸屬系統別 / Owning service",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="作業名(系統別內唯一)/ Operation name"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="業務動作說明 / Description"
    )

    __table_args__ = (
        Index("idx_operations_service_pid", "service_pid"),
        Index(
            "uq_operations_service_pid_name",
            "service_pid",
            "name",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class OperationItem(ClientSettingBaseModel):
    """作業範圍項:一筆 = 作業涵蓋的某表某欄位(`*` = 全欄位)。"""

    __tablename__ = "operation_items"

    uid: Mapped[UUID] = _uid_column("operation_item_uid")
    operation_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.operations.pid", name="fk_operation_items_operation"
        ),
        nullable=False,
        comment="歸屬作業 / Owning operation",
    )
    table_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="資料表(語意層英文名)/ Table (semantic name)"
    )
    column_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="欄位(`*` = 全欄位)/ Column ('*' = all columns)",
    )

    __table_args__ = (
        Index("idx_operation_items_operation_pid", "operation_pid"),
        Index(
            "uq_operation_items_operation_table_column",
            "operation_pid",
            "table_name",
            "column_name",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class PermissionProfile(ClientSettingBaseModel):
    """角色權限設定檔:常規授權的內容載體,被 Role 綁定。"""

    __tablename__ = "permission_profiles"

    uid: Mapped[UUID] = _uid_column("permission_profile_uid")
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="設定檔名(唯一)/ Profile name (unique)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="說明 / Description"
    )

    __table_args__ = (
        Index(
            "uq_permission_profiles_name",
            "name",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ProfileOperation(ClientSettingBaseModel):
    """設定檔勾選的可讀作業(作業開門;實際欄位授權見 `profile_items`)。"""

    __tablename__ = "profile_operations"

    uid: Mapped[UUID] = _uid_column("profile_operation_uid")
    permission_profile_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.permission_profiles.pid",
            name="fk_profile_operations_permission_profile",
        ),
        nullable=False,
        comment="歸屬設定檔 / Owning profile",
    )
    operation_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.operations.pid", name="fk_profile_operations_operation"
        ),
        nullable=False,
        comment="勾選的作業 / Granted operation",
    )

    __table_args__ = (
        Index("idx_profile_operations_permission_profile_pid", "permission_profile_pid"),
        Index("idx_profile_operations_operation_pid", "operation_pid"),
        Index(
            "uq_profile_operations_profile_operation",
            "permission_profile_pid",
            "operation_pid",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ProfileItem(ClientSettingBaseModel):
    """設定檔權限項:一筆 = 某作業下某表某欄位 + 動作(read / edit)。"""

    __tablename__ = "profile_items"

    uid: Mapped[UUID] = _uid_column("profile_item_uid")
    permission_profile_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.permission_profiles.pid",
            name="fk_profile_items_permission_profile",
        ),
        nullable=False,
        comment="歸屬設定檔 / Owning profile",
    )
    operation_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.operations.pid", name="fk_profile_items_operation"
        ),
        nullable=False,
        comment="歸屬作業(授權巢狀在作業下)/ Owning operation",
    )
    table_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="資料表(語意層英文名)/ Table (semantic name)"
    )
    column_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="授權欄位(`*` = 全欄位)/ Granted column ('*' = all columns)",
    )
    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="動作(read / edit)/ Action (read / edit)",
    )

    __table_args__ = (
        CheckConstraint(ACTION_CHECK_SQL, name="ck_profile_items_action"),
        Index("idx_profile_items_permission_profile_pid", "permission_profile_pid"),
        Index("idx_profile_items_operation_pid", "operation_pid"),
        Index(
            "uq_profile_items_profile_operation_table_column_action",
            "permission_profile_pid",
            "operation_pid",
            "table_name",
            "column_name",
            "action",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class Role(ClientSettingBaseModel):
    """Role:名字與指派的載體,**必綁 1 個設定檔**(DB 層 NOT NULL 禁空角色)。"""

    __tablename__ = "roles"

    uid: Mapped[UUID] = _uid_column("role_uid")
    permission_profile_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.permission_profiles.pid",
            name="fk_roles_permission_profile",
        ),
        nullable=False,
        comment="綁定的設定檔(必綁)/ Bound profile (mandatory)",
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="角色名(唯一)/ Role name (unique)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="說明 / Description"
    )

    __table_args__ = (
        Index("idx_roles_permission_profile_pid", "permission_profile_pid"),
        Index(
            "uq_roles_name",
            "name",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ClientRole(ClientSettingBaseModel):
    """API Client 的 Role 指派(0..1;未刪列以 `api_client_uid` partial unique 保證)。"""

    __tablename__ = "client_roles"

    uid: Mapped[UUID] = _uid_column("client_role_uid")
    api_client_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment=(
            "API Client 對外識別碼(跨庫冷關聯,本體在自有 DB,無 FK)"
            "/ API client UID (cross-database soft reference, no FK)"
        ),
    )
    role_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{CLIENT_SETTING_SCHEMA}.roles.pid", name="fk_client_roles_role"),
        nullable=False,
        comment="指派的 Role / Assigned role",
    )

    __table_args__ = (
        Index("idx_client_roles_role_pid", "role_pid"),
        Index(
            "uq_client_roles_api_client_uid",
            "api_client_uid",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ExceptionSet(ClientSettingBaseModel):
    """特例權限組:結構同設定檔,可重用(同一組可綁多個 Client、各自效期)。"""

    __tablename__ = "exception_sets"

    uid: Mapped[UUID] = _uid_column("exception_set_uid")
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="特例權限名(唯一)/ Exception set name (unique)"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="臨時分派用說明 / Description"
    )

    __table_args__ = (
        Index(
            "uq_exception_sets_name",
            "name",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ExceptionOperation(ClientSettingBaseModel):
    """特例組勾選的作業(結構同 `profile_operations`)。"""

    __tablename__ = "exception_operations"

    uid: Mapped[UUID] = _uid_column("exception_operation_uid")
    exception_set_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.exception_sets.pid",
            name="fk_exception_operations_exception_set",
        ),
        nullable=False,
        comment="歸屬特例組 / Owning exception set",
    )
    operation_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.operations.pid", name="fk_exception_operations_operation"
        ),
        nullable=False,
        comment="勾選的作業 / Granted operation",
    )

    __table_args__ = (
        Index("idx_exception_operations_exception_set_pid", "exception_set_pid"),
        Index("idx_exception_operations_operation_pid", "operation_pid"),
        Index(
            "uq_exception_operations_set_operation",
            "exception_set_pid",
            "operation_pid",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ExceptionItem(ClientSettingBaseModel):
    """特例組權限項(結構同 `profile_items`)。"""

    __tablename__ = "exception_items"

    uid: Mapped[UUID] = _uid_column("exception_item_uid")
    exception_set_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.exception_sets.pid",
            name="fk_exception_items_exception_set",
        ),
        nullable=False,
        comment="歸屬特例組 / Owning exception set",
    )
    operation_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.operations.pid", name="fk_exception_items_operation"
        ),
        nullable=False,
        comment="歸屬作業 / Owning operation",
    )
    table_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="資料表(語意層英文名)/ Table (semantic name)"
    )
    column_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="授權欄位(`*` = 全欄位)/ Granted column ('*' = all columns)",
    )
    action: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="動作(read / edit)/ Action (read / edit)",
    )

    __table_args__ = (
        CheckConstraint(ACTION_CHECK_SQL, name="ck_exception_items_action"),
        Index("idx_exception_items_exception_set_pid", "exception_set_pid"),
        Index("idx_exception_items_operation_pid", "operation_pid"),
        Index(
            "uq_exception_items_set_operation_table_column_action",
            "exception_set_pid",
            "operation_pid",
            "table_name",
            "column_name",
            "action",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )


class ClientExceptionSet(ClientSettingBaseModel):
    """API Client 的特例組綁定(0..N,各自效期;`expires_at` NULL = 不設限)。"""

    __tablename__ = "client_exception_sets"

    uid: Mapped[UUID] = _uid_column("client_exception_set_uid")
    api_client_uid: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        comment=(
            "API Client 對外識別碼(跨庫冷關聯,本體在自有 DB,無 FK)"
            "/ API client UID (cross-database soft reference, no FK)"
        ),
    )
    exception_set_pid: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            f"{CLIENT_SETTING_SCHEMA}.exception_sets.pid",
            name="fk_client_exception_sets_exception_set",
        ),
        nullable=False,
        comment="綁定的特例組 / Bound exception set",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
        comment="效期(UTC+8;NULL = 不設限)/ Expires at (UTC+8; NULL = never)",
    )

    __table_args__ = (
        Index("idx_client_exception_sets_exception_set_pid", "exception_set_pid"),
        Index(
            "uq_client_exception_sets_client_exception_set",
            "api_client_uid",
            "exception_set_pid",
            unique=True,
            postgresql_where=_SOFT_DELETE_WHERE,
        ),
        {"schema": CLIENT_SETTING_SCHEMA},
    )
