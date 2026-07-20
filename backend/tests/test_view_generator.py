"""語意化 view 產生器測試(task-005,propose A4)。

純函式(分組 / 簽名 / 欄位交集 / SELECT 組裝)以無 DB 單元測試涵蓋;實際 DDL 行為
(CREATE VIEW / information_schema 內省)無法用 fake 驗證,對齊 test_semantic_schema.py /
test_mirror_sync_incremental.py 模式:連真實本地 PostgreSQL 測試 DB(同時扮演「本地副本
DB」與「目標 RDS」雙重角色,與既有測試慣例一致),不觸碰真正 AWS RDS。

測試建立的帳套 schema / 表 / view 一律用 `CREATE ... IF NOT EXISTS` / `CREATE OR REPLACE
VIEW`,teardown 僅清資料(TRUNCATE)不刪結構(禁 DROP SCHEMA / DROP TABLE)。
"""

from __future__ import annotations

import asyncio
import os
from uuid import uuid4

# app 模組於 import 時即讀 env 建立 engine;連線沿用 AWS_RDS_*(見 reader.py)+ 本地 DATABASE_URL,
# 皆指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS(對齊 test_semantic_schema.py)
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
_TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
_ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
_TEST_DATABASE_URL = f"{_BASE_URL}/{_TEST_DB_NAME}"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ["DATABASE_URL"] = _TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.core import redis as cache  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.etl import view_generator  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402
from app.models.semantic_mapping import SemanticMapping  # noqa: E402
from app.repositories.semantic_mapping_repo import SemanticMappingRepository  # noqa: E402

# ── fixtures:真實測試 DB(對齊 test_mirror_sync_incremental.py)───────────


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)並以 metadata 建 schema;不對既有 DB 做任何 DROP。"""

    async def _prepare() -> None:
        admin_engine = create_async_engine(
            _ADMIN_DATABASE_URL, poolclass=NullPool, isolation_level="AUTOCOMMIT"
        )
        try:
            async with admin_engine.connect() as conn:
                exists = (
                    await conn.execute(
                        text("SELECT 1 FROM pg_database WHERE datname = :name"),
                        {"name": _TEST_DB_NAME},
                    )
                ).scalar()
                if exists is None:
                    await conn.execute(text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
        finally:
            await admin_engine.dispose()

        test_engine = create_async_engine(_TEST_DATABASE_URL, poolclass=NullPool)
        try:
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        finally:
            await test_engine.dispose()

    asyncio.run(_prepare())


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    """本地副本 DB engine(存放 confirmed/draft 映射)。"""
    engine = create_async_engine(_TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """目標 RDS 測試替身(同一實體 DB,扮演「帳套 schema 所在的目標 RDS」角色)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每測試重置 redis 記憶體 fake(避免簽名快取跨測試髒讀,對齊 test_snapshot_module_code.py)。"""
    cache._client = None


@pytest_asyncio.fixture(autouse=True)
async def _clean_semantic_mappings(db_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試前後清空本地副本映射資料(非 DROP)。"""
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM semantic_mappings"))
    yield
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM semantic_mappings"))


