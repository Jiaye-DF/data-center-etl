"""task-002 快照服務測試(真實 PostgreSQL 測試 DB + fake introspect)。

涵蓋:refresh 落地筆數 / 業務名寫入 / upsert 冪等、list_tables 進階篩選(rows / synced)、
list_schemas 聚合、cache 命中第二次不打 repo(以計數驗)、移除的 columns 端點回 404。
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
from datetime import datetime  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.core import redis as cache  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Dataset, RdsTableMeta  # noqa: E402
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository  # noqa: E402
from app.services.snapshot_service import (  # noqa: E402
    SnapshotService,
    TableFilters,
    _CollectedTable,
)


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
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM rds_table_meta"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每測試重置 redis 記憶體 fake(避免跨測試髒讀)。"""
    cache._client = None


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


def _fake_tables() -> list[_CollectedTable]:
    """DS schema 三表:兩張有資料、一張 0 筆(hide_empty 過濾用);AAA_FILE 帶業務名。"""
    return [
        _CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12),
        _CollectedTable("DS", "GAT_FILE", "資料檔名檔", 3, 900),
        _CollectedTable("DS", "EMPTY_FILE", None, 2, 0),
    ]


def _patch_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_collect(self: SnapshotService, dataset_value: str) -> list[_CollectedTable]:
        return _fake_tables()

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect)


async def _refresh(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        result = await SnapshotService(session).refresh("source", uuid4())
        await session.commit()
    return result.table_count


# ── refresh:落地筆數 + 業務名 + 冪等 ───────────────────────────────────
async def test_refresh_persists_rows_and_business_name(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    assert await _refresh(session_factory) == 3
    async with session_factory() as session:
        total = (
            await session.execute(
                select(func.count())
                .select_from(RdsTableMeta)
                .where(
                    RdsTableMeta.dataset == Dataset.SOURCE,
                    RdsTableMeta.is_deleted.is_(False),
                )
            )
        ).scalar_one()
        assert total == 3
        aaa = (
            await session.execute(
                select(RdsTableMeta).where(RdsTableMeta.table_name == "AAA_FILE")
            )
        ).scalar_one()
        assert aaa.business_name == "帳別參數檔"
        assert aaa.column_count == 5
        assert aaa.row_count == 12
        assert aaa.snapshot_at is not None


async def test_refresh_is_idempotent_upsert(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    await _refresh(session_factory)
    async with session_factory() as session:
        total = (
            await session.execute(select(func.count()).select_from(RdsTableMeta))
        ).scalar_one()
        assert total == 3  # 重複 refresh 不新增(find-or-create)


# ── list_tables:rows 篩選(nonempty / empty / all)────────────────────
async def test_list_tables_rows_filter(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        svc = SnapshotService(session)
        nonempty = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(rows="nonempty")
        )
        assert {i.name for i in nonempty.items} == {"AAA_FILE", "GAT_FILE"}
        assert nonempty.total == 2
        empty = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(rows="empty")
        )
        assert {i.name for i in empty.items} == {"EMPTY_FILE"}
        assert empty.total == 1
        shown = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(rows="all")
        )
        assert shown.total == 3
        # 業務名隨快照帶回
        by_name = {i.name: i.business_name for i in shown.items}
        assert by_name["AAA_FILE"] == "帳別參數檔"
        assert by_name["EMPTY_FILE"] is None


# ── list_tables:synced 狀態篩選(NULL / NOT NULL)──────────────────────
async def test_list_tables_synced_filter(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        # 只把 GAT_FILE 標記為已同步,其餘維持 NULL
        await RdsTableMetaRepository(session).mark_synced(
            Dataset.SOURCE, "DS", "GAT_FILE", actor_uid=uuid4()
        )
        await session.commit()
    async with session_factory() as session:
        svc = SnapshotService(session)
        synced = await svc.list_tables(
            "source",
            "DS",
            page=1,
            page_size=50,
            filters=TableFilters(rows="all", synced="synced"),
        )
        assert {i.name for i in synced.items} == {"GAT_FILE"}
        unsynced = await svc.list_tables(
            "source",
            "DS",
            page=1,
            page_size=50,
            filters=TableFilters(rows="all", synced="unsynced"),
        )
        assert {i.name for i in unsynced.items} == {"AAA_FILE", "EMPTY_FILE"}


# ── list_tables:synced + 截止日(是否在該日前同步)──────────────────────
async def test_list_tables_synced_before_cutoff(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        # GAT_FILE 於 2026-06-01 同步;AAA_FILE / EMPTY_FILE 維持未同步(NULL)
        await RdsTableMetaRepository(session).mark_synced(
            Dataset.SOURCE, "DS", "GAT_FILE", actor_uid=uuid4(),
            when=datetime(2026, 6, 1, 12, 0, 0),
        )
        await session.commit()
    async with session_factory() as session:
        svc = SnapshotService(session)
        # 已同步 + 截止日在同步之後 → 含 GAT_FILE
        after = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(
                rows="all", synced="synced", synced_before=datetime(2026, 6, 2, 23, 59)
            ),
        )
        assert {i.name for i in after.items} == {"GAT_FILE"}
        # 已同步 + 截止日在同步之前 → 不含(同步發生在截止日後)
        before = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(
                rows="all", synced="synced", synced_before=datetime(2026, 5, 31, 23, 59)
            ),
        )
        assert before.total == 0
        # 未同步 + 截止日在同步之前 → GAT 到該日仍未同步,連同 NULL 兩張一起
        unsynced_by = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(
                rows="all", synced="unsynced", synced_before=datetime(2026, 5, 31, 23, 59)
            ),
        )
        assert {i.name for i in unsynced_by.items} == {"AAA_FILE", "EMPTY_FILE", "GAT_FILE"}


# ── list_schemas:聚合表數 ──────────────────────────────────────────────
async def test_list_schemas_aggregates_table_count(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        result = await SnapshotService(session).list_schemas("source")
    items = {i.schema_name: i.table_count for i in result.items}
    assert items == {"DS": 3}


# ── cache:命中第二次不打 repo(計數驗)────────────────────────────────
async def test_list_tables_cache_hit_skips_repo(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)

    calls = {"n": 0}
    original = RdsTableMetaRepository.list_by_schema

    async def counting(
        self: RdsTableMetaRepository, *args: object, **kwargs: object
    ) -> tuple[list[RdsTableMeta], int]:
        calls["n"] += 1
        return await original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(RdsTableMetaRepository, "list_by_schema", counting)

    async with session_factory() as session:
        svc = SnapshotService(session)
        first = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters()
        )
        second = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters()
        )

    assert calls["n"] == 1  # 第二次命中 cache,不再打 repo
    assert first.total == second.total == 2


async def test_refresh_invalidates_cache(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        svc = SnapshotService(session)
        filters = TableFilters(rows="all")
        before = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=filters
        )
        assert before.total == 3
    # 第二次 refresh 應失效 cache;此處以 delete_pattern 直接驗鍵已清
    key = cache.cache_key(
        "datasets", "source", "tables", "DS", 1, 50, *filters.cache_fragment()
    )
    assert await cache.cache_get(key) is not None
    await cache.delete_pattern(cache.cache_key("datasets", "source", "*"))
    assert await cache.cache_get(key) is None


# ── 移除的 columns 端點回 404 ──────────────────────────────────────────
async def test_columns_endpoint_removed_returns_404(client: AsyncClient) -> None:
    resp = await client.get(
        "/api/v1/datasets/source/tables/DS/GAT_FILE/columns"
    )
    assert resp.status_code == 404
