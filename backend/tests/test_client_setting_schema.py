"""client_setting schema 冪等建置測試(v1.6.1 task-001)。

對齊 test_semantic_schema.py 模式:連真實本地 PostgreSQL 測試 DB 模擬 RDS
(env 指向共用測試 DB,不觸碰真正 AWS RDS),驗證 12 張權限表齊備、BaseModel 欄位齊、
naive timestamp、roles.permission_profile_pid NOT NULL、DDL 可重跑,以及另開一條
連線(模擬他機)可直接 SELECT。清理一律 DELETE 資料,**不做任何 DROP**。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建立 engine;client_setting 連線沿用 AWS_RDS_*(見 reader.py),
# 測試指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}",
)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl.client_setting_schema import (  # noqa: E402
    client_setting_engine,
    ensure_client_setting_schema,
)
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402
from app.models.client_setting import (  # noqa: E402
    CLIENT_SETTING_SCHEMA,
    CLIENT_SETTING_TABLES,
)

# 各表對外識別碼欄名(獨立於實作重列一份,作為 ERD 對照)
_UID_COLUMNS: dict[str, str] = {
    "services": "service_uid",
    "operations": "operation_uid",
    "operation_items": "operation_item_uid",
    "permission_profiles": "permission_profile_uid",
    "profile_operations": "profile_operation_uid",
    "profile_items": "profile_item_uid",
    "roles": "role_uid",
    "client_roles": "client_role_uid",
    "exception_sets": "exception_set_uid",
    "exception_operations": "exception_operation_uid",
    "exception_items": "exception_item_uid",
    "client_exception_sets": "client_exception_set_uid",
}

_BASE_COLUMNS = (
    "pid",
    "is_deleted",
    "created_at",
    "updated_at",
    "created_by",
    "updated_by",
)

_TABLES_SQL = text(
    "SELECT table_name FROM information_schema.tables WHERE table_schema = :schema"
)

_COLUMNS_SQL = text(
    "SELECT column_name, data_type, is_nullable FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = :table"
)

_TABLE_EXISTS_SQL = text(
    "SELECT 1 FROM information_schema.tables"
    " WHERE table_schema = :schema AND table_name = :table"
)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """指向共用測試 DB 的 engine(NullPool,對齊既有整合測試模式)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def prepared_engine(target_engine: AsyncEngine) -> AsyncEngine:
    """已完成冪等建置的 engine。"""
    async with target_engine.begin() as conn:
        await ensure_client_setting_schema(conn)
    return target_engine


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(target_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試後清空資料(反向 FK 順序,子表在先);表可能不存在,先檢查再清。禁 DROP。"""
    yield
    async with target_engine.begin() as conn:
        for table in reversed(CLIENT_SETTING_TABLES):
            exists = (
                await conn.execute(
                    _TABLE_EXISTS_SQL, {"schema": CLIENT_SETTING_SCHEMA, "table": table}
                )
            ).first()
            if exists is not None:
                await conn.execute(text(f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table}"))


async def test_ensure_is_idempotent(target_engine: AsyncEngine) -> None:
    """重複執行 DDL 不報錯(冪等可重跑)。"""
    for _ in range(2):
        async with target_engine.begin() as conn:
            await ensure_client_setting_schema(conn)


async def test_all_tables_created(prepared_engine: AsyncEngine) -> None:
    """12 張權限表齊備於 client_setting schema。"""
    async with prepared_engine.connect() as conn:
        rows = (
            await conn.execute(_TABLES_SQL, {"schema": CLIENT_SETTING_SCHEMA})
        ).scalars().all()
    assert set(CLIENT_SETTING_TABLES).issubset(set(rows))
    assert len(CLIENT_SETTING_TABLES) == 12


async def test_every_table_has_base_model_columns(prepared_engine: AsyncEngine) -> None:
    """全表含 BaseModel 欄位 + 各自 `<table>_uid`;時間欄位為 naive timestamp。"""
    async with prepared_engine.connect() as conn:
        for table in CLIENT_SETTING_TABLES:
            rows = (
                await conn.execute(
                    _COLUMNS_SQL, {"schema": CLIENT_SETTING_SCHEMA, "table": table}
                )
            ).all()
            columns = {row[0]: (row[1], row[2]) for row in rows}
            for column in _BASE_COLUMNS:
                assert column in columns, f"{table} 缺 {column}"
            assert _UID_COLUMNS[table] in columns, f"{table} 缺對外識別碼欄位"
            assert columns[_UID_COLUMNS[table]][0] == "uuid"
            assert columns["created_by"][0] == "uuid"
            assert columns["updated_by"][0] == "uuid"
            assert columns["is_deleted"][0] == "boolean"
            # 禁 timestamptz(06-timezone:RDS 一律 naive timestamp 存 UTC+8)
            assert columns["created_at"][0] == "timestamp without time zone"
            assert columns["updated_at"][0] == "timestamp without time zone"
            for column in _BASE_COLUMNS:
                assert columns[column][1] == "NO", f"{table}.{column} 應為 NOT NULL"


async def test_roles_permission_profile_pid_not_null(prepared_engine: AsyncEngine) -> None:
    """Role 必綁設定檔:DB 層 NOT NULL 禁空角色。"""
    async with prepared_engine.connect() as conn:
        rows = (
            await conn.execute(
                _COLUMNS_SQL, {"schema": CLIENT_SETTING_SCHEMA, "table": "roles"}
            )
        ).all()
    columns = {row[0]: row[2] for row in rows}
    assert columns["permission_profile_pid"] == "NO"


async def test_client_exception_sets_expires_at_nullable_naive(
    prepared_engine: AsyncEngine,
) -> None:
    """特例效期:naive timestamp 且可為 NULL(NULL = 不設限)。"""
    async with prepared_engine.connect() as conn:
        rows = (
            await conn.execute(
                _COLUMNS_SQL,
                {"schema": CLIENT_SETTING_SCHEMA, "table": "client_exception_sets"},
            )
        ).all()
    columns = {row[0]: (row[1], row[2]) for row in rows}
    assert columns["expires_at"] == ("timestamp without time zone", "YES")


async def test_insert_and_read_from_another_connection(prepared_engine: AsyncEngine) -> None:
    """模擬他機:另開一條 RDS 連線可直接 SELECT client_setting.services 讀到剛寫入的設定。"""
    async with prepared_engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {CLIENT_SETTING_SCHEMA}.services (code, name, description)"
                " VALUES (:code, :name, :description)"
            ),
            {"code": "erp", "name": "ERP 系統", "description": "任務單元測試"},
        )

    async with client_setting_engine() as other_engine:
        async with other_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        f"SELECT service_uid, name, is_deleted, created_at"
                        f" FROM {CLIENT_SETTING_SCHEMA}.services WHERE code = :code"
                    ),
                    {"code": "erp"},
                )
            ).first()
    assert row is not None
    assert row[1] == "ERP 系統"
    assert row[2] is False
    assert row[3].tzinfo is None  # naive UTC+8


async def test_services_code_partial_unique(prepared_engine: AsyncEngine) -> None:
    """未刪列 code 唯一;軟刪除後允許以同 code 重建。"""
    insert_sql = text(
        f"INSERT INTO {CLIENT_SETTING_SCHEMA}.services (code, name) VALUES (:code, :name)"
    )
    async with prepared_engine.begin() as conn:
        await conn.execute(insert_sql, {"code": "crm", "name": "CRM"})

    with pytest.raises(IntegrityError):
        async with prepared_engine.begin() as conn:
            await conn.execute(insert_sql, {"code": "crm", "name": "CRM 重複"})

    async with prepared_engine.begin() as conn:
        await conn.execute(
            text(
                f"UPDATE {CLIENT_SETTING_SCHEMA}.services SET is_deleted = true"
                " WHERE code = :code"
            ),
            {"code": "crm"},
        )
        await conn.execute(insert_sql, {"code": "crm", "name": "CRM 重建"})


async def test_profile_items_action_check(prepared_engine: AsyncEngine) -> None:
    """權限項動作僅接受 read / edit。"""
    async with prepared_engine.begin() as conn:
        service_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.services (code, name)"
                    " VALUES ('hrm', 'HRM') RETURNING pid"
                )
            )
        ).scalar_one()
        operation_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.operations (service_pid, name)"
                    " VALUES (:service_pid, 'O1') RETURNING pid"
                ),
                {"service_pid": service_pid},
            )
        ).scalar_one()
        profile_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.permission_profiles (name)"
                    " VALUES ('P1') RETURNING pid"
                )
            )
        ).scalar_one()

    item_sql = text(
        f"INSERT INTO {CLIENT_SETTING_SCHEMA}.profile_items"
        " (permission_profile_pid, operation_pid, table_name, column_name, action)"
        " VALUES (:profile_pid, :operation_pid, :table_name, :column_name, :action)"
    )
    params = {
        "profile_pid": profile_pid,
        "operation_pid": operation_pid,
        "table_name": "T1",
        "column_name": "C11",
    }
    async with prepared_engine.begin() as conn:
        await conn.execute(item_sql, {**params, "action": "read"})
        await conn.execute(item_sql, {**params, "column_name": "C12", "action": "edit"})

    with pytest.raises(IntegrityError):
        async with prepared_engine.begin() as conn:
            await conn.execute(item_sql, {**params, "column_name": "C13", "action": "write"})


async def test_client_roles_allows_at_most_one_role_per_client(
    prepared_engine: AsyncEngine,
) -> None:
    """API Client 只綁 0..1 Role:未刪列 api_client_uid 唯一。"""
    api_client_uid = uuid4()
    async with prepared_engine.begin() as conn:
        profile_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.permission_profiles (name)"
                    " VALUES ('P-role') RETURNING pid"
                )
            )
        ).scalar_one()
        role_pids = [
            (
                await conn.execute(
                    text(
                        f"INSERT INTO {CLIENT_SETTING_SCHEMA}.roles"
                        " (permission_profile_pid, name) VALUES (:profile_pid, :name)"
                        " RETURNING pid"
                    ),
                    {"profile_pid": profile_pid, "name": name},
                )
            ).scalar_one()
            for name in ("R1", "R2")
        ]
        await conn.execute(
            text(
                f"INSERT INTO {CLIENT_SETTING_SCHEMA}.client_roles (api_client_uid, role_pid)"
                " VALUES (:api_client_uid, :role_pid)"
            ),
            {"api_client_uid": api_client_uid, "role_pid": role_pids[0]},
        )

    with pytest.raises(IntegrityError):
        async with prepared_engine.begin() as conn:
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.client_roles"
                    " (api_client_uid, role_pid) VALUES (:api_client_uid, :role_pid)"
                ),
                {"api_client_uid": api_client_uid, "role_pid": role_pids[1]},
            )


async def test_no_cross_database_foreign_key_on_api_client_uid(
    prepared_engine: AsyncEngine,
) -> None:
    """跨庫冷關聯:api_client_uid 不得有任何 FK 約束。"""
    async with prepared_engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT tc.constraint_name FROM information_schema.table_constraints tc"
                    " JOIN information_schema.key_column_usage kcu"
                    "   ON tc.constraint_name = kcu.constraint_name"
                    "  AND tc.table_schema = kcu.table_schema"
                    " WHERE tc.table_schema = :schema"
                    "   AND tc.constraint_type = 'FOREIGN KEY'"
                    "   AND kcu.column_name = 'api_client_uid'"
                ),
                {"schema": CLIENT_SETTING_SCHEMA},
            )
        ).all()
    assert rows == []
