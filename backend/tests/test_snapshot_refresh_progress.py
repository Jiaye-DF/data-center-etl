"""快照 refresh 進度回報測試(真實 PostgreSQL 測試 DB + fake collect)。

涵蓋:refresh 過程寫入階段進度(introspect / persist / schedules)、結束清進度 key、
聚合進度端點 `GET /progress` 閒置回四欄位 / 進行中回進度、member 403、
同 dataset 併發 refresh 409 互斥(AD-120)、進度 key 不落 datasets:* 誤刪範圍(AD-119)。
introspect / 字典查詢以 monkeypatch `_collect_from_rds` 取代(不打 RDS);Redis 走記憶體 fake。
"""

import asyncio
import os

# app.core.db 於 import 時即建立 engine → 先注入測試 env 再 import app 模組
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
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.api.deps import get_db  # noqa: E402
from app.core import redis as cache  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.schemas.rawdata import SnapshotRefreshProgress  # noqa: E402
from app.services.snapshot_service import (  # noqa: E402
    SnapshotService,
    _CollectedTable,
)


# ── fixtures(對齊 test_snapshot_service.py 慣例)────────────────────────
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
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM rds_table_meta"))
        await conn.execute(text("DELETE FROM users"))
        # 聚合進度端點含 sync(active run)欄位:清 run 殘留使斷言決定性
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每測試重置 redis 記憶體 fake(避免跨測試髒讀)。"""
    cache._client = None


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    app = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


async def _login_as(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    username = f"{role}-user"
    password = f"{role}-password-123"
    async with session_factory() as session:
        password_hash = await hash_password_async(password)
        await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


def _patch_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_collect(
        self: SnapshotService, dataset_value: str
    ) -> list[_CollectedTable]:
        return [
            _CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12),
            _CollectedTable("DS", "GAT_FILE", "資料檔名檔", 3, 900),
            _CollectedTable("DS", "EMPTY_FILE", None, 2, 0),
        ]

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect)


# ── refresh 過程寫入階段進度 + 結束清 key ───────────────────────────────
async def test_refresh_reports_phases_and_clears_key(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    recorded: list[SnapshotRefreshProgress] = []
    real_cache_set = cache.cache_set

    async def spy_cache_set(key: str, value: str, *, ttl_seconds: int) -> None:
        # AD-119 後進度 key 為 snapshot-progress:{dataset}(鎖 key 走 cache_set_nx,不經此)
        if ":snapshot-progress:" in key:
            recorded.append(SnapshotRefreshProgress.model_validate_json(value))
        await real_cache_set(key, value, ttl_seconds=ttl_seconds)

    monkeypatch.setattr(cache, "cache_set", spy_cache_set)

    async with session_factory() as session:
        service = SnapshotService(session)
        await service.refresh("source", uuid4())
        await session.commit()

        phases = [p.phase for p in recorded]
        # fake_collect 跳過 introspect callback,但 refresh 起手式仍回報 introspect
        assert "introspect" in phases
        assert "persist" in phases
        assert "schedules" in phases  # source 才有排程維護階段
        final_persist = [p for p in recorded if p.phase == "persist"][-1]
        assert final_persist.done == final_persist.total == 3
        assert all(p.active for p in recorded)

        # 結束後進度 key 已清 → active=False
        progress = await service.get_refresh_progress("source")
        assert progress.active is False


# ── 聚合進度端點(AD-121):閒置 / 進行中 / 權限 ─────────────────────────
async def test_global_progress_idle_returns_all_inactive(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.get("/api/v1/progress")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert set(data) == {"sync", "snapshot_source", "snapshot_target", "apply"}
    assert data["sync"] is None
    assert data["snapshot_source"]["active"] is False
    assert data["snapshot_target"]["active"] is False
    assert data["apply"]["active"] is False


async def test_global_progress_returns_running_snapshot_progress(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    async with session_factory() as session:
        await SnapshotService(session)._report_progress("target", "introspect", 50, 200)
    resp = await client.get("/api/v1/progress")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["snapshot_target"] == {
        "active": True,
        "phase": "introspect",
        "done": 50,
        "total": 200,
    }
    assert data["snapshot_source"]["active"] is False


async def test_global_progress_member_forbidden(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "member")
    resp = await client.get("/api/v1/progress")
    assert resp.status_code == 403, resp.text


# ── AD-119:進度 key 不落在 datasets:* 快取失效的誤刪範圍 ────────────────
async def test_progress_key_survives_datasets_cache_invalidation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await SnapshotService(session)._report_progress("source", "persist", 100, 500)
    # mirror_sync 收尾 / refresh 後的快取失效 pattern:不得掃到快照進度 key
    await cache.delete_pattern(cache.cache_key("datasets", "source", "*"))
    progress = await SnapshotService.get_refresh_progress("source")
    assert progress.active is True
    assert progress.done == 100


# ── AD-120:同 dataset 併發 refresh 以 SET NX 鎖互斥 → 409 ───────────────
async def test_refresh_conflict_when_lock_held(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    lock_key = cache.cache_key("snapshot-progress", "source", "lock")
    # 模擬另一請求 / process 正在 refresh(持鎖中)
    assert await cache.cache_set_nx(lock_key, "1", ttl_seconds=60) is True
    async with session_factory() as session:
        service = SnapshotService(session)
        with pytest.raises(AppError) as exc_info:
            await service.refresh("source", uuid4())
        assert exc_info.value.status_code == 409
        # 釋放鎖後可正常執行(鎖於 finally 釋放,重跑不殘留)
        await cache.cache_delete(lock_key)
        result = await service.refresh("source", uuid4())
        await session.commit()
    assert result.table_count == 3
    assert await cache.cache_get(lock_key) is None
