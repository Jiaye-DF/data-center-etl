"""task-003(propose A5)語意映射副本表 + 同步回流測試。

涵蓋 Acceptance 三點:
1. `SemanticMappingRepository.replace_all` 整表重灌後副本 = 來源(含二次重灌覆蓋舊列)。
2. 來源(RDS `erp_metadata.semantic_mappings`)缺表 → graceful 略過,不 fail job。
3. worker `mirror_sync` 完成階段呼叫 `replace_all` 後,語意映射快取失效有被呼叫。

對齊 `test_mirror_sync_incremental.py`(真實測試 DB + FakeMirror 注入,不打真 RDS)與
`test_semantic_schema.py`(env 指向共用本地測試 DB,不觸碰真正 AWS RDS)兩檔既有模式。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建立 engine;semantic_mappings 連線沿用 AWS_RDS_*(見 reader.py),
# 測試指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
_TEST_DB_NAME = "data_center_etl_test"
# 獨立、從未執行過 ensure_semantic_schema 的空白 DB:保證 erp_metadata.semantic_mappings
# 恆不存在,供「來源缺表 graceful」測試決定性驗證(禁 DROP,故不重用共用測試 DB 反覆造假)。
_ISOLATED_DB_NAME = "data_center_etl_test_semantic_missing"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
TEST_DATABASE_URL = f"{_BASE_URL}/{_TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

import logging  # noqa: E402
from collections.abc import AsyncIterator  # noqa: E402
from datetime import datetime  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

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

from app.core import db as core_db  # noqa: E402
from app.core import redis as cache_module  # noqa: E402
from app.etl import semantic_autofill  # noqa: E402
from app.etl.comments import quote_ident  # noqa: E402
from app.etl.mirror import TableStat  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.semantic_autofill import AutofillResult  # noqa: E402
from app.etl.semantic_schema import (  # noqa: E402
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402
from app.models.semantic_mapping import SemanticMapping  # noqa: E402
from app.repositories.semantic_mapping_repo import (  # noqa: E402
    SemanticMappingRepository,
    SemanticMappingRow,
)
from app.worker import tasks  # noqa: E402

_QUALIFIED_SOURCE = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

# 來源端 updated_by 為 uuid(v1.5.1 fixed #3)
_SOURCE_ACTOR = UUID("11111111-1111-1111-1111-111111111111")

_INSERT_SOURCE_SQL = text(
    f"INSERT INTO {_QUALIFIED_SOURCE}"
    " (table_name, column_name, english_name, zh_name, status, updated_by)"
    " VALUES (:t, :c, :e, :z, :s, :u)"
)


# ── fixtures(共用測試 DB 建置沿用 conftest.py 的 _prepare_shared_test_db)────────
@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """指向共用測試 DB 的 RDS「目標」engine(語意映射來源實際所在)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(db_engine: AsyncEngine, target_engine: AsyncEngine) -> None:
    """每測試前清空副本表(自有 DB)與來源表(若存在);非 DROP,對齊既有清理策略。"""
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM semantic_mappings"))
    async with target_engine.begin() as conn:
        exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.tables"
                    " WHERE table_schema = :s AND table_name = :t"
                ),
                {"s": SEMANTIC_SCHEMA, "t": SEMANTIC_TABLE},
            )
        ).first()
        if exists is not None:
            await conn.execute(text(f"DELETE FROM {_QUALIFIED_SOURCE}"))


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine() -> AsyncIterator[None]:
    # mirror_sync(taskiq 就地執行)走全域 engine 連線池;
    # pytest-asyncio 每測試換 event loop,不釋放會跨 loop 重用連線而失敗
    yield
    await core_db.engine.dispose()


# ── fake mirror(不打 RDS)────────────────────────────────────────────────
class FakeMirror:
    """結構相容 MirrorEngine:單表、固定計數器,mirror_table 記錄被灌表。"""

    def __init__(self) -> None:
        self.mirrored: list[tuple[str, str]] = []
        self.disposed = False

    async def list_source_tables(self) -> list[tuple[str, str]]:
        return [("DS", "AAA_FILE")]

    async def fetch_source_stats(self) -> dict[tuple[str, str], TableStat]:
        return {("DS", "AAA_FILE"): TableStat(1, 0, 0)}

    async def mirror_table(
        self, schema: str, table: str, *, batch_size: int = 1000
    ) -> int:
        self.mirrored.append((schema, table))
        return 1

    async def dispose(self) -> None:
        self.disposed = True


