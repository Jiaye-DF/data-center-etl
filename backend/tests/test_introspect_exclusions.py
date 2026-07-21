"""introspect 內省排除測試(v1.5.1 fixed:erp_metadata / `*_view` / 舊制 `*_en`
不得出現在快照與 schema 清單 — 系統結構非業務資料分類)。

連真實本地 PostgreSQL 測試 DB(對齊 test_view_generator.py 模式);
建置一律 IF NOT EXISTS,teardown 不刪結構(禁 DROP)。
"""

import asyncio
import os

_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
_TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
_ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
_TEST_DATABASE_URL = f"{_BASE_URL}/{_TEST_DB_NAME}"

import logging  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl import introspect  # noqa: E402
from app.etl.semantic_schema import ensure_semantic_schema  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)+ 語意表 + 內省用探針 schema / 表;不做任何 DROP。"""

    async def _prepare() -> None:
        admin_engine = create_async_engine(
            _ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        try:
            async with admin_engine.connect() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": _TEST_DB_NAME},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
        finally:
            await admin_engine.dispose()

        engine = create_async_engine(_TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with engine.begin() as conn:
                await ensure_semantic_schema(conn)  # erp_metadata.semantic_mappings
                for schema, table in [
                    ("IX_TEST", "IX_PROBE"),
                    ("IX_TEST_view", "IX_VIEW_PROBE"),
                    ("IX_LEGACY_en", "IX_EN_PROBE"),
                ]:
                    await conn.execute(
                        text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
                    )
                    await conn.execute(
                        text(
                            f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}"'
                            " (c1 VARCHAR(5))"
                        )
                    )
        finally:
            await engine.dispose()

    asyncio.run(_prepare())


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(_TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield eng
    finally:
        await eng.dispose()


async def test_snapshot_tables_excludes_metadata_and_view_schemas(
    engine: AsyncEngine,
) -> None:
    async with engine.connect() as conn:
        tables = await introspect.snapshot_tables(conn)
    schemas = {str(t["schema"]) for t in tables}
    assert "IX_TEST" in schemas
    assert "erp_metadata" not in schemas
    assert "IX_TEST_view" not in schemas
    assert "IX_LEGACY_en" not in schemas


async def test_snapshot_tables_logs_suffix_excluded_schemas(
    engine: AsyncEngine, caplog: pytest.LogCaptureFixture
) -> None:
    """AD-129:後綴保留字(_view/_en)排除非靜默 — 快照內省補一次 info log 供診斷。"""
    with caplog.at_level(logging.INFO, logger="app.etl.introspect"):
        async with engine.connect() as conn:
            await introspect.snapshot_tables(conn)
    excluded_logs = [m for m in caplog.messages if "後綴保留字" in m]
    assert len(excluded_logs) == 1
    assert "IX_TEST_view" in excluded_logs[0]
    assert "IX_LEGACY_en" in excluded_logs[0]
    # erp_metadata 為已知系統 schema,不列入後綴排除診斷
    assert "erp_metadata" not in excluded_logs[0]
