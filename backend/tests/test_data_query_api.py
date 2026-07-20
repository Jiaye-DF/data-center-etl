"""資料列查詢 JSON API 測試(task-004,propose A3;真實 PostgreSQL 測試 DB)。

涵蓋:confirmed 表回英文 key、未 confirmed 欄不出現、表層級映射不當資料欄、
全 draft 表 404、未知 schema 404(訊息不回打輸入)、limit 上限 / offset 邊界 422、
分頁 limit/offset、未登入 401、member 403(datasets 全端點 admin-only)、
confirmed mapping 與實際欄位漂移時取交集 / 交集為空與表不存在皆 404 不 500(AD-111)。

RDS dataset 庫在測試中指向本地測試 DB(AWS_RDS_* → localhost 測試 DB,不觸碰真正 AWS RDS);
以真實 source 表(M2201.GEN_FILE)驗證識別字白名單 + bind params 的實際查詢行為。
"""

import asyncio
import os

# app 模組於 import 時即建立 engine → 先注入測試 env 再 import app 模組。
# 自有 DB 走 DATABASE_URL;RDS dataset 庫走 AWS_RDS_*,兩者於測試皆指向同一本地測試 DB。
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
os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_SOURCE_DB"] = TEST_DB_NAME
os.environ["AWS_RDS_TARGET_DB"] = TEST_DB_NAME
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
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.etl import introspect  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Dataset, RdsTableMeta, SemanticMapping  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402

# 測試用 source 表(對齊 Acceptance curl 範例 source/M2201/GEN_FILE)
_SRC_SCHEMA = "M2201"
_SRC_TABLE = "GEN_FILE"
_QUALIFIED = f'"{_SRC_SCHEMA}"."{_SRC_TABLE}"'


# ── fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)並以 metadata 建 schema;另建 source 表(冪等,不 DROP)。"""

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
                # source 表:模擬 RDS 原始表(欄名為 ERP 魔術名 gen01/gen02/gen03)
                await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{_SRC_SCHEMA}"'))
                await conn.execute(
                    text(
                        f'CREATE TABLE IF NOT EXISTS {_QUALIFIED} '
                        "(gen01 VARCHAR(20), gen02 VARCHAR(50), gen03 VARCHAR(50))"
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
        await conn.execute(text("DELETE FROM semantic_mappings"))
        await conn.execute(text("DELETE FROM rds_table_meta"))
        await conn.execute(text("DELETE FROM users"))
        await conn.execute(text(f"DELETE FROM {_QUALIFIED}"))


@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效(NoneType send)。每測試後 dispose + 清快取,確保各測試
    於自身 loop 建立全新連線。"""
    yield
    for engine in list(introspect._ENGINES.values()):
        await engine.dispose()
    introspect._ENGINES.clear()


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


# ── seed helpers ────────────────────────────────────────────────────────
async def _create_user(
    session_factory: async_sessionmaker[AsyncSession], username: str, password: str, role: str
) -> None:
    async with session_factory() as session:
        password_hash = await hash_password_async(password)
        await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()


async def _login_as(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    username = f"{role}-user"
    password = f"{role}-password-123"
    await _create_user(session_factory, username, password, role)
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


async def _seed_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema_name: str = _SRC_SCHEMA,
    table_name: str = _SRC_TABLE,
) -> None:
    """在 rds_table_meta 種一筆快照,讓該 schema 進入 source 允許集合。"""
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            RdsTableMeta(
                uid=uuid4(),
                dataset=Dataset.SOURCE,
                schema_name=schema_name,
                table_name=table_name,
                business_name=None,
                column_count=3,
                row_count=0,
                snapshot_at=None,
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


async def _seed_mapping(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    table_name: str,
    column_name: str,
    english_name: str,
    status: str,
    zh_name: str | None = None,
) -> None:
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            SemanticMapping(
                uid=uuid4(),
                table_name=table_name,
                column_name=column_name,
                english_name=english_name,
                zh_name=zh_name,
                status=status,
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


async def _seed_source_rows(
    db_engine: AsyncEngine, rows: list[tuple[str, str, str]]
) -> None:
    async with db_engine.begin() as conn:
        for gen01, gen02, gen03 in rows:
            await conn.execute(
                text(
                    f"INSERT INTO {_QUALIFIED} (gen01, gen02, gen03)"
                    " VALUES (:a, :b, :c)"
                ),
                {"a": gen01, "b": gen02, "c": gen03},
            )


async def _seed_confirmed_gen_file(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """GEN_FILE:gen01/gen02 confirmed(含表層級映射),gen03 draft(不得外流)。"""
    await _seed_snapshot(session_factory)
    # 表層級英文名(column_name='');不應成為資料欄
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="", english_name="employee",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen01",
        english_name="employee_number", zh_name="員工編號", status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen02",
        english_name="employee_name", zh_name="員工姓名", status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen03",
        english_name="secret_field", status="draft",
    )


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


_URL = f"/api/v1/datasets/source/tables/{_SRC_SCHEMA}/{_SRC_TABLE}/rows"


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_query_rows_requires_login_401(client: AsyncClient) -> None:
    resp = await client.get(_URL)
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


async def test_query_rows_member_forbidden_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """datasets 全端點 admin-only,member 一律 403。"""
    await _login_as(client, session_factory, "member")
    resp = await client.get(_URL)
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


# ── confirmed:回英文 key,未 confirmed 欄不出現 ─────────────────────────
async def test_confirmed_returns_english_keys(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_confirmed_gen_file(session_factory)
    await _seed_source_rows(db_engine, [("E001", "Alice", "top-secret")])

    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    data = body["data"]
    assert data["total_returned"] == 1
    row = data["rows"][0]
    # key 已轉英文語意名
    assert row["employee_number"] == "E001"
    assert row["employee_name"] == "Alice"
    # 原始魔術名不外流
    assert "gen01" not in row
    assert "gen02" not in row
    # 未 confirmed 欄(gen03)完全不出現(草稿英文名也不外流)
    assert "gen03" not in row
    assert "secret_field" not in row
    assert row.get("top-secret") is None  # 值也不在
    # 表層級映射(column_name='')不當作資料欄
    assert set(row.keys()) == {"employee_number", "employee_name"}
    # columns 元資訊:僅語意名(english / zh),不含原始欄名
    meta = {c["english_name"]: c["zh_name"] for c in data["columns"]}
    assert meta == {"employee_number": "員工編號", "employee_name": "員工姓名"}


# ── confirmed mapping 與實際欄位漂移(AD-111)───────────────────────────
async def test_confirmed_intersects_with_actual_columns_partial_drift(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    """confirmed 欄位一部分已從實體表移除(ERP 端改名/移除)→ 僅回實際存在的交集欄位,
    不因缺欄整個拋例外(500)。"""
    await _login_as(client, session_factory, "admin")
    await _seed_snapshot(session_factory)
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="", english_name="employee",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen01",
        english_name="employee_number", zh_name="員工編號", status="confirmed",
    )
    # gen99 不存在於實體表(模擬 ERP 端欄位已移除的 mapping 漂移)
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen99",
        english_name="ghost_column", status="confirmed",
    )
    await _seed_source_rows(db_engine, [("E001", "Alice", "x")])

    resp = await client.get(_URL)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    row = body["data"]["rows"][0]
    assert set(row.keys()) == {"employee_number"}
    assert "ghost_column" not in row
    meta = {c["english_name"] for c in body["data"]["columns"]}
    assert meta == {"employee_number"}


async def test_confirmed_columns_entirely_missing_returns_404_not_500(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """confirmed 欄位與實際表欄位交集為空(全部漂移)→ 404,不讓 SELECT 拋 500。"""
    await _login_as(client, session_factory, "admin")
    await _seed_snapshot(session_factory)
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="", english_name="employee",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen99",
        english_name="ghost_column", status="confirmed",
    )
    resp = await client.get(_URL)
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)
    detail = resp.json()["detail"]
    assert _SRC_SCHEMA not in detail
    assert _SRC_TABLE not in detail


async def test_table_missing_from_rds_returns_404_not_500(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """快照有該表紀錄、confirmed mapping 存在,但實體 RDS 表已不存在(整表刪除/改名)
    → 404,不讓 information_schema 交集查詢後的 SELECT 拋 500。"""
    ghost_table = "GEN_FILE_GHOST"
    await _login_as(client, session_factory, "admin")
    await _seed_snapshot(session_factory, table_name=ghost_table)
    await _seed_mapping(
        session_factory, table_name=ghost_table, column_name="", english_name="employee",
        status="confirmed",
    )
    await _seed_mapping(
        session_factory, table_name=ghost_table, column_name="gen01",
        english_name="employee_number", status="confirmed",
    )
    resp = await client.get(
        f"/api/v1/datasets/source/tables/{_SRC_SCHEMA}/{ghost_table}/rows"
    )
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)


# ── 全 draft 表 → 404 ───────────────────────────────────────────────────
async def test_all_draft_table_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_snapshot(session_factory)
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen01",
        english_name="employee_number", status="draft",
    )
    resp = await client.get(_URL)
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)
    # 404 訊息不回打使用者輸入的 schema / table(避免反射)
    detail = resp.json()["detail"]
    assert _SRC_SCHEMA not in detail
    assert _SRC_TABLE not in detail


# ── 未知 schema(不在 dataset 允許集合)→ 404 ───────────────────────────
async def test_unknown_schema_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    # 有 confirmed 欄位,但快照未收錄該 schema → schema 白名單擋下
    await _seed_mapping(
        session_factory, table_name=_SRC_TABLE, column_name="gen01",
        english_name="employee_number", status="confirmed",
    )
    resp = await client.get(_URL)
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)
    assert _SRC_SCHEMA not in resp.json()["detail"]


# ── limit / offset 邊界 → 422 ───────────────────────────────────────────
async def test_limit_and_offset_bounds_422(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    # limit 上限 500
    assert (await client.get(_URL, params={"limit": 501})).status_code == 422
    # limit 下限 1
    assert (await client.get(_URL, params={"limit": 0})).status_code == 422
    # offset >= 0
    assert (await client.get(_URL, params={"offset": -1})).status_code == 422
    # offset 上界 100_000(AD-114:避免無界 offset 拖垮小連線池)
    assert (await client.get(_URL, params={"offset": 100_001})).status_code == 422
    assert (await client.get(_URL, params={"offset": 100_000})).status_code != 422


# ── 分頁:limit / offset ────────────────────────────────────────────────
async def test_limit_offset_pagination(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_confirmed_gen_file(session_factory)
    await _seed_source_rows(
        db_engine,
        [("E001", "Alice", "x"), ("E002", "Bob", "y"), ("E003", "Carol", "z")],
    )
    # limit 封頂本次回傳列數
    body = (await client.get(_URL, params={"limit": 2, "offset": 0})).json()
    assert body["data"]["total_returned"] == 2
    assert [r["employee_number"] for r in body["data"]["rows"]] == ["E001", "E002"]
    # offset 位移(ORDER BY 欄位位置,分頁穩定)
    body = (await client.get(_URL, params={"limit": 2, "offset": 1})).json()
    assert [r["employee_number"] for r in body["data"]["rows"]] == ["E002", "E003"]
