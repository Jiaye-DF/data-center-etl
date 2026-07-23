"""語意映射自動補列測試(v1.5.2 task-002)。

- 純函式(`plan_autofill` / `_resolve_alias`)以無 DB 單元測試涵蓋補列 / 不覆寫 / 表層級 /
  別名查重 / zh 字典六情境的邏輯核心。
- DB 行為(information_schema 內省 + ON CONFLICT 冪等 + fetch_column_comments 字典串接)
  無法用 fake 驗證,對齊 test_view_generator.py / test_seed_semantic_mappings.py 模式:
  連真實本地 PostgreSQL 測試 DB(同時扮演「目標 RDS」與「來源 RDS」雙重角色),不觸碰真正 AWS RDS。

測試建立的帳套 schema / 表 / 字典表一律 `CREATE ... IF NOT EXISTS`,teardown 僅清資料
(DELETE)不刪結構(禁 DROP SCHEMA / DROP TABLE)。
"""

from __future__ import annotations

import os
from uuid import UUID

# app 模組於 import 時即讀 env 建立 engine;連線沿用 AWS_RDS_*(見 reader.py)+ 本地 DATABASE_URL,
# 皆指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS(對齊 test_view_generator.py)
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
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

import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from app.etl.comments import quote_ident  # noqa: E402
from app.etl.reader import RDS_SOURCE_DB_ENV, rds_database_url  # noqa: E402
from app.etl.semantic_autofill import (  # noqa: E402
    AutofillResult,
    _resolve_alias,
    autofill_semantic_mappings,
    plan_autofill,
)
from app.etl.semantic_schema import (  # noqa: E402
    SEMANTIC_SCHEMA,
    SEMANTIC_TABLE,
    ensure_semantic_schema,
)
from app.etl.writer import RDS_TARGET_DB_ENV  # noqa: E402

_ZERO_UUID = UUID("00000000-0000-0000-0000-000000000000")
_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"


# =============================================================================
# 純函式單元測試(免連線):_resolve_alias
# =============================================================================


def test_resolve_alias_no_collision_returns_base() -> None:
    alias, deduped = _resolve_alias("aaa01", set())
    assert alias == "aaa01"
    assert deduped is False


def test_resolve_alias_collision_appends_col_then_serial() -> None:
    assert _resolve_alias("aaa01", {"aaa01"}) == ("aaa01_col", True)
    assert _resolve_alias("aaa01", {"aaa01", "aaa01_col"}) == ("aaa01_col2", True)
    assert _resolve_alias("aaa01", {"aaa01", "aaa01_col", "aaa01_col2"}) == ("aaa01_col3", True)


# =============================================================================
# 純函式單元測試(免連線):plan_autofill 六情境邏輯核心
# =============================================================================


def test_plan_autofill_adds_confirmed_column_and_table_level() -> None:
    """(a)+(c):空映射 → 補表層級(表名小寫)+ 欄層級(欄名小寫、updated_by 全零)。"""
    inserts, result = plan_autofill(
        {"AAA_FILE": ["AAA01", "AAA02"]}, existing=[], zh_lookup={}
    )
    assert result == AutofillResult(columns_added=2, tables_added=1, aliases_deduped=0)
    # 表層級列
    table_row = next(r for r in inserts if r["c"] == "")
    assert table_row["e"] == "aaa_file"
    assert table_row["u"] == _ZERO_UUID
    # 欄層級列:english=小寫原欄名、updated_by 全零
    col_row = next(r for r in inserts if r["c"] == "AAA01")
    assert col_row["e"] == "aaa01"
    assert col_row["u"] == _ZERO_UUID


def test_plan_autofill_does_not_overwrite_existing_draft_or_confirmed() -> None:
    """(b):既有 draft / confirmed 列(及表層級)一律略過,只補真正缺的欄。"""
    inserts, result = plan_autofill(
        {"AAA_FILE": ["AAA01", "AAA02", "AAA03"]},
        existing=[
            ("AAA_FILE", "", "aaa_file"),  # 表層級已存在
            ("AAA_FILE", "AAA01", "human_confirmed"),  # 人工 confirmed
            ("AAA_FILE", "AAA02", "human_draft"),  # 待複核 draft
        ],
        zh_lookup={},
    )
    # 僅 AAA03 缺;表層級與 AAA01/AAA02 皆不補
    assert result == AutofillResult(columns_added=1, tables_added=0, aliases_deduped=0)
    assert [r["c"] for r in inserts] == ["AAA03"]
    assert inserts[0]["e"] == "aaa03"


