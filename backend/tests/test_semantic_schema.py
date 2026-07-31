"""semantic_schema 冪等建置測試(task-001,propose A1):`erp_metadata.semantic_mappings`。

CHECK 約束等實際 DDL 行為無法用 FakeConn 驗證,故對齊 test_mirror_sync_incremental.py 模式:
連真實本地 PostgreSQL 測試 DB(env 指向共用測試 DB,不觸碰真正 AWS RDS),
驗證冪等呼叫不 raise、schema/table 實際建立、CHECK 拒絕非 draft/confirmed。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建立 engine;semantic_schema 連線沿用 AWS_RDS_*(見 reader.py),
# 測試指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}",
)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from typing import cast  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncConnection,
    AsyncEngine,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl.comments import quote_ident  # noqa: E402
from app.etl.reader import rds_database_url  # noqa: E402
from app.etl.semantic_schema import (  # noqa: E402
    _ENGLISH_TABLE_UNIQUE_INDEX,
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    _ensure_english_table_unique,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402

_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"

_TABLE_EXISTS_SQL = text(
    "SELECT 1 FROM information_schema.tables"
    " WHERE table_schema = :schema AND table_name = :table"
)

_INSERT_SQL = text(
    f"INSERT INTO {_QUALIFIED} (table_name, column_name, english_name, status)"
    " VALUES (:t, :c, :e, :s)"
)


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """指向共用測試 DB 的 engine(NullPool,對齊既有整合測試模式)。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_semantic_mappings(target_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試後清空表資料(非 DROP);表本身可能不存在,先檢查再清。"""
    yield
    async with target_engine.begin() as conn:
        exists = (
            await conn.execute(
                _TABLE_EXISTS_SQL, {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE}
            )
        ).first()
        if exists is not None:
            await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))


async def test_ensure_semantic_schema_idempotent_no_raise(target_engine: AsyncEngine) -> None:
    """重複呼叫 ensure 兩次不 raise(冪等)。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)


async def test_ensure_semantic_schema_creates_schema_and_table(
    target_engine: AsyncEngine,
) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(
                _TABLE_EXISTS_SQL, {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE}
            )
        ).first()
    assert row is not None


