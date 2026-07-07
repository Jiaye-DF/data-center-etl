"""task-003 rds_table_meta signature repo 讀寫方法測試(真實 PostgreSQL 測試 DB)。

涵蓋:
- read_stat_baselines:未寫 signature → None;update_stat_signature 後 → (ins,upd,del)。
- update_stat_signature:三欄正確落地。
- list_excluded:預設空;sync_excluded=true 後 → 含該 (schema,table)。
- dataset 隔離:source / target 互不干擾。
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
from datetime import datetime  # noqa: E402
from uuid import UUID  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text, update  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.core.db import Base  # noqa: E402
from app.models.rds_table_meta import Dataset, RdsTableMeta  # noqa: E402
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository  # noqa: E402

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
                # 既有測試 DB 可能早於 task-001 建立 → 非破壞性補齊新欄位(僅 ADD)
                await conn.execute(
                    text(
                        "ALTER TABLE rds_table_meta "
                        "ADD COLUMN IF NOT EXISTS last_stat_ins BIGINT, "
                        "ADD COLUMN IF NOT EXISTS last_stat_upd BIGINT, "
                        "ADD COLUMN IF NOT EXISTS last_stat_del BIGINT, "
                        "ADD COLUMN IF NOT EXISTS sync_excluded BOOLEAN "
                        "NOT NULL DEFAULT false"
                    )
                )
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
    # 僅測試 DB;非業務環境的物理刪除
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM rds_table_meta"))


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


async def _seed_snapshot(
    session: AsyncSession,
    *,
    dataset: Dataset,
    schema_name: str,
    table_name: str,
) -> None:
    """以 upsert_snapshot 建一筆 source 表快照(未寫 signature 基準)。"""
    await RdsTableMetaRepository(session).upsert_snapshot(
        dataset=dataset,
        schema_name=schema_name,
        table_name=table_name,
        business_name=None,
        column_count=3,
        row_count=10,
        snapshot_at=datetime(2026, 7, 7, 8, 0, 0),
        actor_uid=_ZERO_UID,
    )


# ── read_stat_baselines / update_stat_signature ─────────────────────────
async def test_baseline_none_before_signature_then_tuple_after(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _seed_snapshot(
            session, dataset=Dataset.SOURCE, schema_name="public", table_name="orders"
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        # 未寫 signature → None(尚無基準)
        baselines = await repo.read_stat_baselines(Dataset.SOURCE)
        assert baselines == {("public", "orders"): None}

        # 寫入 signature 基準
        await repo.update_stat_signature(
            Dataset.SOURCE,
            "public",
            "orders",
            n_tup_ins=100,
            n_tup_upd=20,
            n_tup_del=5,
            actor_uid=_ZERO_UID,
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        baselines = await repo.read_stat_baselines(Dataset.SOURCE)
        assert baselines == {("public", "orders"): (100, 20, 5)}


async def test_update_stat_signature_persists_three_columns(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _seed_snapshot(
            session, dataset=Dataset.SOURCE, schema_name="sales", table_name="invoices"
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        await repo.update_stat_signature(
            Dataset.SOURCE,
            "sales",
            "invoices",
            n_tup_ins=7,
            n_tup_upd=8,
            n_tup_del=9,
            actor_uid=_ZERO_UID,
        )
        await session.commit()

    async with session_factory() as session:
        row = (
            await session.execute(
                RdsTableMeta.__table__.select().where(
                    RdsTableMeta.schema_name == "sales",
                    RdsTableMeta.table_name == "invoices",
                )
            )
        ).one()
        assert row.last_stat_ins == 7
        assert row.last_stat_upd == 8
        assert row.last_stat_del == 9


# ── list_excluded ───────────────────────────────────────────────────────
async def test_list_excluded_empty_then_included(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _seed_snapshot(
            session, dataset=Dataset.SOURCE, schema_name="public", table_name="a"
        )
        await _seed_snapshot(
            session, dataset=Dataset.SOURCE, schema_name="public", table_name="b"
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        assert await repo.list_excluded(Dataset.SOURCE) == set()

    # 直接 raw update 設 sync_excluded=true(task-007 尚未提供設定方法)
    async with session_factory() as session:
        await session.execute(
            update(RdsTableMeta)
            .where(
                RdsTableMeta.dataset == Dataset.SOURCE,
                RdsTableMeta.schema_name == "public",
                RdsTableMeta.table_name == "a",
            )
            .values(sync_excluded=True)
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        assert await repo.list_excluded(Dataset.SOURCE) == {("public", "a")}


# ── dataset 隔離 ─────────────────────────────────────────────────────────
async def test_dataset_isolation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await _seed_snapshot(
            session, dataset=Dataset.SOURCE, schema_name="public", table_name="t"
        )
        await _seed_snapshot(
            session, dataset=Dataset.TARGET, schema_name="public", table_name="t"
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        # 只在 source 寫 signature 與排除
        await repo.update_stat_signature(
            Dataset.SOURCE,
            "public",
            "t",
            n_tup_ins=1,
            n_tup_upd=2,
            n_tup_del=3,
            actor_uid=_ZERO_UID,
        )
        await session.execute(
            update(RdsTableMeta)
            .where(
                RdsTableMeta.dataset == Dataset.SOURCE,
                RdsTableMeta.schema_name == "public",
                RdsTableMeta.table_name == "t",
            )
            .values(sync_excluded=True)
        )
        await session.commit()

    async with session_factory() as session:
        repo = RdsTableMetaRepository(session)
        # source 有基準與排除
        assert await repo.read_stat_baselines(Dataset.SOURCE) == {
            ("public", "t"): (1, 2, 3)
        }
        assert await repo.list_excluded(Dataset.SOURCE) == {("public", "t")}
        # target 不受影響:仍無基準、無排除
        assert await repo.read_stat_baselines(Dataset.TARGET) == {("public", "t"): None}
        assert await repo.list_excluded(Dataset.TARGET) == set()
