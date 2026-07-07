"""task-002 ScheduleRepository v1.3.1 逐表方法測試(真實 PostgreSQL 測試 DB)。

涵蓋:
- find_by_source_table / upsert_for_source_table(建立 + 不覆蓋既有啟停 / cron)
- soft_delete_by_source_tables_absent(來源表消失軟刪)
- soft_delete_legacy_all_table(軟刪 v1.3.0 遺留全表排程)
- list_tables_view(反映最新 log status + enabled / last_result / keyword 篩選)
- list_schema_summaries(表數 / 已啟用排程數)
- batch_set_enabled(實際變更筆數)
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
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.core.db import Base  # noqa: E402
from app.models import Dataset, EtlRun, EtlRunLog, Schedule  # noqa: E402
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository  # noqa: E402
from app.repositories.schedule_repo import ScheduleRepository  # noqa: E402
from app.utils.datetime import db_now  # noqa: E402

_ACTOR = uuid4()


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
                # create_all 不會為既有表補欄位;測試 DB 為持久複用,補齊 task-001 欄位
                # (ADD COLUMN IF NOT EXISTS 為非破壞性、冪等操作)
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
                await conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_schedules_source_table "
                        "ON schedules (source_schema, source_table) "
                        "WHERE is_deleted = false"
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
    # 依 FK 依賴順序清空(僅測試 DB;非業務環境的物理刪除)
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM etl_mappings"))
        await conn.execute(text("DELETE FROM etl_tables"))
        await conn.execute(text("DELETE FROM rds_table_meta"))
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


# ── helpers ─────────────────────────────────────────────────────────────
async def _snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema: str,
    table: str,
    business_name: str | None = None,
    row_count: int = 0,
    last_synced_at: datetime | None = None,
) -> None:
    async with session_factory() as session:
        meta = await RdsTableMetaRepository(session).upsert_snapshot(
            dataset=Dataset.SOURCE,
            schema_name=schema,
            table_name=table,
            business_name=business_name,
            column_count=1,
            row_count=row_count,
            snapshot_at=db_now(),
            actor_uid=_ACTOR,
        )
        if last_synced_at is not None:
            meta.last_synced_at = last_synced_at
        await session.commit()


async def _insert_log(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema: str,
    table: str,
    status: str,
) -> None:
    """插入一次 run + 一筆逐表 log(pid 遞增,較晚插入者為最新)。"""
    async with session_factory() as session:
        run = EtlRun(
            uid=uuid4(),
            trigger_type="manual",
            status="success",
            created_by=_ACTOR,
            updated_by=_ACTOR,
        )
        session.add(run)
        await session.flush()
        log = EtlRunLog(
            uid=uuid4(),
            etl_run_pid=run.pid,
            etl_table_pid=None,
            source_schema=schema,
            source_table=table,
            status=status,
            created_by=_ACTOR,
            updated_by=_ACTOR,
        )
        session.add(log)
        await session.commit()


async def _insert_legacy_schedule(
    session_factory: async_sessionmaker[AsyncSession], name: str
) -> None:
    """v1.3.0 遺留「全表增量」排程:source_schema / source_table 皆 NULL。"""
    async with session_factory() as session:
        session.add(
            Schedule(
                uid=uuid4(),
                name=name,
                cron_expr="0 2 * * *",
                is_enabled=True,
                etl_table_pid=None,
                source_schema=None,
                source_table=None,
                description=None,
                created_by=_ACTOR,
                updated_by=_ACTOR,
            )
        )
        await session.commit()


# ── find_by_source_table / upsert_for_source_table ───────────────────────
async def test_upsert_creates_then_does_not_overwrite(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        assert await repo.find_by_source_table("public", "orders") is None
        created = await repo.upsert_for_source_table(
            schema="public",
            table="orders",
            name="public.orders",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert created.source_schema == "public"
        assert created.source_table == "orders"
        assert created.etl_table_pid is None

    # 使用者手動停用並改 cron
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        found = await repo.find_by_source_table("public", "orders")
        assert found is not None
        found.is_enabled = False
        found.cron_expr = "30 5 * * *"
        await session.commit()

    # 再次 upsert(模擬快照)不得覆蓋既有啟停 / cron
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        again = await repo.upsert_for_source_table(
            schema="public",
            table="orders",
            name="public.orders",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert again.is_enabled is False
        assert again.cron_expr == "30 5 * * *"

    # 未重複建立(仍只有一筆未刪除)
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(Schedule).where(
                    Schedule.source_table == "orders",
                    Schedule.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        assert len(rows) == 1


# ── soft_delete_by_source_tables_absent ──────────────────────────────────
async def test_soft_delete_absent_source_tables(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        for tbl in ("a", "b", "c"):
            await repo.upsert_for_source_table(
                schema="public",
                table=tbl,
                name=f"public.{tbl}",
                cron_expr="0 2 * * *",
                is_enabled=True,
                actor_uid=_ACTOR,
            )
        await session.commit()

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        # 只保留 a,b → c 應被軟刪
        deleted = await repo.soft_delete_by_source_tables_absent(
            {("public", "a"), ("public", "b")}, _ACTOR
        )
        await session.commit()
        assert deleted == 1

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        assert await repo.find_by_source_table("public", "c") is None
        assert await repo.find_by_source_table("public", "a") is not None
        # DB 資料仍在(軟刪除)
        row = (
            await session.execute(
                select(Schedule).where(Schedule.source_table == "c")
            )
        ).scalar_one()
        assert row.is_deleted is True


# ── soft_delete_legacy_all_table ─────────────────────────────────────────
async def test_soft_delete_legacy_all_table(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _insert_legacy_schedule(session_factory, "全表增量-1")
    await _insert_legacy_schedule(session_factory, "全表增量-2")
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        # 另建一筆逐表排程(source_schema 非 NULL)不應被誤刪
        await repo.upsert_for_source_table(
            schema="public",
            table="keep",
            name="public.keep",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        await session.commit()

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        count = await repo.soft_delete_legacy_all_table(_ACTOR)
        await session.commit()
        assert count == 2

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        # 逐表排程仍在
        assert await repo.find_by_source_table("public", "keep") is not None
        remaining_legacy = (
            await session.execute(
                select(Schedule).where(
                    Schedule.source_schema.is_(None),
                    Schedule.is_deleted.is_(False),
                )
            )
        ).scalars().all()
        assert remaining_legacy == []


# ── list_tables_view ─────────────────────────────────────────────────────
async def test_list_tables_view_reflects_latest_log_status(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _snapshot(session_factory, schema="public", table="t1", row_count=10)
    # 先 failed 後 success → 最新應為 success
    await _insert_log(session_factory, schema="public", table="t1", status="failed")
    await _insert_log(session_factory, schema="public", table="t1", status="success")

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50
        )
        assert total == 1
        row = rows[0]
        assert row.table_name == "t1"
        assert row.row_count == 10
        assert row.last_run_status == "success"
        # 無排程 → schedule 欄位為 NULL
        assert row.schedule_uid is None
        assert row.is_enabled is None


async def test_list_tables_view_filters(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # 三張表:enabled 排程 / disabled 排程 / 無排程
    await _snapshot(
        session_factory, schema="public", table="orders", business_name="訂單"
    )
    await _snapshot(
        session_factory, schema="public", table="items", business_name="品項"
    )
    await _snapshot(
        session_factory, schema="public", table="logs", business_name="日誌"
    )
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        s_on = await repo.upsert_for_source_table(
            schema="public",
            table="orders",
            name="public.orders",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        s_off = await repo.upsert_for_source_table(
            schema="public",
            table="items",
            name="public.items",
            cron_expr="0 3 * * *",
            is_enabled=False,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert s_on.is_enabled is True
        assert s_off.is_enabled is False

    # 加最新結果:orders=success, items=failed, logs 無 log
    await _insert_log(session_factory, schema="public", table="orders", status="success")
    await _insert_log(session_factory, schema="public", table="items", status="failed")

    async with session_factory() as session:
        repo = ScheduleRepository(session)

        # enabled 篩選
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, enabled="enabled"
        )
        assert total == 1 and rows[0].table_name == "orders"

        # disabled 篩選(含 items 與無排程的 logs)
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, enabled="disabled"
        )
        assert total == 2
        assert {r.table_name for r in rows} == {"items", "logs"}

        # last_result=success
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, last_result="success"
        )
        assert total == 1 and rows[0].table_name == "orders"

        # last_result=failed
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, last_result="failed"
        )
        assert total == 1 and rows[0].table_name == "items"

        # last_result=never(logs 無任何 log)
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, last_result="never"
        )
        assert total == 1 and rows[0].table_name == "logs"

        # keyword 命中 business_name
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, keyword="訂單"
        )
        assert total == 1 and rows[0].table_name == "orders"

        # keyword 命中 table_name
        rows, total = await repo.list_tables_view(
            schema="public", offset=0, limit=50, keyword="item"
        )
        assert total == 1 and rows[0].table_name == "items"


# ── list_schema_summaries ────────────────────────────────────────────────
async def test_list_schema_summaries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _snapshot(session_factory, schema="public", table="a")
    await _snapshot(session_factory, schema="public", table="b")
    await _snapshot(session_factory, schema="sales", table="c")
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        await repo.upsert_for_source_table(
            schema="public",
            table="a",
            name="public.a",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        await repo.upsert_for_source_table(
            schema="public",
            table="b",
            name="public.b",
            cron_expr="0 2 * * *",
            is_enabled=False,
            actor_uid=_ACTOR,
        )
        await session.commit()

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        summaries = await repo.list_schema_summaries()
        assert summaries == [("public", 2, 1), ("sales", 1, 0)]


# ── batch_set_enabled ────────────────────────────────────────────────────
async def test_batch_set_enabled_affected_count(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        repo = ScheduleRepository(session)
        for tbl in ("a", "b"):
            await repo.upsert_for_source_table(
                schema="public",
                table=tbl,
                name=f"public.{tbl}",
                cron_expr="0 2 * * *",
                is_enabled=True,
                actor_uid=_ACTOR,
            )
        await repo.upsert_for_source_table(
            schema="sales",
            table="c",
            name="sales.c",
            cron_expr="0 2 * * *",
            is_enabled=True,
            actor_uid=_ACTOR,
        )
        await session.commit()

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        # 停用 public schema 的 2 張 → 影響 2
        changed = await repo.batch_set_enabled(
            schema="public",
            enabled=False,
            only_source_tables=True,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert changed == 2

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        # 已停用者再停用 → 無變更(0)
        changed = await repo.batch_set_enabled(
            schema="public",
            enabled=False,
            only_source_tables=True,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert changed == 0

        # 全部 schema 啟用 → public 2 + sales 1(sales 本已啟用不變)= 只影響 2
        changed = await repo.batch_set_enabled(
            schema=None,
            enabled=True,
            only_source_tables=True,
            actor_uid=_ACTOR,
        )
        await session.commit()
        assert changed == 2

    async with session_factory() as session:
        repo = ScheduleRepository(session)
        assert (await repo.find_by_source_table("public", "a")).is_enabled is True
        assert (await repo.find_by_source_table("sales", "c")).is_enabled is True
