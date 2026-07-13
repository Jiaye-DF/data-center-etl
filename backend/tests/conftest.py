"""測試共用前置:get_settings 為 lru_cache(scan AD-007),各測試檔的 env 注入
時點不同(檔頭 os.environ 設定),每個測試前清快取確保讀到該檔期望的 env。
"""

import asyncio
import os

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()


# 共用測試 DB(data_center_etl_test)之建庫 + create_all 中央化:多支測試檔
# (test_audit_log.py / test_runs_api.py / test_snapshot_service.py / test_sync_api.py /
# test_schedule_api_v131.py 等)未自帶建表流程,全新環境依 pytest 收集順序先跑到即
# 集體 fail-fast;於此中央化冪等補齊,讓上述測試檔不依賴其他檔案的執行順序。
# 角色為固定字串(admin / member,見 app/core/roles.py),無 roles 表、無需 seed。
_SHARED_TEST_DB_NAME = "data_center_etl_test"


@pytest.fixture(scope="session", autouse=True)
def _prepare_shared_test_db() -> None:
    """共用測試 DB:不存在才建庫,並以 metadata create_all 補齊資料表(冪等)。

    僅本次 session 已有測試檔將 DATABASE_URL 指向共用測試 DB(`data_center_etl_test`)
    才動作;未觸碰 DB 的純單元測試一律略過。不對既有 DB 做任何 DROP。
    """
    database_url = os.environ.get("DATABASE_URL", "")
    if _SHARED_TEST_DB_NAME not in database_url:
        return

    pg_host = os.environ.get("TEST_PG_HOST", "localhost")
    pg_port = os.environ.get("TEST_PG_PORT", "5435")
    pg_user = os.environ.get("TEST_PG_USER", "data_center_etl")
    pg_password = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
    pg_admin_db = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
    base_url = f"postgresql+asyncpg://{pg_user}:{pg_password}@{pg_host}:{pg_port}"
    admin_database_url = f"{base_url}/{pg_admin_db}"
    test_database_url = f"{base_url}/{_SHARED_TEST_DB_NAME}"

    async def _prepare() -> None:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import NullPool

        from app import models  # noqa: F401  匯入全部 model 讓 create_all 建齊資料表
        from app.core.db import Base

        admin_engine = create_async_engine(
            admin_database_url, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        try:
            async with admin_engine.connect() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": _SHARED_TEST_DB_NAME},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(text(f'CREATE DATABASE "{_SHARED_TEST_DB_NAME}"'))
        finally:
            await admin_engine.dispose()

        test_engine = create_async_engine(test_database_url, poolclass=NullPool)
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await test_engine.dispose()

    asyncio.run(_prepare())
