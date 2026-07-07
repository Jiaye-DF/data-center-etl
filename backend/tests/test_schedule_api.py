"""task-005 排程管理 API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:排程 CRUD / 啟停、cron 格式驗證 400、名稱重複 409、
分頁、軟刪除(資料仍在 DB,is_deleted=true)、viewer 寫入 403、ApiResponse 外殼。

v1.3:同步統一為「增量同步全部表」單一語意,排程不再逐表選擇,已移除 etl_table_uid 相關測試。
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
from uuid import UUID, uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
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
from app.main import create_app  # noqa: E402
from app.models import Schedule  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402


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
        await conn.execute(text("DELETE FROM users"))


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
    # base_url 用 https:cookie 為 secure=True,走 http 不會被 client 回送
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    username: str,
    password: str,
    role: str,
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


def _schedule_payload(suffix: str = "a", **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": f"每日排程 {suffix}",
        "cron_expr": "0 2 * * *",
        "is_enabled": True,
        "description": f"測試排程 {suffix}",
    }
    payload.update(overrides)
    return payload


async def _create_schedule(client: AsyncClient, suffix: str = "a") -> str:
    resp = await client.post("/api/v1/schedules", json=_schedule_payload(suffix))
    assert resp.status_code == 201, resp.text
    uid = resp.json()["data"]["uid"]
    assert isinstance(uid, str)
    return uid


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    """斷言 ApiResponse 外殼:success / data / detail / response_code。"""
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


# ── 未登入 / viewer 權限 ────────────────────────────────────────────────
async def test_list_requires_login_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


async def test_viewer_can_read_but_writes_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    # 讀取 OK
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 200
    # 寫入類一律 403:create / patch / delete / enable / disable
    fake_uid = str(uuid4())
    assert (
        await client.post("/api/v1/schedules", json=_schedule_payload())
    ).status_code == 403
    assert (
        await client.patch(f"/api/v1/schedules/{fake_uid}", json={"description": "x"})
    ).status_code == 403
    assert (await client.delete(f"/api/v1/schedules/{fake_uid}")).status_code == 403
    assert (await client.post(f"/api/v1/schedules/{fake_uid}/enable")).status_code == 403
    resp = await client.post(f"/api/v1/schedules/{fake_uid}/disable")
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


# ── 建立 ────────────────────────────────────────────────────────────────
async def test_create_schedule_201(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post("/api/v1/schedules", json=_schedule_payload())
    assert resp.status_code == 201
    body = resp.json()
    _assert_shell(body, success=True, response_code=201)
    data = body["data"]
    assert data["name"] == "每日排程 a"
    assert data["cron_expr"] == "0 2 * * *"
    assert data["is_enabled"] is True
    assert data["job_desc"] == "增量同步全部表"
    assert data["last_run_status"] is None
    assert data["last_run_finished_at"] is None
    assert "etl_table_uid" not in data
    assert data["description"] == "測試排程 a"
    assert data["created_at"] is not None and data["updated_at"] is not None


async def test_create_invalid_cron_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    for bad_cron in ("not-a-cron", "0 2 * *", "0 2 * * * *", "0 2 * * x"):
        resp = await client.post(
            "/api/v1/schedules", json=_schedule_payload(cron_expr=bad_cron)
        )
        assert resp.status_code == 400, bad_cron
        _assert_shell(resp.json(), success=False, response_code=400)


async def test_create_duplicate_name_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_schedule(client, "dup")
    resp = await client.post("/api/v1/schedules", json=_schedule_payload("dup"))
    assert resp.status_code == 409
    _assert_shell(resp.json(), success=False, response_code=409)


# ── 查詢 ────────────────────────────────────────────────────────────────
async def test_list_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    for suffix in ("p1", "p2", "p3"):
        await _create_schedule(client, suffix)
    resp = await client.get("/api/v1/schedules", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    # data 禁直接為 array:必為 {items, total, ...}
    assert isinstance(body["data"], dict)
    assert body["data"]["total"] == 3
    assert len(body["data"]["items"]) == 2
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    resp2 = await client.get("/api/v1/schedules", params={"page": 2, "page_size": 2})
    assert len(resp2.json()["data"]["items"]) == 1


async def test_get_detail_and_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client)
    resp = await client.get(f"/api/v1/schedules/{uid}")
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    assert body["data"]["uid"] == uid
    resp = await client.get(f"/api/v1/schedules/{uuid4()}")
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)


# ── 更新 ────────────────────────────────────────────────────────────────
async def test_patch_updates_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client, "patch")
    resp = await client.patch(
        f"/api/v1/schedules/{uid}",
        json={"name": "改名排程", "cron_expr": "30 4 * * 1-5", "description": "改過"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "改名排程"
    assert data["cron_expr"] == "30 4 * * 1-5"
    assert data["description"] == "改過"
    # v1.3:回應不再含 etl_table_uid,固定 job_desc
    assert "etl_table_uid" not in data
    assert data["job_desc"] == "增量同步全部表"


async def test_patch_invalid_cron_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client)
    resp = await client.patch(f"/api/v1/schedules/{uid}", json={"cron_expr": "bad"})
    assert resp.status_code == 400
    _assert_shell(resp.json(), success=False, response_code=400)


async def test_patch_duplicate_name_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_schedule(client, "n1")
    uid2 = await _create_schedule(client, "n2")
    resp = await client.patch(f"/api/v1/schedules/{uid2}", json={"name": "每日排程 n1"})
    assert resp.status_code == 409


# ── 刪除(軟刪除)───────────────────────────────────────────────────────
async def test_delete_is_soft_delete(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client)
    resp = await client.delete(f"/api/v1/schedules/{uid}")
    assert resp.status_code == 200
    _assert_shell(resp.json(), success=True, response_code=200)
    # 清單與明細都看不到
    assert (await client.get(f"/api/v1/schedules/{uid}")).status_code == 404
    list_body = (await client.get("/api/v1/schedules")).json()
    assert list_body["data"]["total"] == 0
    # DB 資料仍在(軟刪除,禁物理刪除)
    async with session_factory() as session:
        schedule = (
            await session.execute(select(Schedule).where(Schedule.uid == UUID(uid)))
        ).scalar_one()
        assert schedule.is_deleted is True


# ── 啟用 / 停用 ─────────────────────────────────────────────────────────
async def test_disable_and_enable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client)
    resp = await client.post(f"/api/v1/schedules/{uid}/disable")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False
    # DB 同步反映(scheduler 依此欄位決定是否派工)
    async with session_factory() as session:
        schedule = (
            await session.execute(select(Schedule).where(Schedule.uid == UUID(uid)))
        ).scalar_one()
        assert schedule.is_enabled is False
    resp = await client.post(f"/api/v1/schedules/{uid}/enable")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is True
