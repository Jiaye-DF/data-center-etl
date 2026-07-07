"""task-004 增量同步整合測試(真實 PostgreSQL 測試 DB;mirror 以 fake 注入,不打 RDS)。

涵蓋 mirror_sync 的增量偵測 / 全量分支(v1.3.1 起排除語意改由排程 is_enabled 決定,
不再由 mirror_sync 讀 sync_excluded;逐表 tables 派工另見 test_mirror_sync_tables_v131):
1. 首次(baseline None)→ 全部被灌 + signature 寫入。
2. 第二次無異動(baseline == current)→ 全部 skip,last_synced_at 不更新。
3. 某表計數器增加 → 該表被灌、其餘 skip。
4. 計數器倒退 / 重置(current < baseline)→ 該表被判定變動、被灌。
5. incremental=False 全量 → 忽略偵測,全部被灌,signature 仍更新。
6. trigger_type="schedule" + schedule_pid → 建立的 run 帶正確觸發資訊。
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
from app.core import db as core_db  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.etl.mirror import TableStat  # noqa: E402
from app.models.etl_run import EtlRun  # noqa: E402
from app.models.etl_run_log import EtlRunLog  # noqa: E402
from app.models.rds_table_meta import Dataset, RdsTableMeta  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from app.worker import tasks  # noqa: E402


# ── fixtures(對齊 test_sync_api.py:真實測試 DB)────────────────────────
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
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM rds_table_meta"))


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine() -> AsyncIterator[None]:
    # mirror_sync(taskiq 就地執行)走全域 engine 連線池;
    # pytest-asyncio 每測試換 event loop,不釋放會跨 loop 重用連線而失敗
    yield
    await core_db.engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


# ── fake mirror(不打 RDS,計數器可控)──────────────────────────────────
class FakeMirror:
    """結構相容 MirrorEngine:fetch_source_stats 回可控計數器,mirror_table 記錄被灌表。"""

    def __init__(
        self, stats: dict[tuple[str, str], TableStat], *, written: int = 3
    ) -> None:
        self._stats = stats
        self._written = written
        self.mirrored: list[tuple[str, str]] = []
        self.disposed = False

    async def list_source_tables(self) -> list[tuple[str, str]]:
        return sorted(self._stats.keys())

    async def fetch_source_stats(self) -> dict[tuple[str, str], TableStat]:
        return dict(self._stats)

    async def mirror_table(
        self, schema: str, table: str, *, batch_size: int = 1000
    ) -> int:
        self.mirrored.append((schema, table))
        return self._written

    async def dispose(self) -> None:
        self.disposed = True


# ── helpers ─────────────────────────────────────────────────────────────
async def _seed_meta(
    session_factory: async_sessionmaker[AsyncSession],
    schema: str,
    table: str,
    *,
    baseline: tuple[int, int, int] | None = None,
    sync_excluded: bool = False,
    last_synced_at: datetime | None = None,
) -> None:
    """插入一筆 SOURCE 快照,可設 signature 基準 / 排除旗標 / 既有同步時間。"""
    actor = uuid4()
    ins, upd, dele = baseline if baseline is not None else (None, None, None)
    async with session_factory() as session:
        session.add(
            RdsTableMeta(
                uid=uuid4(),
                dataset=Dataset.SOURCE,
                schema_name=schema,
                table_name=table,
                column_count=3,
                row_count=0,
                snapshot_at=datetime(2026, 7, 3, 2, 0, 0),
                last_synced_at=last_synced_at,
                last_stat_ins=ins,
                last_stat_upd=upd,
                last_stat_del=dele,
                sync_excluded=sync_excluded,
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


async def _get_meta(
    session_factory: async_sessionmaker[AsyncSession], schema: str, table: str
) -> RdsTableMeta:
    async with session_factory() as session:
        return (
            await session.execute(
                select(RdsTableMeta).where(
                    RdsTableMeta.dataset == Dataset.SOURCE,
                    RdsTableMeta.schema_name == schema,
                    RdsTableMeta.table_name == table,
                )
            )
        ).scalar_one()


async def _run_log_statuses(
    session_factory: async_sessionmaker[AsyncSession], run_pid: int
) -> list[tuple[str, str]]:
    """回該 run 逐表 log 的 (table, status)。"""
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(EtlRunLog.source_table, EtlRunLog.status).where(
                    EtlRunLog.etl_run_pid == run_pid
                )
            )
        ).all()
    return [(str(t), str(s)) for t, s in rows]


async def _get_run(
    session_factory: async_sessionmaker[AsyncSession], run_pid: int
) -> EtlRun:
    async with session_factory() as session:
        return (
            await session.execute(select(EtlRun).where(EtlRun.pid == run_pid))
        ).scalar_one()


async def _invoke(
    monkeypatch: pytest.MonkeyPatch, fake: FakeMirror, **kwargs: object
) -> dict[str, object]:
    """monkeypatch make_mirror → fake,enqueue mirror_sync(InMemoryBroker 就地執行)。"""
    monkeypatch.setattr(tasks, "make_mirror", lambda: fake)
    task = await tasks.mirror_sync.kiq(**kwargs)
    result = await task.wait_result(timeout=10)
    assert not result.is_err, result.error
    return result.return_value


# ── 1. 首次(baseline None)→ 全部被灌 + signature 寫入 ───────────────────
async def test_first_run_no_baseline_mirrors_all(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_meta(session_factory, "DS", "AAA_FILE", baseline=None)
    await _seed_meta(session_factory, "DS", "BBB_FILE", baseline=None)
    stats = {
        ("DS", "AAA_FILE"): TableStat(10, 2, 1),
        ("DS", "BBB_FILE"): TableStat(5, 0, 0),
    }
    fake = FakeMirror(stats, written=7)

    ret = await _invoke(monkeypatch, fake, incremental=True)

    assert fake.mirrored == [("DS", "AAA_FILE"), ("DS", "BBB_FILE")]
    assert ret["success_tables"] == 2
    assert ret["skipped_tables"] == 0
    # signature 基準寫入為當下來源計數器
    meta = await _get_meta(session_factory, "DS", "AAA_FILE")
    assert (meta.last_stat_ins, meta.last_stat_upd, meta.last_stat_del) == (10, 2, 1)
    assert meta.last_synced_at is not None


# ── 2. 第二次無異動 → 全部 skip,last_synced_at 不更新 ─────────────────────
async def test_second_run_unchanged_skips_all(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_meta(
        session_factory, "DS", "AAA_FILE", baseline=(10, 2, 1), last_synced_at=None
    )
    stats = {("DS", "AAA_FILE"): TableStat(10, 2, 1)}
    fake = FakeMirror(stats)

    ret = await _invoke(monkeypatch, fake, incremental=True)

    assert fake.mirrored == []
    assert ret["skipped_tables"] == 1
    assert ret["success_tables"] == 0
    assert await _run_log_statuses(session_factory, ret["run_pid"]) == [
        ("AAA_FILE", "skipped")
    ]
    # 未變動 → 不重灌、last_synced_at 保持原樣(None)
    meta = await _get_meta(session_factory, "DS", "AAA_FILE")
    assert meta.last_synced_at is None


# ── 3. 某表計數器增加 → 該表被灌、其餘 skip ──────────────────────────────
async def test_only_changed_table_mirrored(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_meta(session_factory, "DS", "AAA_FILE", baseline=(10, 0, 0))
    await _seed_meta(session_factory, "DS", "BBB_FILE", baseline=(5, 0, 0))
    stats = {
        ("DS", "AAA_FILE"): TableStat(10, 0, 0),  # 未變動
        ("DS", "BBB_FILE"): TableStat(8, 0, 0),  # n_tup_ins 增加 → 變動
    }
    fake = FakeMirror(stats)

    ret = await _invoke(monkeypatch, fake, incremental=True)

    assert fake.mirrored == [("DS", "BBB_FILE")]
    assert ret["success_tables"] == 1
    assert ret["skipped_tables"] == 1
    # 被灌表 signature 前進;未灌表 signature 不動
    changed = await _get_meta(session_factory, "DS", "BBB_FILE")
    assert changed.last_stat_ins == 8
    unchanged = await _get_meta(session_factory, "DS", "AAA_FILE")
    assert unchanged.last_stat_ins == 10


# ── 4. 計數器倒退 / 重置(current < baseline)→ 被判定變動、被灌 ──────────
async def test_counter_reset_treated_as_changed(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _seed_meta(session_factory, "DS", "AAA_FILE", baseline=(100, 20, 5))
    stats = {("DS", "AAA_FILE"): TableStat(3, 0, 0)}  # 來源重啟 / pg_stat_reset
    fake = FakeMirror(stats)

    ret = await _invoke(monkeypatch, fake, incremental=True)

    assert fake.mirrored == [("DS", "AAA_FILE")]
    assert ret["success_tables"] == 1
    meta = await _get_meta(session_factory, "DS", "AAA_FILE")
    assert (meta.last_stat_ins, meta.last_stat_upd, meta.last_stat_del) == (3, 0, 0)


# ── 5. incremental=False 全量 → 忽略偵測,全部被灌,signature 仍更新 ──
async def test_full_sync_ignores_detection_and_exclusion(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # AAA 無異動(baseline==current);BBB 被排除;全量模式兩者皆應被灌
    await _seed_meta(session_factory, "DS", "AAA_FILE", baseline=(10, 0, 0))
    await _seed_meta(
        session_factory, "DS", "BBB_FILE", baseline=(5, 0, 0), sync_excluded=True
    )
    stats = {
        ("DS", "AAA_FILE"): TableStat(10, 0, 0),
        ("DS", "BBB_FILE"): TableStat(5, 0, 0),
    }
    fake = FakeMirror(stats)

    ret = await _invoke(monkeypatch, fake, incremental=False)

    assert fake.mirrored == [("DS", "AAA_FILE"), ("DS", "BBB_FILE")]
    assert ret["success_tables"] == 2
    assert ret["skipped_tables"] == 0
    # 全量仍刷新 signature 基準
    meta = await _get_meta(session_factory, "DS", "BBB_FILE")
    assert meta.last_stat_ins == 5
    assert meta.last_synced_at is not None


# ── 7. trigger_type="schedule" + schedule_pid → run 帶正確觸發資訊 ─────────
async def test_schedule_trigger_carries_run_metadata(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor = uuid4()
    async with session_factory() as session:
        schedule = Schedule(
            uid=uuid4(),
            name="增量排程",
            cron_expr="0 2 * * *",
            is_enabled=True,
            created_by=actor,
            updated_by=actor,
        )
        session.add(schedule)
        await session.commit()
        schedule_pid = schedule.pid

    await _seed_meta(session_factory, "DS", "AAA_FILE", baseline=None)
    fake = FakeMirror({("DS", "AAA_FILE"): TableStat(1, 0, 0)})

    ret = await _invoke(
        monkeypatch,
        fake,
        incremental=True,
        trigger_type="schedule",
        schedule_pid=schedule_pid,
    )

    run = await _get_run(session_factory, ret["run_pid"])
    assert run.trigger_type == "schedule"
    assert run.schedule_pid == schedule_pid