async def _invoke(
    monkeypatch: pytest.MonkeyPatch,
    *,
    schema: str | None = None,
    table: str | None = None,
) -> dict[str, object]:
    monkeypatch.setattr(tasks, "make_mirror", lambda: FakeMirror())
    task = await tasks.mirror_sync.kiq(schema=schema, table=table)
    result = await task.wait_result(timeout=10)
    assert not result.is_err, result.error
    return_value = result.return_value
    assert isinstance(return_value, dict)
    return return_value


async def _seed_own_copy_row(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """在自有 DB 副本表預先塞一列,用來驗證「缺表 graceful」時副本不被動到。"""
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            SemanticMapping(
                uid=uuid4(),
                table_name="PRESEEDED_FILE",
                column_name="",
                english_name="preseeded_file",
                status="draft",
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


# ── 1. replace_all 整表重灌後副本 = 來源 ───────────────────────────────────
async def test_replace_all_matches_source_and_full_refresh(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    actor = uuid4()
    first_rows = [
        SemanticMappingRow(
            table_name="ZZZ_TASK003_FILE",
            column_name="",
            english_name="zzz_task003_file",
            zh_name=None,
            status="draft",
            source_updated_by=_SOURCE_ACTOR,
            source_updated_at=None,
        ),
        SemanticMappingRow(
            table_name="ZZZ_TASK003_FILE",
            column_name="ZZZ01",
            english_name="account_no",
            zh_name="帳號",
            status="confirmed",
            source_updated_by=_SOURCE_ACTOR,
            source_updated_at=datetime(2026, 7, 1, 10, 0, 0),
        ),
    ]
    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        written = await repo.replace_all(first_rows, actor_uid=actor)
    assert written == 2

    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        confirmed = await repo.get_confirmed_map("ZZZ_TASK003_FILE")
    assert confirmed == {"ZZZ01": "account_no"}

    async with session_factory() as session:
        rows = (
            await session.execute(
                select(SemanticMapping).where(
                    SemanticMapping.table_name == "ZZZ_TASK003_FILE"
                )
            )
        ).scalars().all()
    by_column = {r.column_name: r for r in rows}
    assert by_column["ZZZ01"].zh_name == "帳號"
    assert by_column["ZZZ01"].source_updated_at == datetime(2026, 7, 1, 10, 0, 0)
    assert by_column[""].status == "draft"

    # 二次重灌(較少列)→ 舊列被整批清除,副本恆等於本次來源全量(非累加 upsert)
    second_rows = [
        SemanticMappingRow(
            table_name="ZZZ_TASK003_FILE",
            column_name="ZZZ02",
            english_name="account_name",
            zh_name="戶名",
            status="confirmed",
            source_updated_by=_SOURCE_ACTOR,
            source_updated_at=None,
        ),
    ]
    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        written = await repo.replace_all(second_rows, actor_uid=actor)
    assert written == 1

    async with session_factory() as session:
        remaining = (
            await session.execute(select(SemanticMapping.column_name))
        ).scalars().all()
    assert set(remaining) == {"ZZZ02"}


# ── 2. 來源缺表 graceful:worker 不 fail、副本不被動、語意快取未失效 ─────────
async def test_source_table_missing_is_graceful(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _seed_own_copy_row(session_factory)

    invalidated: list[str] = []

    async def _fake_delete_pattern(pattern: str) -> None:
        invalidated.append(pattern)

    async def _fake_fetch_returns_none() -> list[SemanticMappingRow] | None:
        # 模擬「讀取回 None」(涵蓋來源表不存在 / 環境未備妥兩種 graceful 情境)
        return None

    async def _noop_autofill(target: object, source: object) -> AutofillResult:
        # 本測試聚焦副本重灌 graceful,非 autofill;中和 task-003 autofill 免打真身表
        return AutofillResult()

    monkeypatch.setattr(cache_module, "delete_pattern", _fake_delete_pattern)
    monkeypatch.setattr(tasks, "_fetch_semantic_mapping_rows", _fake_fetch_returns_none)
    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _noop_autofill)

    with caplog.at_level(logging.WARNING, logger="app.worker.tasks"):
        ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")

    assert ret["status"] == "success"
    assert any("語意映射" in message for message in caplog.messages)
    assert not any(p.startswith("data-center-etl:semantic-mappings") for p in invalidated)

    async with session_factory() as session:
        remaining = (
            await session.execute(select(SemanticMapping.table_name))
        ).scalars().all()
    assert remaining == ["PRESEEDED_FILE"]


# ── 2b. AD-120:手動套用持鎖中 → mirror_sync 收尾略過本輪副本重灌(不 fail run)──
async def test_mirror_sync_skips_semantic_refresh_when_apply_locked(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    refresh_calls: list[bool] = []

    async def _spy_refresh(session: object) -> None:
        refresh_calls.append(True)

    monkeypatch.setattr(tasks, "refresh_semantic_copy_and_views", _spy_refresh)

    assert await tasks.acquire_apply_lock() is True
    try:
        with caplog.at_level(logging.INFO, logger="app.worker.tasks"):
            ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")
    finally:
        await tasks.release_apply_lock()

    assert ret["status"] == "success"
    assert refresh_calls == []
    assert any(
        "略過本輪語意映射自動補列與副本重灌" in message for message in caplog.messages
    )


# ── 3. mirror_sync 完成階段呼叫 replace_all + 語意映射快取失效被呼叫 ────────
async def test_mirror_sync_replaces_mapping_and_invalidates_cache(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    fetched_rows = [
        SemanticMappingRow(
            table_name="ZZZ_TASK003_FILE",
            column_name="",
            english_name="zzz_task003_file",
            zh_name=None,
            status="draft",
            source_updated_by=_SOURCE_ACTOR,
            source_updated_at=None,
        ),
    ]

    async def _fake_fetch() -> list[SemanticMappingRow] | None:
        return fetched_rows

    hook_calls: list[bool] = []

    async def _fake_hook(
        session: object, repo: object, on_progress: object = None
    ) -> None:
        hook_calls.append(True)

    invalidated: list[str] = []

    async def _fake_delete_pattern(pattern: str) -> None:
        invalidated.append(pattern)

    async def _noop_autofill(target: object, source: object) -> AutofillResult:
        # 本測試聚焦副本重灌 + 快取失效,非 autofill;中和 task-003 autofill 免打真身表
        return AutofillResult()

    monkeypatch.setattr(tasks, "_fetch_semantic_mapping_rows", _fake_fetch)
    monkeypatch.setattr(tasks, "regenerate_views_if_changed", _fake_hook)
    monkeypatch.setattr(cache_module, "delete_pattern", _fake_delete_pattern)
    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _noop_autofill)

    ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")

    assert ret["status"] == "success"
    assert hook_calls == [True]
    assert any(p.startswith("data-center-etl:semantic-mappings") for p in invalidated)

    async with session_factory() as session:
        rows = (
            await session.execute(select(SemanticMapping.table_name))
        ).scalars().all()
    assert rows == ["ZZZ_TASK003_FILE"]


# ── 4. _fetch_semantic_mapping_rows 本體:來源存在 → 正確轉出;來源不存在 → None ──
async def test_fetch_semantic_mapping_rows_reads_source_table(
    target_engine: AsyncEngine,
) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
        await conn.execute(
            _INSERT_SOURCE_SQL,
            {
                "t": "ZZZ_TASK003_FILE",
                "c": "ZZZ01",
                "e": "account_no",
                "z": "帳號",
                "s": "confirmed",
                "u": _SOURCE_ACTOR,
            },
        )

    rows = await tasks._fetch_semantic_mapping_rows()

    assert rows is not None
    matched = [r for r in rows if r.table_name == "ZZZ_TASK003_FILE"]
    assert len(matched) == 1
    row = matched[0]
    assert row.column_name == "ZZZ01"
    assert row.english_name == "account_no"
    assert row.zh_name == "帳號"
    assert row.status == "confirmed"
    assert row.source_updated_by == _SOURCE_ACTOR
    assert row.source_updated_at is not None
    assert row.source_updated_at.tzinfo is None


async def test_fetch_semantic_mapping_rows_returns_none_when_source_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """獨立、從未跑過 ensure_semantic_schema 的空白 DB → 保證來源表不存在,回 None。"""
    admin_engine = create_async_engine(
        ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            exists = (
                await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": _ISOLATED_DB_NAME},
                )
            ).scalar()
            if exists is None:
                await conn.execute(text(f'CREATE DATABASE "{_ISOLATED_DB_NAME}"'))
    finally:
        await admin_engine.dispose()

    monkeypatch.setenv("AWS_RDS_TARGET_DB", _ISOLATED_DB_NAME)

    result = await tasks._fetch_semantic_mapping_rows()

    assert result is None


# ── task-003 掛接:autofill → 副本重灌 → view 重生同輪生效(Acceptance 四情境)──────
async def _ensure_isolated_missing_db() -> None:
    """建立獨立空白 DB(從未跑過 ensure_semantic_schema)→ 保證真身表恆不存在;非 DROP。"""
    admin_engine = create_async_engine(
        ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
    )
    try:
        async with admin_engine.connect() as conn:
            exists = (
                await conn.execute(
                    text("SELECT 1 FROM pg_database WHERE datname = :n"),
                    {"n": _ISOLATED_DB_NAME},
                )
            ).scalar()
            if exists is None:
                await conn.execute(text(f'CREATE DATABASE "{_ISOLATED_DB_NAME}"'))
    finally:
        await admin_engine.dispose()


# (a) 收尾順序:autofill 先於副本重灌(replace_all)
async def test_mirror_sync_autofill_runs_before_replace_all(
    monkeypatch: pytest.MonkeyPatch,
    target_engine: AsyncEngine,
) -> None:
    # 真身表存在(冪等建置)→ autofill 前置存在檢查通過,進入補列
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    order: list[str] = []

    async def _spy_autofill(target: object, source: object) -> AutofillResult:
        order.append("autofill")
        return AutofillResult(columns_added=1, tables_added=0, aliases_deduped=0)

    async def _spy_refresh(session: object) -> None:
        order.append("replace_all")

    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _spy_autofill)
    monkeypatch.setattr(tasks, "refresh_semantic_copy_and_views", _spy_refresh)

    ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")

    assert ret["status"] == "success"
    assert order == ["autofill", "replace_all"]


# (b) 真身表不存在 → 略過 autofill,不 fail run,且不呼叫 autofill 本體
async def test_mirror_sync_autofill_skipped_when_mapping_table_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    await _ensure_isolated_missing_db()
    monkeypatch.setenv("AWS_RDS_TARGET_DB", _ISOLATED_DB_NAME)

    called: list[bool] = []

    async def _spy_autofill(target: object, source: object) -> AutofillResult:
        called.append(True)
        return AutofillResult()

    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _spy_autofill)

    with caplog.at_level(logging.WARNING, logger="app.worker.tasks"):
        ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")

    assert ret["status"] == "success"
    assert called == []
    assert any("略過語意映射自動補列" in message for message in caplog.messages)


# (c) autofill 拋例外 → warning 後既有副本重灌照跑(不因補列失敗擋收尾)
async def test_mirror_sync_autofill_exception_still_triggers_refresh(
    monkeypatch: pytest.MonkeyPatch,
    target_engine: AsyncEngine,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    refresh_calls: list[bool] = []

    async def _boom_autofill(target: object, source: object) -> AutofillResult:
        raise RuntimeError("autofill boom")

    async def _spy_refresh(session: object) -> None:
        refresh_calls.append(True)

    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _boom_autofill)
    monkeypatch.setattr(tasks, "refresh_semantic_copy_and_views", _spy_refresh)

    with caplog.at_level(logging.WARNING, logger="app.worker.tasks"):
        ret = await _invoke(monkeypatch, schema="DS", table="AAA_FILE")

    assert ret["status"] == "success"
    assert refresh_calls == [True]
    assert any("語意映射自動補列失敗" in message for message in caplog.messages)


# (d) semantic_apply(手動套用變更)路徑不掛 autofill
async def test_semantic_apply_does_not_call_autofill(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    async def _spy_autofill(target: object, source: object) -> AutofillResult:
        called.append(True)
        return AutofillResult()

    async def _fake_fetch_none() -> list[SemanticMappingRow] | None:
        return None

    monkeypatch.setattr(semantic_autofill, "autofill_semantic_mappings", _spy_autofill)
    monkeypatch.setattr(tasks, "_fetch_semantic_mapping_rows", _fake_fetch_none)

    task = await tasks.semantic_apply.kiq()
    result = await task.wait_result(timeout=10)
    assert not result.is_err, result.error
    assert called == []
