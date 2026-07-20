"""semantic_schema 冪等建置測試(task-001,propose A1):`erp_metadata.semantic_mappings`。

CHECK 約束等實際 DDL 行為無法用 FakeConn 驗證,故對齊 test_mirror_sync_incremental.py 模式:
連真實本地 PostgreSQL 測試 DB(env 指向共用測試 DB,不觸碰真正 AWS RDS),
驗證冪等呼叫不 raise、schema/table 實際建立、CHECK 拒絕非 draft/confirmed。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建立 engine;semantic_schema 連線沿用 AWS_RDS_*(見 reader.py),
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

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl.comments import quote_ident  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.semantic_schema import (  # noqa: E402
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

_TABLE_EXISTS_SQL = text(
    "SELECT 1 FROM information_schema.tables"
    " WHERE table_schema = :schema AND table_name = :table"
)

_INSERT_SQL = text(
    f"INSERT INTO {_QUALIFIED} (table_name, column_name, english_name, status)"
    " VALUES (:t, :c, :e, :s)"
)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """指向共用測試 DB 的 engine(NullPool,對齊既有整合測試模式)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_semantic_mappings(target_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試後清空表資料(非 DROP);表本身可能不存在,先檢查再清。"""
    yield
    async with target_engine.begin() as conn:
        exists = (
            await conn.execute(
                _TABLE_EXISTS_SQL, {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE}
            )
        ).first()
        if exists is not None:
            await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))


async def test_ensure_semantic_schema_idempotent_no_raise(target_engine: AsyncEngine) -> None:
    """重複呼叫 ensure 兩次不 raise(冪等)。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)


async def test_ensure_semantic_schema_creates_schema_and_table(
    target_engine: AsyncEngine,
) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(
                _TABLE_EXISTS_SQL, {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE}
            )
        ).first()
    assert row is not None


async def test_check_rejects_invalid_status(target_engine: AsyncEngine) -> None:
    """CHECK 拒絕非 draft/confirmed 的 status。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    with pytest.raises(IntegrityError):
        async with target_engine.begin() as conn:
            await conn.execute(
                _INSERT_SQL,
                {"t": "AAA_FILE", "c": "AAA01", "e": "account no", "s": "invalid"},
            )


async def test_check_accepts_draft_and_confirmed(target_engine: AsyncEngine) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.begin() as conn:
        await conn.execute(
            _INSERT_SQL,
            {"t": "AAA_FILE", "c": "AAA01", "e": "account no", "s": "draft"},
        )
        await conn.execute(
            _INSERT_SQL,
            {"t": "AAA_FILE", "c": "AAA02", "e": "account name", "s": "confirmed"},
        )


_UPDATED_AT_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = :table AND column_name = 'updated_at'"
)


async def test_updated_at_is_naive_timestamp(target_engine: AsyncEngine) -> None:
    """updated_at 一律 naive timestamp(MSSQL datetime2 等價;user 決議 2026-07-20)。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(
                _UPDATED_AT_TYPE_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
    assert row is not None
    assert row[0] == "timestamp without time zone"


async def test_ensure_migrates_legacy_timestamptz(target_engine: AsyncEngine) -> None:
    """舊版 timestamptz 欄位:ensure 冪等轉為 naive timestamp 且既有資料保留。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
        # 模擬舊版部署狀態:把欄位改回 timestamptz(僅測試用;非破壞性型別轉換)
        await conn.execute(
            text(
                f"ALTER TABLE {_QUALIFIED} ALTER COLUMN updated_at TYPE timestamptz"
                " USING (updated_at AT TIME ZONE 'Asia/Taipei')"
            )
        )
        await conn.execute(
            _INSERT_SQL,
            {"t": "LEGACY_FILE", "c": "L01", "e": "legacy col", "s": "draft"},
        )

    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        type_row = (
            await conn.execute(
                _UPDATED_AT_TYPE_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
        data_row = (
            await conn.execute(
                text(
                    f"SELECT updated_at FROM {_QUALIFIED}"
                    " WHERE table_name = 'LEGACY_FILE' AND column_name = 'L01'"
                )
            )
        ).first()
    assert type_row is not None and type_row[0] == "timestamp without time zone"
    assert data_row is not None and data_row[0] is not None
    assert data_row[0].tzinfo is None