def test_plan_autofill_fills_only_table_level_when_columns_exist() -> None:
    """(c):欄層級已存在但缺表層級列 → 只補表層級(表名小寫)。"""
    inserts, result = plan_autofill(
        {"AAA_FILE": ["AAA01"]},
        existing=[("AAA_FILE", "AAA01", "human_confirmed")],
        zh_lookup={},
    )
    assert result == AutofillResult(columns_added=0, tables_added=1, aliases_deduped=0)
    assert inserts == [
        {"t": "AAA_FILE", "c": "", "e": "aaa_file", "z": "", "u": _ZERO_UUID}
    ]


def test_plan_autofill_dedup_against_existing_english_name() -> None:
    """(d):新欄自動英文名撞同表既有 english_name → `_col` / 序號規避。"""
    inserts, result = plan_autofill(
        {"AAA_FILE": ["AAA09", "AAA02"]},
        # 既有欄 AAA09 佔用 english_name 'aaa02';表層級也已存在
        existing=[
            ("AAA_FILE", "", "aaa_file"),
            ("AAA_FILE", "AAA09", "aaa02"),
        ],
        zh_lookup={},
    )
    # AAA09 已存在略過;AAA02 新,base 'aaa02' 撞既有 → 'aaa02_col'
    assert result == AutofillResult(columns_added=1, tables_added=0, aliases_deduped=1)
    assert inserts[0]["c"] == "AAA02"
    assert inserts[0]["e"] == "aaa02_col"


def test_plan_autofill_dedup_within_same_round() -> None:
    """(d):同輪兩欄小寫後撞名(大小寫不同)→ 後者確定性附 `_col`。"""
    inserts, result = plan_autofill(
        {"T": ["AB", "ab"]}, existing=[], zh_lookup={}
    )
    assert result.aliases_deduped == 1
    aliases = {r["c"]: r["e"] for r in inserts if r["c"] != ""}
    # sorted(['AB','ab']) → 'AB' 先取 'ab';'ab' 撞 → 'ab_col'
    assert aliases == {"AB": "ab", "ab": "ab_col"}


def test_plan_autofill_zh_from_lookup_else_empty() -> None:
    """(f):zh_name 取字典值(小寫欄名為 key),缺則空字串。"""
    inserts, _result = plan_autofill(
        {"AAA_FILE": ["AAA01", "AAA02"]},
        existing=[("AAA_FILE", "", "aaa_file")],
        zh_lookup={"aaa01": "帳別編號"},
    )
    by_col = {r["c"]: r["z"] for r in inserts}
    assert by_col["AAA01"] == "帳別編號"
    assert by_col["AAA02"] == ""  # 字典缺 → 空


# =============================================================================
# 真實 DB 整合測試:autofill_semantic_mappings 端到端
# =============================================================================


