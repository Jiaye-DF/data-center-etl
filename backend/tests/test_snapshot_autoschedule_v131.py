"""task-003 快照同步自動建逐表排程 + 收斂測試(真實 PostgreSQL 測試 DB + fake introspect)。

涵蓋 Acceptance:
- refresh(source)後每張來源表各一筆 `0 0 * * *` / 停用排程;
- 既有已啟用排程 refresh 後不被重置(啟停 / cron 不覆蓋);
- 來源表移除後對應排程軟刪;
- 預塞 `source_schema IS NULL` 的 v1.3.0 全表舊排程 → refresh 後被軟刪;
- refresh(dataset=target)不建立任何排程。

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
from app.models import Schedule  # noqa: E402
from app.services.snapshot_service import (  # noqa: E402
    SnapshotService,
    _CollectedTable,
)


# ── fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)並以 metadata 建 schema;跨 run 複用時以非破壞性
    ADD COLUMN IF NOT EXISTS 補齊 schedules 的 v1.3.1 來源表欄位。不對既有 DB 做任何 DROP。
    """

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
                # 跨 run 複用既有 schedules 表時,補齊 v1.3.1 欄位(非破壞性)
                await conn.execute(
                    text(
                        "ALTER TABLE schedules "
                        "ADD COLUMN IF NOT EXISTS source_schema VARCHAR(100)"
                    )
                )
                await conn.execute(
                    text(
                        "ALTER TABLE schedules "
                        "ADD COLUMN IF NOT EXISTS source_table VARCHAR(200)"
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
    async with db_engine.begin() as conn:
        # schedules 先於 rds_table_meta(避免殘留排程干擾;無 etl_runs 參照)
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM rds_table_meta"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每測試重置 redis 記憶體 fake(避免跨測試髒讀)。"""
    cache._client = None


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


_SYSTEM_UID = "00000000-0000-0000-0000-000000000000"


def _tables_three() -> list[_CollectedTable]:
    return [
        _CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12),
        _CollectedTable("DS", "GAT_FILE", "資料檔名檔", 3, 900),
        _CollectedTable("DS", "BBB_FILE", None, 2, 4),
    ]


def _patch_collect(
    monkeypatch: pytest.MonkeyPatch, tables: list[_CollectedTable]
) -> None:
    async def fake_collect(
        self: SnapshotService, dataset_value: str
    ) -> list[_CollectedTable]:
        return list(tables)

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect)


async def _refresh(
    session_factory: async_sessionmaker[AsyncSession], dataset: str = "source"
) -> int:
    async with session_factory() as session:
        result = await SnapshotService(session).refresh(dataset, uuid4())
        await session.commit()
    return result.table_count


async def _live_schedules(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[Schedule]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Schedule).where(Schedule.is_deleted.is_(False))
            )
        ).scalars()
        return list(rows.all())


# ── 每表一筆 0 0 * * * / 停用 ───────────────────────────────────────────
async def test_refresh_source_creates_disabled_daily_schedule_per_table(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch, _tables_three())
    assert await _refresh(session_factory) == 3

    schedules = await _live_schedules(session_factory)
    by_table = {(s.source_schema, s.source_table): s for s in schedules}
    assert set(by_table) == {
        ("DS", "AAA_FILE"),
        ("DS", "GAT_FILE"),
        ("DS", "BBB_FILE"),
    }
    for (schema, table), sched in by_table.items():
        assert sched.cron_expr == "0 0 * * *"
        assert sched.is_enabled is False
        assert sched.name == f"{schema}.{table}"
        assert sched.etl_table_pid is None


async def test_refresh_source_schedule_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch, _tables_three())
    await _refresh(session_factory)
    await _refresh(session_factory)
    schedules = await _live_schedules(session_factory)
    assert len(schedules) == 3  # 重複 refresh 不新增


# ── 既有已啟用排程 refresh 後不被重置 ──────────────────────────────────
async def test_existing_enabled_schedule_not_reset(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    # 預先建立一筆已啟用、cron 自訂的 GAT_FILE 排程
    async with session_factory() as session:
        session.add(
            Schedule(
                uid=uuid4(),
                name="DS.GAT_FILE",
                cron_expr="30 2 * * *",
                is_enabled=True,
                etl_table_pid=None,
                source_schema="DS",
                source_table="GAT_FILE",
                created_by=_SYSTEM_UID,
                updated_by=_SYSTEM_UID,
            )
        )
        await session.commit()

    _patch_collect(monkeypatch, _tables_three())
    await _refresh(session_factory)

    schedules = await _live_schedules(session_factory)
    gat = [s for s in schedules if s.source_table == "GAT_FILE"]
    assert len(gat) == 1  # 未重複建立
    assert gat[0].is_enabled is True  # 啟停未被重置
    assert gat[0].cron_expr == "30 2 * * *"  # cron 未被覆蓋
    assert len(schedules) == 3  # 其餘兩表補齊


# ── 來源表移除後軟刪對應排程 ────────────────────────────────────────────
async def test_removed_source_table_schedule_soft_deleted(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch, _tables_three())
    await _refresh(session_factory)

    # 下一輪 BBB_FILE 消失
    _patch_collect(
        monkeypatch,
        [
            _CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12),
            _CollectedTable("DS", "GAT_FILE", "資料檔名檔", 3, 900),
        ],
    )
    await _refresh(session_factory)

    live = {s.source_table for s in await _live_schedules(session_factory)}
    assert live == {"AAA_FILE", "GAT_FILE"}
    async with session_factory() as session:
        bbb = (
            await session.execute(
                select(Schedule).where(Schedule.source_table == "BBB_FILE")
            )
        ).scalar_one()
        assert bbb.is_deleted is True


# ── v1.3.0 全表舊排程(source_schema IS NULL)一次性軟刪 ─────────────────
async def test_legacy_all_table_schedule_soft_deleted(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async with session_factory() as session:
        session.add(
            Schedule(
                uid=uuid4(),
                name="每天增量同步(全部表)",
                cron_expr="0 3 * * *",
                is_enabled=True,
                etl_table_pid=None,
                source_schema=None,
                source_table=None,
                created_by=_SYSTEM_UID,
                updated_by=_SYSTEM_UID,
            )
        )
        await session.commit()

    _patch_collect(monkeypatch, _tables_three())
    await _refresh(session_factory)

    async with session_factory() as session:
        legacy = (
            await session.execute(
                select(Schedule).where(Schedule.source_schema.is_(None))
            )
        ).scalar_one()
        assert legacy.is_deleted is True
    # 逐表排程正常建立,舊全表排程不列入 live
    live = {s.source_table for s in await _live_schedules(session_factory)}
    assert live == {"AAA_FILE", "GAT_FILE", "BBB_FILE"}


# ── dataset=target 不建立任何排程 ──────────────────────────────────────
async def test_refresh_target_creates_no_schedule(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(
        monkeypatch,
        [_CollectedTable("PUBLIC", "orders", None, 4, 10)],
    )
    await _refresh(session_factory, dataset="target")

    async with session_factory() as session:
        total = (
            await session.execute(select(func.count()).select_from(Schedule))
        ).scalar_one()
        assert total == 0