async def _seed_mapping(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    table_name: str,
    column_name: str,
    english_name: str,
    status: str,
) -> None:
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            SemanticMapping(
                uid=uuid4(),
                table_name=table_name,
                column_name=column_name,
                english_name=english_name,
                status=status,
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


async def _ensure_source_table(
    target_engine: AsyncEngine, schema: str, table: str, columns: dict[str, str]
) -> None:
    """建立測試用帳套 schema / 表(冪等,禁 DROP);`columns` 為 `{欄名: DDL 型別}`。"""
    col_defs = ", ".join(f'"{col}" {ddl}' for col, ddl in columns.items())
    async with target_engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" ({col_defs})'))
        await conn.execute(text(f'TRUNCATE TABLE "{schema}"."{table}"'))
        placeholders = ", ".join(f":{col}" for col in columns)
        col_list = ", ".join(f'"{col}"' for col in columns)
        await conn.execute(
            text(f'INSERT INTO "{schema}"."{table}" ({col_list}) VALUES ({placeholders})'),
            {col: f"v-{col}" for col in columns},
        )


# =============================================================================
# 純函式單元測試(免連線)
# =============================================================================


def test_group_confirmed_rows_groups_by_table() -> None:
    rows = [
        ("VG_MASTER", "", "employee_master"),
        ("VG_MASTER", "VGA01", "employee_number"),
        ("VG_MASTER", "VGA02", "employee_name"),
        ("VG_OTHER", "", "other_master"),
    ]
    grouped = view_generator.group_confirmed_rows(rows)
    assert grouped == {
        "VG_MASTER": {
            "": "employee_master",
            "VGA01": "employee_number",
            "VGA02": "employee_name",
        },
        "VG_OTHER": {"": "other_master"},
    }


def test_compute_confirmed_signature_stable_and_order_independent() -> None:
    a = {"T1": {"": "t1_view", "C1": "c1"}, "T2": {"": "t2_view"}}
    b = {"T2": {"": "t2_view"}, "T1": {"C1": "c1", "": "t1_view"}}
    sig_a = view_generator.compute_confirmed_signature(a)
    sig_b = view_generator.compute_confirmed_signature(b)
    assert sig_a == sig_b


def test_compute_confirmed_signature_changes_on_content_diff() -> None:
    a = {"T1": {"": "t1_view", "C1": "c1"}}
    b = {"T1": {"": "t1_view", "C1": "c1_renamed"}}
    sig_a = view_generator.compute_confirmed_signature(a)
    sig_b = view_generator.compute_confirmed_signature(b)
    assert sig_a != sig_b


def test_select_view_columns_intersection_preserves_table_order() -> None:
    table_columns = ["VGA03", "VGA01", "VGA02"]
    table_map = {"": "employee_master", "VGA01": "employee_number", "VGA02": "employee_name"}
    result = view_generator.select_view_columns(table_columns, table_map)
    # VGA03 不在 confirmed → 排除;'' 表層級鍵不應出現在欄位別名;依表實際欄位順序
    assert list(result.items()) == [("VGA01", "employee_number"), ("VGA02", "employee_name")]


def test_select_view_columns_empty_intersection() -> None:
    table_columns = ["ZZ01", "ZZ02"]
    table_map = {"": "some_view", "VGA01": "employee_number"}
    assert view_generator.select_view_columns(table_columns, table_map) == {}


def test_build_view_select_sql_quotes_identifiers_and_aliases() -> None:
    sql = view_generator.build_view_select_sql(
        "VG_TEST", "VG_MASTER", {"VGA01": "employee_number", "VGA02": "employee_name"}
    )
    assert sql == (
        'SELECT "VGA01" AS "employee_number", "VGA02" AS "employee_name" '
        'FROM "VG_TEST"."VG_MASTER"'
    )


# =============================================================================
# 真實 DB 整合測試:generate_views_for_schema / generate_views
# =============================================================================


async def test_confirmed_table_produces_view_with_english_aliases(
    target_engine: AsyncEngine,
) -> None:
    await _ensure_source_table(
        target_engine,
        "VG_TEST",
        "VG_MASTER_ALIAS",
        {"VGA01": "VARCHAR(10)", "VGA02": "VARCHAR(20)", "VGA03": "VARCHAR(20)"},
    )
    confirmed = {
        "VG_MASTER_ALIAS": {
            "": "employee_master_alias",
            "VGA01": "employee_number",
            "VGA02": "employee_name",
            # VGA03 刻意不映射,驗證僅 confirmed 交集欄位進 view
        }
    }
    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        created, failed = await view_generator.generate_views_for_schema(
            conn, "VG_TEST", confirmed
        )
    assert created == ["VG_TEST_en.employee_master_alias"]
    assert failed == []

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(text('SELECT * FROM "VG_TEST_en"."employee_master_alias"'))
        ).mappings().first()
    assert row is not None
    assert set(row.keys()) == {"employee_number", "employee_name"}
    assert row["employee_number"] == "v-VGA01"
    assert row["employee_name"] == "v-VGA02"


async def test_empty_intersection_skips_table_no_view(target_engine: AsyncEngine) -> None:
    await _ensure_source_table(target_engine, "VG_TEST", "VG_EMPTY", {"ZZ01": "VARCHAR(20)"})
    confirmed = {"VG_EMPTY": {"": "empty_view", "VGA99": "not_present_on_table"}}
    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        created, failed = await view_generator.generate_views_for_schema(
            conn, "VG_TEST", confirmed
        )
    assert created == []
    assert failed == []

    async with target_engine.connect() as conn:
        exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.views"
                    " WHERE table_schema = 'VG_TEST_en' AND table_name = 'empty_view'"
                )
            )
        ).first()
    assert exists is None


