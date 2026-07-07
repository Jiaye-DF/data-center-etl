"""R-PII-003 audit_logs 稽核測試(真實 PostgreSQL 測試 DB)。

涵蓋:登入成功寫 login_success、登入失敗寫 login_failed(獨立 session,
不因 401 rollback 消失)、viewer 打 GET /audit-logs 403、
admin 讀到分頁結果(最新在前 + action 過濾)。
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
from app.core import db as core_db  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import AuditLog  # noqa: E402
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
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM etl_mappings"))
        await conn.execute(text("DELETE FROM etl_tables"))
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine() -> AsyncIterator[None]:
    # 手動觸發的 run_etl(taskiq 就地執行)走全域 engine 連線池;
    # pytest-asyncio 每測試換 event loop,不釋放會跨 loop 重用連線而失敗
    yield
    await core_db.engine.dispose()


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


async def _audit_rows(
    session_factory: async_sessionmaker[AsyncSession], action: str
) -> list[AuditLog]:
    async with session_factory() as session:
        stmt = (
            select(AuditLog).where(AuditLog.action == action).order_by(AuditLog.pid.asc())
        )
        return list((await session.execute(stmt)).scalars().all())


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    """斷言 ApiResponse 外殼:success / data / detail / response_code。"""
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


# ── 登入成敗稽核 ────────────────────────────────────────────────────────
async def test_login_success_writes_audit(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "alice", "alice-password-123", "admin")
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "alice-password-123"}
    )
    assert resp.status_code == 200
    rows = await _audit_rows(session_factory, "login_success")
    assert len(rows) == 1
    row = rows[0]
    assert row.actor_username == "alice"
    assert row.actor_uid is not None
    # detail 禁含密碼內容
    assert row.detail is not None and "alice-password-123" not in row.detail


async def test_login_failed_audit_survives_rollback(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """登入失敗 raise AppError → get_db rollback;稽核走獨立 session 不得被回滾。"""
    await _create_user(session_factory, "alice", "alice-password-123", "admin")
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    # 不存在帳號的失敗也要留痕(匿名事件:actor_uid 為 NULL)
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "whatever-123"}
    )
    assert resp.status_code == 401
    rows = await _audit_rows(session_factory, "login_failed")
    assert [r.actor_username for r in rows] == ["alice", "nobody"]
    for row in rows:
        assert row.actor_uid is None
        assert row.detail is not None
        assert "wrong-password" not in row.detail and "whatever-123" not in row.detail
    # 登入失敗不得留下 login_success
    assert await _audit_rows(session_factory, "login_success") == []


# ── 查詢 API:權限與分頁 ────────────────────────────────────────────────
async def test_viewer_get_audit_logs_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    resp = await client.get("/api/v1/audit-logs")
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


async def test_admin_list_audit_logs_pagination_and_filter(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # admin 登入成功(1 筆 login_success)+ 兩次密碼錯誤(2 筆 login_failed)
    await _login_as(client, session_factory, "admin")
    for _ in range(2):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "admin-user", "password": "definitely-wrong-pw"},
        )
        assert resp.status_code == 401
    resp = await client.get("/api/v1/audit-logs", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    data = body["data"]
    assert isinstance(data, dict)
    assert data["total"] == 3
    assert data["page"] == 1 and data["page_size"] == 2
    # 最新在前:兩筆 login_failed
    assert [item["action"] for item in data["items"]] == [
        "login_failed",
        "login_failed",
    ]
    # 回應排除內部欄(pid / is_deleted / created_by / updated_by)
    item = data["items"][0]
    assert set(item.keys()) == {
        "uid",
        "actor_uid",
        "actor_username",
        "action",
        "target_type",
        "target_uid",
        "detail",
        "created_at",
    }
    # 第二頁:剩 login_success
    resp2 = await client.get("/api/v1/audit-logs", params={"page": 2, "page_size": 2})
    assert [item["action"] for item in resp2.json()["data"]["items"]] == ["login_success"]
    # action 過濾
    resp3 = await client.get("/api/v1/audit-logs", params={"action": "login_failed"})
    body3 = resp3.json()
    assert body3["data"]["total"] == 2
    assert all(
        item["action"] == "login_failed" for item in body3["data"]["items"]
    )
