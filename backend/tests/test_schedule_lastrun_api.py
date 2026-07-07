"""task-006 排程列表「上次執行結果」+ sync 語意測試(真實 PostgreSQL 測試 DB)。

涵蓋:
- 建立排程後,ScheduleResponse 含固定 job_desc、last_run_status 尚無執行為 None。
- 手動塞 etl_runs 後,list 取到最新一筆 run 的 status / finished_at。
- create/update 契約不再含 etl_table_uid(送了亦被忽略,回應不含該欄)。
- viewer 讀取 OK。
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
from app.models import EtlRun, Schedule  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402

_ZERO_UUID = UUID(int=0)


# ── fixtures(沿用 test_schedule_api.py 風格)────────────────────────────
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


async def _schedule_pid_by_uid(
    session_factory: async_sessionmaker[AsyncSession], uid: str
) -> int:
    async with session_factory() as session:
        schedule = (
            await session.execute(select(Schedule).where(Schedule.uid == UUID(uid)))
        ).scalar_one()
        return schedule.pid


async def _insert_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schedule_pid: int,
    status: str,
    finished_at: datetime | None,
) -> None:
    async with session_factory() as session:
        session.add(
            EtlRun(
                uid=uuid4(),
                trigger_type="schedule",
                schedule_pid=schedule_pid,
                status=status,
                finished_at=finished_at,
                created_by=_ZERO_UUID,
                updated_by=_ZERO_UUID,
            )
        )
        await session.commit()


# ── 上次執行結果 ─────────────────────────────────────────────────────────
async def test_schedule_job_desc_and_no_run(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_schedule(client, "nr")
    body = (await client.get("/api/v1/schedules")).json()
    item = body["data"]["items"][0]
    assert item["job_desc"] == "增量同步全部表"
    assert item["last_run_status"] is None
    assert item["last_run_finished_at"] is None
    # 契約已移除 etl_table_uid
    assert "etl_table_uid" not in item


async def test_list_reflects_latest_run(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client, "lr")
    pid = await _schedule_pid_by_uid(session_factory, uid)

    # 第一筆 run:success
    await _insert_run(
        session_factory,
        schedule_pid=pid,
        status="success",
        finished_at=datetime(2026, 7, 7, 2, 0, 0),
    )
    item = (await client.get("/api/v1/schedules")).json()["data"]["items"][0]
    assert item["last_run_status"] == "success"
    assert item["last_run_finished_at"] is not None

    # 更新一筆 run:failed → list 取最新
    await _insert_run(
        session_factory,
        schedule_pid=pid,
        status="failed",
        finished_at=datetime(2026, 7, 7, 3, 0, 0),
    )
    item = (await client.get("/api/v1/schedules")).json()["data"]["items"][0]
    assert item["last_run_status"] == "failed"


async def test_detail_reflects_latest_run(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client, "dt")
    pid = await _schedule_pid_by_uid(session_factory, uid)
    await _insert_run(
        session_factory,
        schedule_pid=pid,
        status="partial",
        finished_at=datetime(2026, 7, 7, 4, 0, 0),
    )
    data = (await client.get(f"/api/v1/schedules/{uid}")).json()["data"]
    assert data["job_desc"] == "增量同步全部表"
    assert data["last_run_status"] == "partial"
    assert data["last_run_finished_at"] is not None


# ── 契約:etl_table_uid 已移除 ──────────────────────────────────────────
async def test_create_ignores_etl_table_uid(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post(
        "/api/v1/schedules",
        json=_schedule_payload("ig", etl_table_uid=str(uuid4())),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    # 送了 etl_table_uid 亦被忽略,回應不含該欄且不因未知 uid 而 400
    assert "etl_table_uid" not in data
    assert data["job_desc"] == "增量同步全部表"


async def test_update_ignores_etl_table_uid(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_schedule(client, "up")
    resp = await client.patch(
        f"/api/v1/schedules/{uid}",
        json={"description": "改", "etl_table_uid": str(uuid4())},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["description"] == "改"
    assert "etl_table_uid" not in data


# ── viewer 讀取 ─────────────────────────────────────────────────────────
async def test_viewer_can_read_list(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"]["items"], list)