async def test_rerun_is_idempotent(target_engine: AsyncEngine) -> None:
    await _ensure_source_table(
        target_engine,
        "VG_TEST",
        "VG_MASTER_IDEM",
        {"VGA01": "VARCHAR(10)", "VGA02": "VARCHAR(20)"},
    )
    confirmed = {
        "VG_MASTER_IDEM": {
            "": "employee_master_idem",
            "VGA01": "employee_number",
            "VGA02": "employee_name",
        }
    }
    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        first, first_failed = await view_generator.generate_views_for_schema(
            conn, "VG_TEST", confirmed
        )
        second, second_failed = await view_generator.generate_views_for_schema(
            conn, "VG_TEST", confirmed
        )
    assert first == second == ["VG_TEST_en.employee_master_idem"]
    assert first_failed == second_failed == []


async def test_list_target_schemas_excludes_ds_erp_metadata_and_en_suffix(
    target_engine: AsyncEngine,
) -> None:
    await _ensure_source_table(
        target_engine, "VG_TEST", "VG_SCHEMA_PROBE", {"VGA01": "VARCHAR(10)"}
    )
    await _ensure_source_table(target_engine, "DS", "VG_DS_PROBE", {"C1": "VARCHAR(5)"})
    await _ensure_source_table(target_engine, "erp_metadata", "VG_META_PROBE", {"C1": "VARCHAR(5)"})
    await _ensure_source_table(target_engine, "VG_TEST_en", "VG_EN_PROBE", {"C1": "VARCHAR(5)"})

    async with target_engine.connect() as conn:
        schemas = await view_generator._list_target_schemas(conn)

    assert "VG_TEST" in schemas
    assert "DS" not in schemas
    assert "erp_metadata" not in schemas
    assert "VG_TEST_en" not in schemas


# =============================================================================
# 真實 DB 整合測試:_create_or_replace_view 重建分支收斂(AD-112)
# =============================================================================


async def test_create_or_replace_view_incompatible_columns_triggers_rebuild(
    target_engine: AsyncEngine,
) -> None:
    """既有 view 欄位別名改變(Postgres 拒絕 REPLACE,42P16)→ 觸發 DROP VIEW + CREATE 重建。"""
    await _ensure_source_table(target_engine, "VG_TEST", "VG_REBUILD", {"VGA01": "VARCHAR(10)"})
    qualified = '"VG_TEST_en"."vg_rebuild"'
    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "VG_TEST_en"'))
        await view_generator._create_or_replace_view(
            conn, qualified, 'SELECT "VGA01" AS "old_alias" FROM "VG_TEST"."VG_REBUILD"'
        )
        # 欄位別名改變 = 欄位集合不相容,Postgres 拒絕 REPLACE → 應觸發重建
        await view_generator._create_or_replace_view(
            conn, qualified, 'SELECT "VGA01" AS "new_alias" FROM "VG_TEST"."VG_REBUILD"'
        )

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(text('SELECT * FROM "VG_TEST_en"."vg_rebuild"'))
        ).mappings().first()
    assert row is not None
    assert set(row.keys()) == {"new_alias"}


async def test_create_or_replace_view_other_error_does_not_drop_view(
    target_engine: AsyncEngine,
) -> None:
    """非 42P16 例外(如語法 / 欄位不存在)不得觸發 DROP,例外照樣往上拋,原 view 保留。"""
    await _ensure_source_table(target_engine, "VG_TEST", "VG_KEEP", {"VGA01": "VARCHAR(10)"})
    qualified = '"VG_TEST_en"."vg_keep"'
    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "VG_TEST_en"'))
        await view_generator._create_or_replace_view(
            conn, qualified, 'SELECT "VGA01" AS "employee_number" FROM "VG_TEST"."VG_KEEP"'
        )

        # 引用不存在欄位 → UndefinedColumnError(42703),非欄位集合不相容,不應 DROP
        bad_select_sql = 'SELECT "NOT_EXIST_COL" AS "employee_number" FROM "VG_TEST"."VG_KEEP"'
        with pytest.raises(DBAPIError):
            await view_generator._create_or_replace_view(conn, qualified, bad_select_sql)

    async with target_engine.connect() as conn:
        exists = (
            await conn.execute(
                text(
                    "SELECT 1 FROM information_schema.views"
                    " WHERE table_schema = 'VG_TEST_en' AND table_name = 'vg_keep'"
                )
            )
        ).first()
    assert exists is not None  # view 未被 DROP


# =============================================================================
# 真實 DB 整合測試:generate_views_for_schema 回報失敗表(AD-113)
# =============================================================================