async def test_check_rejects_invalid_status(target_engine: AsyncEngine) -> None:
    """CHECK 拒絕非 draft/confirmed 的 status。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    with pytest.raises(IntegrityError):
        async with target_engine.begin() as conn:
            await conn.execute(
                _INSERT_SQL,
                {"t": "AAA_FILE", "c": "AAA01", "e": "account no", "s": "invalid"},
            )


async def test_check_accepts_draft_and_confirmed(target_engine: AsyncEngine) -> None:
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.begin() as conn:
        await conn.execute(
            _INSERT_SQL,
            {"t": "AAA_FILE", "c": "AAA01", "e": "account no", "s": "draft"},
        )
        await conn.execute(
            _INSERT_SQL,
            {"t": "AAA_FILE", "c": "AAA02", "e": "account name", "s": "confirmed"},
        )


_UPDATED_AT_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = :table AND column_name = 'updated_at'"
)


async def test_updated_at_is_naive_timestamp(target_engine: AsyncEngine) -> None:
    """updated_at 一律 naive timestamp(MSSQL datetime2 等價;user 決議 2026-07-20)。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(
                _UPDATED_AT_TYPE_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
    assert row is not None
    assert row[0] == "timestamp without time zone"


_UPDATED_BY_TYPE_SQL = text(
    "SELECT data_type FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = :table AND column_name = 'updated_by'"
)


_UPDATED_BY_META_SQL = text(
    "SELECT data_type, is_nullable, column_default FROM information_schema.columns"
    " WHERE table_schema = :schema AND table_name = :table AND column_name = 'updated_by'"
)


async def test_updated_by_is_uuid_not_null_with_zero_default(
    target_engine: AsyncEngine,
) -> None:
    """updated_by 為 uuid NOT NULL,DEFAULT 全零(04-databases 型別 + user 決議 2026-07-21)。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        row = (
            await conn.execute(
                _UPDATED_BY_META_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
    assert row is not None
    assert row[0] == "uuid"
    assert row[1] == "NO"
    assert "00000000-0000-0000-0000-000000000000" in str(row[2])


async def test_ensure_migrates_legacy_text_updated_by(target_engine: AsyncEngine) -> None:
    """舊版 text 欄位:ensure 冪等轉 uuid;合法 UUID 原值保留、工具標記與 NULL 皆轉全零。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
        # 模擬舊版部署狀態:欄位改回 text nullable 並塞三種值(僅測試用;非破壞性型別轉換)
        await conn.execute(
            text(
                f"ALTER TABLE {_QUALIFIED} ALTER COLUMN updated_by DROP NOT NULL,"
                " ALTER COLUMN updated_by DROP DEFAULT"
            )
        )
        await conn.execute(
            text(
                f"ALTER TABLE {_QUALIFIED} ALTER COLUMN updated_by TYPE text"
                " USING (updated_by::text)"
            )
        )
        for suffix, updated_by in [
            ("U1", "22222222-2222-2222-2222-222222222222"),
            ("U2", "bulk-confirm-tool-marker"),
            ("U3", None),
        ]:
            await conn.execute(
                text(
                    f"INSERT INTO {_QUALIFIED}"
                    " (table_name, column_name, english_name, status, updated_by)"
                    " VALUES (:t, :c, :e, 'draft', :u)"
                ),
                {"t": "LEGACY_BY_FILE", "c": suffix, "e": f"col_{suffix.lower()}", "u": updated_by},
            )

    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        type_row = (
            await conn.execute(
                _UPDATED_BY_TYPE_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
        values = dict(
            (
                await conn.execute(
                    text(
                        f"SELECT column_name, CAST(updated_by AS text) FROM {_QUALIFIED}"
                        " WHERE table_name = 'LEGACY_BY_FILE'"
                    )
                )
            ).all()
        )
    assert type_row is not None and type_row[0] == "uuid"
    assert values["U1"] == "22222222-2222-2222-2222-222222222222"
    assert values["U2"] == "00000000-0000-0000-0000-000000000000"
    assert values["U3"] == "00000000-0000-0000-0000-000000000000"  # NULL 回填全零


async def test_ensure_migrates_legacy_timestamptz(target_engine: AsyncEngine) -> None:
    """舊版 timestamptz 欄位:ensure 冪等轉為 naive timestamp 且既有資料保留。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)
        # 模擬舊版部署狀態:把欄位改回 timestamptz(僅測試用;非破壞性型別轉換)
        await conn.execute(
            text(
                f"ALTER TABLE {_QUALIFIED} ALTER COLUMN updated_at TYPE timestamptz"
                " USING (updated_at AT TIME ZONE 'Asia/Taipei')"
            )
        )
        await conn.execute(
            _INSERT_SQL,
            {"t": "LEGACY_FILE", "c": "L01", "e": "legacy col", "s": "draft"},
        )

    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        type_row = (
            await conn.execute(
                _UPDATED_AT_TYPE_SQL,
                {"schema": SEMANTIC_SCHEMA, "table": SEMANTIC_TABLE},
            )
        ).first()
        data_row = (
            await conn.execute(
                text(
                    f"SELECT updated_at FROM {_QUALIFIED}"
                    " WHERE table_name = 'LEGACY_FILE' AND column_name = 'L01'"
                )
            )
        ).first()
    assert type_row is not None and type_row[0] == "timestamp without time zone"
    assert data_row is not None and data_row[0] is not None
    assert data_row[0].tzinfo is None


# ── 表層級英文名唯一(v1.6.1 fixed AD-154 / AD-150)──────────────────────
_INDEX_EXISTS_SQL = text(
    "SELECT 1 FROM pg_indexes WHERE schemaname = :schema AND indexname = :index"
)


async def test_table_level_english_name_is_globally_unique(
    target_engine: AsyncEngine,
) -> None:
    """表層級英文名(column_name = '')全域唯一;欄位級同名跨表仍合法。"""
    async with target_engine.begin() as conn:
        await ensure_semantic_schema(conn)

    async with target_engine.connect() as conn:
        index_row = (
            await conn.execute(
                _INDEX_EXISTS_SQL,
                {"schema": SEMANTIC_SCHEMA, "index": _ENGLISH_TABLE_UNIQUE_INDEX},
            )
        ).first()
    assert index_row is not None

    async with target_engine.begin() as conn:
        await conn.execute(
            _INSERT_SQL, {"t": "AAA_FILE", "c": "", "e": "shared_name", "s": "confirmed"}
        )

    # 另一張表想用同一個表層級英文名 → 被唯一索引擋下(否則既有授權會錯接到別張表)
    with pytest.raises(IntegrityError):
        async with target_engine.begin() as conn:
            await conn.execute(
                _INSERT_SQL,
                {"t": "BBB_FILE", "c": "", "e": "shared_name", "s": "confirmed"},
            )

    # 欄位級不受此索引限制(對外 key 是 表.欄位)
    async with target_engine.begin() as conn:
        await conn.execute(
            _INSERT_SQL, {"t": "AAA_FILE", "c": "A01", "e": "shared_name", "s": "draft"}
        )
        await conn.execute(
            _INSERT_SQL, {"t": "BBB_FILE", "c": "B01", "e": "shared_name", "s": "draft"}
        )


class _FakeResult:
    def __init__(self, rows: list[tuple[str, int]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[str, int]]:
        return self._rows


class _FakeConn:
    """只錄下執行過的 SQL:用來驗「有重複時不下 CREATE INDEX」,不需真連線。"""

    def __init__(self, duplicates: list[tuple[str, int]]) -> None:
        self._duplicates = duplicates
        self.executed: list[str] = []

    async def execute(self, statement: object) -> _FakeResult:
        self.executed.append(str(statement))
        return _FakeResult(self._duplicates)


async def test_ensure_skips_unique_index_when_duplicates_exist(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """既有資料已有重複表層級英文名時:只 log warning 並跳過建索引(不炸啟動 / 建置)。

    真連線下重複資料早被索引擋住而塞不進去,故此路徑以 fake conn 驗證
    (對齊本檔頭「無法用 FakeConn 驗證者才連真 DB」的分工)。
    """
    duplicated = _FakeConn([("dup_name", 2)])
    with caplog.at_level("WARNING"):
        await _ensure_english_table_unique(cast(AsyncConnection, duplicated))
    assert not any("CREATE UNIQUE INDEX" in sql for sql in duplicated.executed)
    assert _ENGLISH_TABLE_UNIQUE_INDEX in caplog.text
    assert "dup_name×2" in caplog.text

    # 清重後(查重回空)才會真的下 CREATE UNIQUE INDEX
    clean = _FakeConn([])
    await _ensure_english_table_unique(cast(AsyncConnection, clean))
    assert any("CREATE UNIQUE INDEX" in sql for sql in clean.executed)
