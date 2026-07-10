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


# 共用測試 DB(data_center_etl_test)角色冪等 seed 中央化(fixed.md §4):多支測試檔
# (test_audit_log.py / test_runs_api.py / test_snapshot_service.py / test_sync_api.py /
# test_schedule_api_v131.py 等)呼叫 UserRepository.create 卻未自帶 roles seed,
# 全新環境依 pytest 收集順序先跑到即集體 fail-fast;於此中央化冪等補齊,
# 讓上述測試檔不再依賴其他檔案的執行順序自立。
_SHARED_TEST_DB_NAME = "data_center_etl_test"
_SYSTEM_ACTOR_UID = "00000000-0000-0000-0000-000000000000"
_SEED_ROLES = (
    ("admin", "管理員", "00000000-0000-0000-0000-0000000000a1"),
    ("viewer", "檢視者", "00000000-0000-0000-0000-0000000000a2"),
)


@pytest.fixture(scope="session", autouse=True)
def _seed_shared_test_db_roles() -> None:
    """共用測試 DB 角色 seed(admin / viewer,存在即跳過)。

    僅本次 session 已有測試檔將 DATABASE_URL 指向共用測試 DB(`data_center_etl_test`)
    才動作;獨立測試 DB(如 v141 / seed 專用)或未觸碰 DB 的純單元測試一律略過,
    不影響既有測試檔案。
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

    async def _seed() -> None:
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
                for code, name, seed_uid in _SEED_ROLES:
                    role_exists = (
                        await conn.execute(
                            text(
                                "SELECT 1 FROM roles "
                                "WHERE code = :code AND is_deleted = false"
                            ),
                            {"code": code},
                        )
                    ).scalar()
                    if role_exists is None:
                        await conn.execute(
                            text(
                                "INSERT INTO roles "
                                "(uid, code, name, is_builtin, created_by, updated_by) "
                                "VALUES (:uid, :code, :name, true, :actor, :actor)"
                            ),
                            {
                                "uid": seed_uid,
                                "code": code,
                                "name": name,
                                "actor": _SYSTEM_ACTOR_UID,
                            },
                        )
        finally:
            await test_engine.dispose()

    asyncio.run(_seed())