async def test_generate_views_for_schema_reports_failed_tables(
    target_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _ensure_source_table(target_engine, "VG_TEST", "VG_FAIL", {"VGA01": "VARCHAR(10)"})
    await _ensure_source_table(target_engine, "VG_TEST", "VG_OK", {"VGA01": "VARCHAR(10)"})
    confirmed = {
        "VG_FAIL": {"": "employee_fail", "VGA01": "employee_number"},
        "VG_OK": {"": "employee_ok", "VGA01": "employee_number"},
    }
    real_create_or_replace = view_generator._create_or_replace_view

    async def _flaky(conn: AsyncConnection, qualified_view: str, select_sql: str) -> None:
        if "employee_fail" in qualified_view:
            raise RuntimeError("boom(模擬非 42P16 失敗)")
        await real_create_or_replace(conn, qualified_view, select_sql)

    monkeypatch.setattr(view_generator, "_create_or_replace_view", _flaky)

    async with target_engine.connect() as conn:
        conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        created, failed = await view_generator.generate_views_for_schema(
            conn, "VG_TEST", confirmed
        )

    assert created == ["VG_TEST_en.employee_ok"]
    assert failed == ["VG_TEST.VG_FAIL"]


async def test_regenerate_views_if_changed_does_not_cache_signature_on_partial_failure(
    session_factory: async_sessionmaker[AsyncSession],
    target_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """部分表失敗 → 不寫入內容簽名,確保下輪(即便內容未再變動)仍會重試補齊。"""
    await _ensure_source_table(
        target_engine, "VG_TEST", "VG_PARTIAL", {"VGA01": "VARCHAR(10)"}
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_PARTIAL",
        column_name="",
        english_name="employee_partial",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_PARTIAL",
        column_name="VGA01",
        english_name="employee_number",
        status="confirmed",
    )

    async def _failing_generate_views(
        engine: AsyncEngine, confirmed: dict[str, dict[str, str]]
    ) -> tuple[list[str], list[str]]:
        return [], ["VG_TEST.VG_PARTIAL"]

    monkeypatch.setattr(view_generator, "generate_views", _failing_generate_views)

    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        await view_generator.regenerate_views_if_changed(session, repo)

    cached = await cache.cache_get(view_generator._SIGNATURE_CACHE_KEY)
    assert cached is None  # 失敗未寫簽名,下輪會重試


# =============================================================================
# 真實 DB 整合測試:fetch_confirmed_mapping(draft 不進結果)
# =============================================================================


async def test_fetch_confirmed_mapping_excludes_draft(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="",
        english_name="employee_master",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="VGA01",
        english_name="employee_number",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="VGA02",
        english_name="draft_only_column",
        status="draft",
    )

    async with session_factory() as session:
        confirmed = await view_generator.fetch_confirmed_mapping(session)

    assert confirmed == {
        "VG_MASTER": {"": "employee_master", "VGA01": "employee_number"}
    }


# =============================================================================
# 真實 DB 整合測試:regenerate_views_if_changed 掛點(異動才重生)
# =============================================================================


async def test_regenerate_views_if_changed_skips_when_signature_unchanged(
    session_factory: async_sessionmaker[AsyncSession],
    target_engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _ensure_source_table(
        target_engine, "VG_TEST", "VG_MASTER", {"VGA01": "VARCHAR(10)", "VGA02": "VARCHAR(20)"}
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="",
        english_name="employee_master",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="VGA01",
        english_name="employee_number",
        status="confirmed",
    )

    call_count = 0
    real_generate_views = view_generator.generate_views

    async def _counting_generate_views(
        engine: AsyncEngine, confirmed: dict[str, dict[str, str]]
    ) -> tuple[list[str], list[str]]:
        nonlocal call_count
        call_count += 1
        return await real_generate_views(engine, confirmed)

    monkeypatch.setattr(view_generator, "generate_views", _counting_generate_views)

    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        await view_generator.regenerate_views_if_changed(session, repo)
    assert call_count == 1

    # mapping 無異動 → 第二次呼叫略過(不重跑 generate_views)
    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        await view_generator.regenerate_views_if_changed(session, repo)
    assert call_count == 1

    # mapping 異動(新增一筆 confirmed 欄位)→ 第三次呼叫重新產生
    await _seed_mapping(
        session_factory,
        table_name="VG_MASTER",
        column_name="VGA02",
        english_name="employee_name",
        status="confirmed",
    )
    async with session_factory() as session:
        repo = SemanticMappingRepository(session)
        await view_generator.regenerate_views_if_changed(session, repo)
    assert call_count == 2
