"""語意映射管理 API 測試(v1.5.1 task-004;真實本地 PostgreSQL 測試 DB 假扮目標 RDS)。

涵蓋:列表分頁 / 表名精準 / 狀態 / 關鍵字篩選、PATCH 更新(含 404 / 422 驗證)、
confirm-table 整表轉態(冪等)、member 403。
對齊 test_view_generator.py 模式:AWS_RDS_* 指向本地測試 DB,不觸碰真正 AWS RDS;
teardown 僅清資料(DELETE)不刪結構(禁 DROP)。
"""

import asyncio
import os

# app 模組於 import 時即讀 env 建立 engine → 先注入測試 env 再 import app 模組
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_PG_ADMIN_DB = os.environ.get("TEST_PG_ADMIN_DB", "data_center_etl")
TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
ADMIN_DATABASE_URL = f"{_BASE_URL}/{_PG_ADMIN_DB}"
TEST_DATABASE_URL = f"{_BASE_URL}/{TEST_DB_NAME}"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", TEST_DB_NAME)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402

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
from app.core import redis as cache  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.etl import introspect  # noqa: E402
from app.etl.semantic_schema import ensure_semantic_schema  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402

_BASE_PATH = "/api/v1/semantic-mappings"


# ── fixtures(對齊 test_snapshot_refresh_progress.py 慣例)──────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)+ metadata 建 schema + erp_metadata 語意表;不做任何 DROP。"""

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
                await ensure_semantic_schema(conn)
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
        await conn.execute(text("DELETE FROM erp_metadata.semantic_mappings"))
        await conn.execute(text("DELETE FROM semantic_mappings"))  # 自有 DB 本地副本
        await conn.execute(text("DELETE FROM users"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    cache._client = None


@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效。每測試後 dispose + 清快取(對齊 test_data_query_api.py)。"""
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


async def _login_as(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    username = f"{role}-user"
    password = f"{role}-password-123"
    async with session_factory() as session:
        password_hash = await hash_password_async(password)
        await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


async def _seed_rows(db_engine: AsyncEngine) -> None:
    """兩表五列樣本:BMA_FILE(表層級+兩欄,confirmed 混 draft)、GAT06(表層級+一欄)。"""
    rows = [
        ("BMA_FILE", "", "bma_file", "品號主檔", "confirmed"),
        ("BMA_FILE", "BMA001", "part_number", "品號", "confirmed"),
        ("BMA_FILE", "BMA002", "part_name", "品名", "draft"),
        ("GAT06", "", "voucher_type_config", "單別設定", "draft"),
        ("GAT06", "GAT061", "voucher_type", "單別", "draft"),
    ]
    async with db_engine.begin() as conn:
        for t, c, e, z, s in rows:
            await conn.execute(
                text(
                    "INSERT INTO erp_metadata.semantic_mappings"
                    " (table_name, column_name, english_name, zh_name, status)"
                    " VALUES (:t, :c, :e, :z, :s)"
                ),
                {"t": t, "c": c, "e": e, "z": z, "s": s},
            )


# ── 列表 / 篩選 ─────────────────────────────────────────────────────────
async def test_list_mappings_pagination_and_filters(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.get(_BASE_PATH, params={"page": 1, "page_size": 3})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 3

    resp = await client.get(_BASE_PATH, params={"table": "BMA_FILE"})
    assert {i["table_name"] for i in resp.json()["data"]["items"]} == {"BMA_FILE"}
    assert resp.json()["data"]["total"] == 3

    resp = await client.get(_BASE_PATH, params={"status": "draft"})
    assert resp.json()["data"]["total"] == 3

    resp = await client.get(_BASE_PATH, params={"keyword": "part_"})
    names = {i["english_name"] for i in resp.json()["data"]["items"]}
    assert names == {"part_number", "part_name"}

    # 中英皆可:表名子字串 / 中文名子字串皆可命中
    resp = await client.get(_BASE_PATH, params={"keyword": "GAT06"})
    assert resp.json()["data"]["total"] == 2
    resp = await client.get(_BASE_PATH, params={"keyword": "品號"})
    names = {i["english_name"] for i in resp.json()["data"]["items"]}
    assert names == {"bma_file", "part_number"}


async def test_list_tables_with_status_counts(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.get(f"{_BASE_PATH}/tables")
    assert resp.status_code == 200, resp.text
    by_name = {i["table_name"]: i for i in resp.json()["data"]["items"]}
    assert by_name["BMA_FILE"]["confirmed_count"] == 2
    assert by_name["BMA_FILE"]["draft_count"] == 1
    assert by_name["GAT06"]["draft_count"] == 2
    # 表層級中英文名帶出(供前端表名 combobox 中英搜尋)
    assert by_name["BMA_FILE"]["zh_name"] == "品號主檔"
    assert by_name["BMA_FILE"]["english_name"] == "bma_file"


# ── PATCH 更新 ──────────────────────────────────────────────────────────
async def test_patch_updates_fields_and_actor(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA002",
            "english_name": "part_display_name",
            "status": "confirmed",
        },
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["english_name"] == "part_display_name"
    assert item["status"] == "confirmed"
    assert item["updated_by"] is not None


async def test_patch_missing_row_returns_404(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.patch(
        _BASE_PATH,
        json={"table_name": "NOPE", "column_name": "X", "english_name": "abc"},
    )
    assert resp.status_code == 404, resp.text


async def test_patch_invalid_english_name_returns_422(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.patch(
        _BASE_PATH,
        json={"table_name": "BMA_FILE", "column_name": "BMA002", "english_name": "Bad Name"},
    )
    assert resp.status_code == 422, resp.text


async def test_patch_without_updatable_fields_returns_422(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.patch(
        _BASE_PATH, json={"table_name": "BMA_FILE", "column_name": "BMA002"}
    )
    assert resp.status_code == 422, resp.text


# ── confirm-table ───────────────────────────────────────────────────────
async def test_confirm_table_idempotent(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.post(
        f"{_BASE_PATH}/confirm-table", json={"table_name": "GAT06"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["affected"] == 2

    resp = await client.post(
        f"{_BASE_PATH}/confirm-table", json={"table_name": "GAT06"}
    )
    assert resp.json()["data"]["affected"] == 0

    resp = await client.get(_BASE_PATH, params={"table": "GAT06", "status": "draft"})
    assert resp.json()["data"]["total"] == 0


# ── sync-views(task-005:副本重灌 + view 重生)──────────────────────────
async def test_sync_views_copies_replica_and_reports(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["copied"] == 5
    # confirmed 映射存在且簽名初次寫入 → 執行重生;樣本表無實體表 → 建立/失敗皆 0
    assert data["regenerated"] is True
    assert data["created"] == 0
    assert data["failed"] == 0

    # 本地副本(自有 DB semantic_mappings)已整表重灌
    async with db_engine.connect() as conn:
        replica_total = (
            await conn.execute(text("SELECT count(*) FROM semantic_mappings"))
        ).scalar_one()
    assert int(replica_total) == 5

    # 內容未異動的第二次呼叫:副本照灌,view 重生略過(簽名命中)
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["copied"] == 5
    assert data["regenerated"] is False


# ── 套用進度端點(閒置 / 進行中)──────────────────────────────────────────
async def test_apply_progress_idle_and_running(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.worker.tasks import _report_apply_progress

    await _login_as(client, session_factory, "admin")
    resp = await client.get(f"{_BASE_PATH}/sync-views/progress")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active"] is False

    await _report_apply_progress("views", 120, 1284)
    resp = await client.get(f"{_BASE_PATH}/sync-views/progress")
    data = resp.json()["data"]
    assert data == {"active": True, "phase": "views", "done": 120, "total": 1284}


async def test_sync_views_clears_apply_progress_key(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 200, resp.text
    # 套用結束後進度 key 已清 → 閒置 inactive
    resp = await client.get(f"{_BASE_PATH}/sync-views/progress")
    assert resp.json()["data"]["active"] is False


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_member_forbidden(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "member")
    for method, path, kwargs in [
        ("GET", _BASE_PATH, {}),
        ("GET", f"{_BASE_PATH}/tables", {}),
        (
            "PATCH",
            _BASE_PATH,
            {"json": {"table_name": "X", "column_name": "", "english_name": "abc"}},
        ),
        ("POST", f"{_BASE_PATH}/confirm-table", {"json": {"table_name": "X"}}),
        ("POST", f"{_BASE_PATH}/sync-views", {}),
    ]:
        resp = await client.request(method, path, **kwargs)
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"