@pytest_asyncio.fixture
async def target_engine() -> AsyncIterator[AsyncEngine]:
    """目標 RDS 測試替身(同一實體測試 DB);確保 erp_metadata.semantic_mappings 存在。"""
    engine = create_async_engine(rds_database_url(RDS_TARGET_DB_ENV), poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await ensure_semantic_schema(conn)
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def source_engine() -> AsyncIterator[AsyncEngine]:
    """來源 RDS 測試替身(同一實體測試 DB,供 DS 字典查詢)。"""
    engine = create_async_engine(rds_database_url(RDS_SOURCE_DB_ENV), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_semantic_mappings(target_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試前後清空語意映射資料(非 DROP)。"""
    async with target_engine.begin() as conn:
        await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))
    yield
    async with target_engine.begin() as conn:
        await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))


async def _ensure_account_table(
    engine: AsyncEngine, schema: str, table: str, columns: list[str]
) -> None:
    """建立測試用帳套 schema / 表(冪等,禁 DROP);欄位型別一律 TEXT。"""
    col_defs = ", ".join(f'"{col}" TEXT' for col in columns)
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
        await conn.execute(text(f'CREATE TABLE IF NOT EXISTS "{schema}"."{table}" ({col_defs})'))


async def _insert_existing_mapping(
    engine: AsyncEngine,
    *,
    table_name: str,
    column_name: str,
    english_name: str,
    status: str,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                f"INSERT INTO {_QUALIFIED}"
                " (table_name, column_name, english_name, status)"
                " VALUES (:t, :c, :e, :s)"
            ),
            {"t": table_name, "c": column_name, "e": english_name, "s": status},
        )


async def _fetch_rows(
    engine: AsyncEngine, table_name: str
) -> dict[str, tuple[str, str | None, str, UUID]]:
    """回傳指定表的映射列 {column_name: (english_name, zh_name, status, updated_by)}。"""
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    "SELECT column_name, english_name, zh_name, status, updated_by"
                    f" FROM {_QUALIFIED} WHERE table_name = :t"
                ),
                {"t": table_name},
            )
        ).all()
    return {r[0]: (r[1], r[2], r[3], r[4]) for r in rows}


async def test_autofill_inserts_confirmed_and_preserves_existing(
    target_engine: AsyncEngine, source_engine: AsyncEngine
) -> None:
    """(a)+(b)+(c):缺欄補 confirmed(english 小寫 / updated_by 全零)、既有列不覆寫、補表層級。"""
    await _ensure_account_table(target_engine, "AF_TEST", "AF_MASTER", ["AFA01", "AFA02", "AFA03"])
    # 既有一筆 draft(人工待複核),驗證不被覆寫
    await _insert_existing_mapping(
        target_engine,
        table_name="AF_MASTER",
        column_name="AFA01",
        english_name="human_alias",
        status="draft",
    )

    await autofill_semantic_mappings(target_engine, source_engine)

    rows = await _fetch_rows(target_engine, "AF_MASTER")
    # 表層級補入:english=表名小寫、confirmed、updated_by 全零
    assert rows[""][0] == "af_master"
    assert rows[""][2] == "confirmed"
    assert rows[""][3] == _ZERO_UUID
    # 既有 draft 未被覆寫
    assert rows["AFA01"] == ("human_alias", None, "draft", _ZERO_UUID)
    # 缺欄補 confirmed,english=小寫原欄名、updated_by 全零
    assert rows["AFA02"][0] == "afa02"
    assert rows["AFA02"][2] == "confirmed"
    assert rows["AFA02"][3] == _ZERO_UUID
    assert rows["AFA03"][0] == "afa03"
    assert rows["AFA03"][2] == "confirmed"


async def test_autofill_is_idempotent_on_rerun(
    target_engine: AsyncEngine, source_engine: AsyncEngine
) -> None:
    """(e):ON CONFLICT DO NOTHING → 重跑不炸 PK,第二輪不再補任何列(全 DB 已補齊)。"""
    await _ensure_account_table(target_engine, "AF_TEST", "AF_IDEM", ["AFB01", "AFB02"])

    await autofill_semantic_mappings(target_engine, source_engine)
    first = await _fetch_rows(target_engine, "AF_IDEM")

    # 第二輪:全 DB 缺列於首輪已補齊 → 統計全零,且不重複插入
    second_result = await autofill_semantic_mappings(target_engine, source_engine)
    second = await _fetch_rows(target_engine, "AF_IDEM")

    assert second_result == AutofillResult(columns_added=0, tables_added=0, aliases_deduped=0)
    assert first == second


async def test_autofill_dedup_alias_against_existing(
    target_engine: AsyncEngine, source_engine: AsyncEngine
) -> None:
    """(d):新欄自動英文名撞同表既有 english_name → 落庫為 `_col` 規避。"""
    await _ensure_account_table(target_engine, "AF_TEST", "AF_DEDUP", ["AFC02"])
    # 既有欄佔用 english_name 'afc02',使新欄 AFC02 的自動別名撞名
    await _insert_existing_mapping(
        target_engine,
        table_name="AF_DEDUP",
        column_name="AFC99",
        english_name="afc02",
        status="confirmed",
    )

    await autofill_semantic_mappings(target_engine, source_engine)

    rows = await _fetch_rows(target_engine, "AF_DEDUP")
    assert rows["AFC02"][0] == "afc02_col"


async def test_autofill_zh_name_from_dictionary_else_empty(
    target_engine: AsyncEngine, source_engine: AsyncEngine
) -> None:
    """(f):zh_name 經來源 DS 字典(GAQ_FILE)取中文名,缺則空字串。"""
    # 建 DS.GAQ_FILE 並填一筆繁體中文名(對齊 dictionary.fetch_column_comments 契約)
    async with source_engine.begin() as conn:
        await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "DS"'))
        await conn.execute(
            text(
                'CREATE TABLE IF NOT EXISTS "DS"."GAQ_FILE"'
                ' ("GAQ01" TEXT, "GAQ02" TEXT, "GAQ03" TEXT, "GAQ04" TEXT, "GAQ05" TEXT)'
            )
        )
        await conn.execute(
            text('DELETE FROM "DS"."GAQ_FILE" WHERE "GAQ01" = :c'), {"c": "AFD01"}
        )
        await conn.execute(
            text(
                'INSERT INTO "DS"."GAQ_FILE" ("GAQ01", "GAQ02", "GAQ03")'
                " VALUES ('AFD01', '0', '字典中文名')"
            )
        )
    await _ensure_account_table(target_engine, "AF_TEST", "AF_ZH", ["AFD01", "AFD02"])

    try:
        await autofill_semantic_mappings(target_engine, source_engine)
        rows = await _fetch_rows(target_engine, "AF_ZH")
        assert rows["AFD01"][1] == "字典中文名"  # 取字典值
        assert rows["AFD02"][1] == ""  # 字典缺 → 空
    finally:
        async with source_engine.begin() as conn:
            await conn.execute(
                text('DELETE FROM "DS"."GAQ_FILE" WHERE "GAQ01" = :c'), {"c": "AFD01"}
            )
