"""task-003 角色列表 / 使用者清單 / 角色指派 API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:GET /roles(已登入可讀)、GET /users(admin only + 分頁 + eager load 角色)、
PATCH /users/{uid}/role(admin only + 自降防呆 + 稽核 + 即時生效)。
"""

import os

# app.core.db 於 import 時即建立 engine → 必須先注入測試 env,再 import app 模組
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
TEST_DB_NAME = "data_center_etl_test"

_BASE_URL = f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}"
TEST_DATABASE_URL = f"{_BASE_URL}/{TEST_DB_NAME}"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from typing import Annotated  # noqa: E402

import pytest_asyncio  # noqa: E402
from fastapi import APIRouter, Depends, FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_db, require_admin  # noqa: E402
from app.core.response import success  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import AuditLog  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.schemas.response import ApiResponse  # noqa: E402

# ── 假 admin-only 端點:驗證角色變更即時生效(同 test_auth.py 前例)──────────
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
# 共用測試 DB 的建庫 / create_all / roles seed 已由 tests/conftest.py 的
# `_seed_shared_test_db_roles`(session-scoped autouse)中央處理,本檔不再重複。
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
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def app(session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    fastapi_app = create_app()
    fastapi_app.include_router(_probe_router, prefix="/api/v1")

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    return fastapi_app


def _new_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    # base_url 用 https:cookie 為 secure=True,走 http 不會被 client 回送
    return AsyncClient(transport=transport, base_url="https://testserver")


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with _new_client(app) as ac:
        yield ac


async def _create_user(
    session_factory: async_sessionmaker[AsyncSession],
    username: str,
    password: str,
    role: str,
) -> User:
    async with session_factory() as session:
        password_hash = await hash_password_async(password)
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


# ── GET /roles ──────────────────────────────────────────────────────────
async def test_roles_requires_login(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/roles")
    assert resp.status_code == 401


async def test_member_can_read_roles(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "vera", "vera-password-123", "member")
    await _login(client, "vera", "vera-password-123")
    resp = await client.get("/api/v1/roles")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    codes = sorted(item["code"] for item in body["data"]["items"])
    assert codes == ["admin", "member"]
    assert {"code", "name", "description"} <= body["data"]["items"][0].keys()


# ── GET /users ──────────────────────────────────────────────────────────
async def test_member_hits_users_list_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "vera", "vera-password-123", "member")
    await _login(client, "vera", "vera-password-123")
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 403


async def test_admin_lists_users_with_provider_and_role(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "adam", "adam-password-123", "admin")
    await _create_user(session_factory, "vera", "vera-password-123", "member")
    await _login(client, "adam", "adam-password-123")
    resp = await client.get("/api/v1/users")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] == 2
    item = body["data"]["items"][0]
    assert {"uid", "username", "display_name", "provider", "role"} <= item.keys()
    by_username = {row["username"]: row for row in body["data"]["items"]}
    assert by_username["adam"]["role"] == "admin"
    assert by_username["adam"]["provider"] == "local"
    assert by_username["vera"]["role"] == "member"


# ── PATCH /users/{uid}/role ────────────────────────────────────────────
async def test_member_cannot_assign_role(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    target = await _create_user(session_factory, "riser", "riser-password-123", "member")
    await _create_user(session_factory, "vera", "vera-password-123", "member")
    await _login(client, "vera", "vera-password-123")
    resp = await client.patch(
        f"/api/v1/users/{target.uid}/role", json={"role": "admin"}
    )
    assert resp.status_code == 403


async def test_admin_assigns_role_effective_next_request(
    app: FastAPI, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """升級 member → admin 後,該使用者下一請求即以新角色判定(即時生效);
    反向降回 member 後同請求 403(不發新 token / 不強制重登)。

    admin / riser 各自獨立登入 session(各自獨立 cookie jar),同一 app 實例
    (同一 DB),模擬「admin 指派角色時,riser 沿用既有登入不重登」的真實情境。
    """
    await _create_user(session_factory, "adam", "adam-password-123", "admin")
    riser = await _create_user(session_factory, "riser", "riser-password-123", "member")

    async with _new_client(app) as riser_client, _new_client(app) as admin_client:
        await _login(riser_client, "riser", "riser-password-123")
        assert (await riser_client.post("/api/v1/admin-only-probe")).status_code == 403

        await _login(admin_client, "adam", "adam-password-123")
        resp = await admin_client.patch(
            f"/api/v1/users/{riser.uid}/role", json={"role": "admin"}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["role"] == "admin"

        # 下一請求即生效(riser 沿用同一登入 cookie,守衛每請求讀 DB)
        assert (await riser_client.post("/api/v1/admin-only-probe")).status_code == 200

        # 稽核:action=role_assigned 且 target_uid 正確
        async with session_factory() as session:
            log = (
                await session.execute(
                    select(AuditLog).where(AuditLog.action == "role_assigned")
                )
            ).scalar_one()
            assert log.target_uid == riser.uid

        # DB 角色字串已更新
        async with session_factory() as session:
            row = (
                await session.execute(select(User).where(User.uid == riser.uid))
            ).scalar_one()
            assert row.role == "admin"

        # 反向降回 member 後同請求 403
        resp = await admin_client.patch(
            f"/api/v1/users/{riser.uid}/role", json={"role": "member"}
        )
        assert resp.status_code == 200, resp.text
        assert (await riser_client.post("/api/v1/admin-only-probe")).status_code == 403


async def test_admin_cannot_demote_self(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    admin = await _create_user(session_factory, "adam", "adam-password-123", "admin")
    await _login(client, "adam", "adam-password-123")
    resp = await client.patch(f"/api/v1/users/{admin.uid}/role", json={"role": "member"})
    assert resp.status_code == 403
    body = resp.json()
    assert body["success"] is False
    assert body["response_code"] == 403


async def test_assign_unknown_role_code_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "adam", "adam-password-123", "admin")
    target = await _create_user(session_factory, "riser", "riser-password-123", "member")
    await _login(client, "adam", "adam-password-123")
    resp = await client.patch(
        f"/api/v1/users/{target.uid}/role", json={"role": "ghost-role"}
    )
    assert resp.status_code == 404
    assert resp.status_code != 500
