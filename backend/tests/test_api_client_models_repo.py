"""task-001 API Client 機器身分 model / repository 測試(真實 PostgreSQL 測試 DB)。

涵蓋:
- 建 client + 雙 active 密鑰並存;第三把被應用層上限擋下(AppError 409)。
- retire 後 active 只剩一把。
- get_by_client_id 不回軟刪列。
- client_id 軟刪後可重建同名(partial unique index)。
- 兩表 status CHECK 違規丟 IntegrityError。
"""

import asyncio
import os

# app.core.db 於 import 時即建立 engine → 必須先注入測試 env,再 import app 模組
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
TEST_DATABASE_URL = f"{_BASE_URL}/{TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from uuid import UUID  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.core.db import Base  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.models.api_client_secret import (  # noqa: E402
    SECRET_STATUS_ACTIVE,
    SECRET_STATUS_RETIRED,
    ApiClientSecret,
)
from app.models.api_client_user import (  # noqa: E402
    CLIENT_STATUS_DISABLED,
    CLIENT_STATUS_ENABLED,
    DEFAULT_RATE_LIMIT_PER_10MIN,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    ApiClientUser,
)
from app.repositories.api_client_repo import (  # noqa: E402
    MAX_ACTIVE_SECRETS,
    ApiClientRepository,
)

_ZERO_UID = UUID(int=0)


# ── fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)並以 metadata 建 schema;不對既有 DB 做任何 DROP。"""

    async def _prepare() -> None:
        admin_engine = create_async_engine(
            ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        try:
            async with admin_engine.connect() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": TEST_DB_NAME},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        finally:
            await admin_engine.dispose()

        test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await test_engine.dispose()

    asyncio.run(_prepare())


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(db_engine: AsyncEngine) -> None:
    # 僅測試 DB;非業務環境的物理刪除(先子表後父表)
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM api_client_secrets"))
        await conn.execute(text("DELETE FROM api_client_users"))


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _create_client(session: AsyncSession, client_id: str) -> ApiClientUser:
    return await ApiClientRepository(session).create(
        client_id=client_id, name=f"系統 {client_id}", actor_uid=_ZERO_UID
    )


# ── model 預設值 / 約束定義 ──────────────────────────────────────────────
def test_partial_unique_index_on_client_id() -> None:
    """uq_api_client_users_client_id 為未刪除範圍的 partial unique index。"""
    idx = next(
        i
        for i in ApiClientUser.__table__.indexes
        if i.name == "uq_api_client_users_client_id"
    )
    assert idx.unique
    assert idx.dialect_options["postgresql"]["where"] is not None
    assert {c.name for c in idx.columns} == {"client_id"}


def test_secret_fk_and_index_naming() -> None:
    """FK / index 命名符合 04-databases 命名規範。"""
    table = ApiClientSecret.__table__
    fk = next(iter(table.columns["api_client_user_pid"].foreign_keys))
    assert fk.constraint is not None
    assert fk.constraint.name == "fk_api_client_secrets_api_client_user"
    assert fk.column is ApiClientUser.__table__.columns["pid"]
    assert any(
        i.name == "idx_api_client_secrets_api_client_user_pid" for i in table.indexes
    )


async def test_create_applies_status_and_rate_limit_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        client = await _create_client(session, "erp-portal")
        await session.commit()

    assert client.status == CLIENT_STATUS_ENABLED
    assert client.rate_limit_per_minute == DEFAULT_RATE_LIMIT_PER_MINUTE
    assert client.rate_limit_per_10min == DEFAULT_RATE_LIMIT_PER_10MIN
    assert client.is_deleted is False


# ── 雙鑰輪替 ─────────────────────────────────────────────────────────────
async def test_two_active_secrets_coexist_and_third_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        client = await _create_client(session, "dual-key")
        await repo.add_secret(client, secret_hash="$2b$hash-a", actor_uid=_ZERO_UID)
        await repo.add_secret(client, secret_hash="$2b$hash-b", actor_uid=_ZERO_UID)
        await session.commit()

    async with session_factory() as session:
        repo = ApiClientRepository(session)
        found = await repo.get_by_client_id("dual-key")
        assert found is not None
        client, secrets = found
        assert len(secrets) == MAX_ACTIVE_SECRETS
        assert [s.secret_hash for s in secrets] == ["$2b$hash-a", "$2b$hash-b"]
        assert all(s.status == SECRET_STATUS_ACTIVE for s in secrets)

        # 第三把由應用層上限擋下(DB 無此約束)
        with pytest.raises(AppError) as exc:
            await repo.add_secret(client, secret_hash="$2b$hash-c", actor_uid=_ZERO_UID)
        assert exc.value.status_code == 409


async def test_retire_leaves_single_active_secret(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        client = await _create_client(session, "rotate-me")
        old = await repo.add_secret(client, secret_hash="$2b$old", actor_uid=_ZERO_UID)
        await repo.add_secret(client, secret_hash="$2b$new", actor_uid=_ZERO_UID)
        await repo.retire_secret(old, actor_uid=_ZERO_UID)
        await session.commit()

    async with session_factory() as session:
        repo = ApiClientRepository(session)
        found = await repo.get_by_client_id("rotate-me")
        assert found is not None
        client, secrets = found
        assert [s.secret_hash for s in secrets] == ["$2b$new"]

        # retired 舊鑰仍在(不物理刪除),且輪替後可再補一把
        retired = (
            await session.execute(
                ApiClientSecret.__table__.select().where(
                    ApiClientSecret.status == SECRET_STATUS_RETIRED
                )
            )
        ).one()
        assert retired.secret_hash == "$2b$old"
        await repo.add_secret(client, secret_hash="$2b$newer", actor_uid=_ZERO_UID)
        assert len(await repo.list_active_secrets(client)) == MAX_ACTIVE_SECRETS


# ── 軟刪除 ───────────────────────────────────────────────────────────────
async def test_get_by_client_id_skips_soft_deleted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        client = await _create_client(session, "gone")
        await repo.soft_delete(client, actor_uid=_ZERO_UID)
        await session.commit()

    async with session_factory() as session:
        repo = ApiClientRepository(session)
        assert await repo.get_by_client_id("gone") is None
        clients, total = await repo.list_(offset=0, limit=10)
        assert clients == []
        assert total == 0


async def test_client_id_reusable_after_soft_delete(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        first = await _create_client(session, "reused")
        await repo.soft_delete(first, actor_uid=_ZERO_UID)
        await session.commit()

    async with session_factory() as session:
        repo = ApiClientRepository(session)
        second = await repo.create(
            client_id="reused",
            name="重建後的系統",
            description="同名重建",
            status=CLIENT_STATUS_DISABLED,
            actor_uid=_ZERO_UID,
        )
        await session.commit()

    assert second.pid != first.pid

    async with session_factory() as session:
        repo = ApiClientRepository(session)
        found = await repo.get_by_client_id("reused")
        assert found is not None
        assert found[0].pid == second.pid
        assert found[0].status == CLIENT_STATUS_DISABLED


async def test_duplicate_active_client_id_rejected(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """未刪除範圍內同 client_id 由 partial unique index 擋下。"""
    async with session_factory() as session:
        await _create_client(session, "dup")
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await _create_client(session, "dup")
            await session.commit()
        await session.rollback()


# ── update ───────────────────────────────────────────────────────────────
async def test_update_changes_only_given_fields(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        client = await repo.create(
            client_id="patch-me",
            name="原名",
            description="原說明",
            actor_uid=_ZERO_UID,
        )
        await repo.update(
            client,
            status=CLIENT_STATUS_DISABLED,
            rate_limit_per_minute=5,
            actor_uid=_ZERO_UID,
        )
        await session.commit()

    async with session_factory() as session:
        found = await ApiClientRepository(session).get_by_client_id("patch-me")
        assert found is not None
        updated = found[0]
        assert updated.status == CLIENT_STATUS_DISABLED
        assert updated.rate_limit_per_minute == 5
        assert updated.name == "原名"
        assert updated.description == "原說明"
        assert updated.rate_limit_per_10min == DEFAULT_RATE_LIMIT_PER_10MIN


# ── CHECK 約束 ───────────────────────────────────────────────────────────
async def test_client_status_check_rejects_unknown_value(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await ApiClientRepository(session).create(
                client_id="bad-status", name="壞狀態", status="paused", actor_uid=_ZERO_UID
            )
            await session.commit()
        await session.rollback()


async def test_secret_status_check_rejects_unknown_value(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        client = await _create_client(session, "secret-check")
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            session.add(
                ApiClientSecret(
                    uid=UUID(int=1),
                    api_client_user_pid=client.pid,
                    secret_hash="$2b$whatever",
                    status="expired",
                    created_by=_ZERO_UID,
                    updated_by=_ZERO_UID,
                )
            )
            await session.commit()
        await session.rollback()
