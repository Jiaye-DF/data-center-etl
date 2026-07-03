"""task-002 本地帳密登入 / init_admin 冪等 / 角色權限測試(真實 PostgreSQL 測試 DB)。"""

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
INIT_ADMIN_USERNAME = os.environ["INIT_ADMIN_USERNAME"]
INIT_ADMIN_PASSWORD = os.environ["INIT_ADMIN_PASSWORD"]

from collections.abc import AsyncIterator  # noqa: E402
from typing import Annotated  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi import APIRouter, Depends  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app import models  # noqa: E402, F401  匯入全部 model 讓 create_all 建齊資料表
from app.api.deps import get_db, require_admin  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.response import success  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.schemas.response import ApiResponse  # noqa: E402
from app.services.auth_service import ensure_init_admin  # noqa: E402

# ── 假 admin-only 端點:驗證 require_admin(viewer 一律 403)──────────────
_probe_router = APIRouter()


@_probe_router.post(
    "/admin-only-probe",
    response_model=ApiResponse[dict[str, str]],
    summary="測試用 admin-only 假端點",
)
async def _admin_only_probe(
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[dict[str, str]]:
    return success(data={"ok": "true"})


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
async def _clean_users(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(
    db_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.include_router(_probe_router, prefix="/api/v1")

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
    password: str | None,
    role: str,
) -> User:
    async with session_factory() as session:
        password_hash = await hash_password_async(password) if password is not None else None
        user = await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()
        return user


async def _login(client: AsyncClient, username: str, password: str) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


# ── 登入 ────────────────────────────────────────────────────────────────
async def test_login_success_sets_httponly_cookie(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "alice", "alice-password-123", "admin")
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "alice-password-123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["response_code"] == 200
    assert body["data"]["username"] == "alice"
    assert body["data"]["role"] == "admin"
    # 回應不得帶密碼相關欄位
    assert "password" not in body["data"]
    assert "password_hash" not in body["data"]
    set_cookie = resp.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie


async def test_login_wrong_password_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "alice", "alice-password-123", "admin")
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-password"}
    )
    assert resp.status_code == 401
    body = resp.json()
    assert body["success"] is False
    assert body["response_code"] == 401


async def test_login_unknown_user_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "whatever-123"}
    )
    assert resp.status_code == 401


async def test_login_sso_only_user_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """無本地密碼(SSO-only)使用者走本地登入一律 401。"""
    await _create_user(session_factory, "sso-only", None, "viewer")
    resp = await client.post(
        "/api/v1/auth/login", json={"username": "sso-only", "password": "anything-123"}
    )
    assert resp.status_code == 401


# ── me / 登出 ───────────────────────────────────────────────────────────
async def test_me_requires_login(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_me_after_login(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "bob", "bob-password-123", "viewer")
    await _login(client, "bob", "bob-password-123")
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["username"] == "bob"
    assert body["data"]["role"] == "viewer"


async def test_logout_clears_cookie(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "bob", "bob-password-123", "viewer")
    await _login(client, "bob", "bob-password-123")
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    resp = await client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401


# ── 角色權限:viewer 打 admin-only 一律 403 ─────────────────────────────
async def test_viewer_hits_admin_only_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "vera", "vera-password-123", "viewer")
    await _login(client, "vera", "vera-password-123")
    resp = await client.post("/api/v1/admin-only-probe")
    assert resp.status_code == 403
    body = resp.json()
    assert body["success"] is False
    assert body["response_code"] == 403


async def test_admin_hits_admin_only_200(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "adam", "adam-password-123", "admin")
    await _login(client, "adam", "adam-password-123")
    resp = await client.post("/api/v1/admin-only-probe")
    assert resp.status_code == 200


async def test_admin_only_without_login_401(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/admin-only-probe")
    assert resp.status_code == 401


# ── Settings fail-fast:缺 INIT_ADMIN_* env 即驗證失敗 ──────────────────
def test_settings_missing_init_admin_env_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INIT_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INIT_ADMIN_PASSWORD", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        # 隔離本機 .env,只看 env 變數(缺 INIT_ADMIN_* 必須驗證失敗)
        Settings(_env_file=None, DATABASE_URL=TEST_DATABASE_URL)  # type: ignore[call-arg]
    message = str(exc_info.value)
    assert "INIT_ADMIN_USERNAME" in message
    assert "INIT_ADMIN_PASSWORD" in message


def test_settings_with_init_admin_env_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INIT_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("INIT_ADMIN_PASSWORD", raising=False)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None,
        DATABASE_URL=TEST_DATABASE_URL,
        INIT_ADMIN_USERNAME="ok-admin",
        INIT_ADMIN_PASSWORD="ok-password-123",
    )
    assert settings.INIT_ADMIN_USERNAME == "ok-admin"


# ── init_admin:冪等(重複啟動不重建、不覆寫密碼)────────────────────────
async def test_init_admin_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await ensure_init_admin(session) is True
        await session.commit()

    async with session_factory() as session:
        stmt = select(User).where(User.username == INIT_ADMIN_USERNAME)
        admin = (await session.execute(stmt)).scalar_one()
        first_uid = admin.uid
        first_hash = admin.password_hash
        assert admin.role == "admin"
        assert first_hash is not None
        assert first_hash != INIT_ADMIN_PASSWORD  # 只存雜湊,禁明文

    # 模擬第二次啟動:不重建、不覆寫
    async with session_factory() as session:
        assert await ensure_init_admin(session) is False
        await session.commit()

    async with session_factory() as session:
        stmt = select(User).where(User.username == INIT_ADMIN_USERNAME)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].uid == first_uid
        assert rows[0].password_hash == first_hash


async def test_init_admin_can_login(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """env 注入的初始管理員可用該帳密登入。"""
    async with session_factory() as session:
        await ensure_init_admin(session)
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": INIT_ADMIN_USERNAME, "password": INIT_ADMIN_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"
