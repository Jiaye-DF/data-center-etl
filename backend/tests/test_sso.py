"""task-003 DF-SSO 後端整合測試(中央以 respx mock;真實 PostgreSQL 測試 DB)。

涵蓋:callback 換 token / 首次登入建 viewer / 重複登入不重建 /
back-channel logout 使 session 失效,以及 /me / /logout 契約行為。
"""

import asyncio
import hashlib
import hmac
import json
import os
import time

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
# DF-SSO 測試設定(env 注入,無硬編於 app 程式碼)
os.environ["SSO_URL"] = "https://sso.test"
os.environ["SSO_APP_ID"] = "test-app-id"
os.environ["SSO_APP_SECRET"] = "test-sso-app-secret"
os.environ["FRONTEND_URL"] = "http://localhost:3000"

SSO_BASE = os.environ["SSO_URL"]
SSO_APP_SECRET = os.environ["SSO_APP_SECRET"]
FRONTEND_URL = os.environ["FRONTEND_URL"]

from collections.abc import AsyncIterator  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import respx  # noqa: E402
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
from app.models.user import User  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services import sso_service  # noqa: E402

CENTRAL_USER = {
    "userId": "azure-oid-001",
    "email": "sso.user@df-recycle.com.tw",
    "name": "SSO 使用者",
    "erpData": None,
    "loginAt": "2026-07-03T10:00:00.000Z",
}


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


@pytest.fixture(autouse=True)
def _reset_sso_revocations() -> None:
    """各測試間清空撤銷註記,避免 process-local 狀態外溢。"""
    sso_service.reset_sso_revocations()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(
    db_engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
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


# ── helpers ─────────────────────────────────────────────────────────────
def _mock_central_ok() -> respx.Route:
    """中央 exchange + me 都成功;回傳 exchange route 供斷言。"""
    exchange_route = respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(200, json={"token": "central-token-1"})
    )
    respx.get(f"{SSO_BASE}/api/auth/me").mock(
        return_value=httpx.Response(200, json={"user": CENTRAL_USER})
    )
    return exchange_route


def _sign(user_id: str, timestamp: int, secret: str = SSO_APP_SECRET) -> str:
    return hmac.new(
        secret.encode("utf-8"), f"{user_id}:{timestamp}".encode(), hashlib.sha256
    ).hexdigest()


async def _sso_login(client: AsyncClient, code: str = "auth-code-1") -> None:
    resp = await client.get("/api/v1/sso/callback", params={"code": code})
    assert resp.status_code == 302, resp.text
    assert resp.headers["location"] == f"{FRONTEND_URL}/"


# ── callback:code 換 token(respx mock)─────────────────────────────────
@respx.mock
async def test_callback_exchanges_code_and_sets_cookie(client: AsyncClient) -> None:
    exchange_route = _mock_central_ok()
    resp = await client.get("/api/v1/sso/callback", params={"code": "auth-code-1"})
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/"
    set_cookie = resp.headers["set-cookie"]
    assert "access_token=" in set_cookie
    assert "HttpOnly" in set_cookie
    # exchange 帶 code / client_id / client_secret(server-to-server,值來自 env)
    assert exchange_route.called
    sent = json.loads(exchange_route.calls.last.request.content)
    assert sent["code"] == "auth-code-1"
    assert sent["client_id"] == os.environ["SSO_APP_ID"]
    assert sent["client_secret"] == SSO_APP_SECRET


@respx.mock
async def test_callback_without_code_redirects_error(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/sso/callback")
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/login?error=no_code"


@respx.mock
async def test_callback_exchange_failed_redirects_error(client: AsyncClient) -> None:
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(400, json={"error": "exchange_failed"})
    )
    resp = await client.get("/api/v1/sso/callback", params={"code": "bad-code"})
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/login?error=exchange_failed"
    assert "set-cookie" not in resp.headers


@respx.mock
async def test_callback_central_unreachable_redirects_error(client: AsyncClient) -> None:
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        side_effect=httpx.ConnectError("boom")
    )
    resp = await client.get("/api/v1/sso/callback", params={"code": "auth-code-1"})
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/login?error=exchange_error"


# ── 首次登入建 user(role=viewer)/ 重複登入不重建 ───────────────────────
@respx.mock
async def test_first_sso_login_creates_viewer_user(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_central_ok()
    await _sso_login(client)
    async with session_factory() as session:
        stmt = select(User).where(User.sso_subject == CENTRAL_USER["userId"])
        user = (await session.execute(stmt)).scalar_one()
        assert user.role == "viewer"
        assert user.password_hash is None
        assert user.username == CENTRAL_USER["email"]


@respx.mock
async def test_repeat_sso_login_does_not_recreate_user(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _mock_central_ok()
    await _sso_login(client, code="code-1")
    async with session_factory() as session:
        stmt = select(User).where(User.sso_subject == CENTRAL_USER["userId"])
        first = (await session.execute(stmt)).scalar_one()
    await _sso_login(client, code="code-2")
    async with session_factory() as session:
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].uid == first.uid
        assert rows[0].role == "viewer"


@respx.mock
async def test_sso_login_links_existing_local_user_and_keeps_role(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """同帳號(email)已有本地使用者 → 綁定 sso_subject,不重建、保留原角色。"""
    email = str(CENTRAL_USER["email"])
    async with session_factory() as session:
        password_hash = await hash_password_async("local-password-123")
        await UserRepository(session).create(
            username=email, password_hash=password_hash, role="admin"
        )
        await session.commit()
    _mock_central_ok()
    await _sso_login(client)
    async with session_factory() as session:
        stmt = select(User).where(User.username == email)
        rows = (await session.execute(stmt)).scalars().all()
        assert len(rows) == 1
        assert rows[0].sso_subject == CENTRAL_USER["userId"]
        assert rows[0].role == "admin"
        assert rows[0].password_hash is not None


# ── /me:即時回源中央 ────────────────────────────────────────────────────
@respx.mock
async def test_sso_me_returns_local_role_and_central_user(client: AsyncClient) -> None:
    _mock_central_ok()
    await _sso_login(client)
    resp = await client.get("/api/v1/sso/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["provider"] == "sso"
    assert data["role"] == "viewer"
    assert data["username"] == CENTRAL_USER["email"]
    assert data["sso_user"]["user_id"] == CENTRAL_USER["userId"]


async def test_sso_me_without_cookie_401_no_token(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/sso/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "no_token"


@respx.mock
async def test_sso_me_central_401_clears_cookie(client: AsyncClient) -> None:
    """中央 session 已失效 → 401 session_expired 並刪本地 cookie(契約 #1)。"""
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(200, json={"token": "central-token-1"})
    )
    respx.get(f"{SSO_BASE}/api/auth/me").mock(
        side_effect=[
            httpx.Response(200, json={"user": CENTRAL_USER}),  # callback 期間
            httpx.Response(401, json={"error": "session_expired"}),
        ]
    )
    await _sso_login(client)
    resp = await client.get("/api/v1/sso/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "session_expired"
    assert "access_token" not in client.cookies
    # cookie 已刪 → 再打 me 回 no_token
    resp = await client.get("/api/v1/sso/me")
    assert resp.json()["detail"] == "no_token"


@respx.mock
async def test_sso_me_central_unreachable_502_keeps_cookie(client: AsyncClient) -> None:
    """中央不可達 → 502 sso_unreachable 且不刪 cookie(避免網路抖動踢人)。"""
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(200, json={"token": "central-token-1"})
    )
    respx.get(f"{SSO_BASE}/api/auth/me").mock(
        side_effect=[
            httpx.Response(200, json={"user": CENTRAL_USER}),  # callback 期間
            httpx.ConnectError("boom"),
        ]
    )
    await _sso_login(client)
    resp = await client.get("/api/v1/sso/me")
    assert resp.status_code == 502
    assert resp.json()["detail"] == "sso_unreachable"
    assert client.cookies.get("access_token") is not None


# ── back-channel logout:HMAC 驗章 + session 失效 ───────────────────────
@respx.mock
async def test_back_channel_logout_invalidates_session(client: AsyncClient) -> None:
    _mock_central_ok()  # 中央 me 持續回 200 → 失效必來自本地撤銷
    await _sso_login(client)
    assert (await client.get("/api/v1/sso/me")).status_code == 200

    user_id = str(CENTRAL_USER["userId"])
    ts = int(time.time() * 1000)
    resp = await client.post(
        "/api/v1/sso/back-channel-logout",
        json={"user_id": user_id, "timestamp": ts, "signature": _sign(user_id, ts)},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["revoked"] is True

    resp = await client.get("/api/v1/sso/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "session_expired"


@respx.mock
async def test_back_channel_logout_invalid_signature_401(client: AsyncClient) -> None:
    user_id = str(CENTRAL_USER["userId"])
    ts = int(time.time() * 1000)
    resp = await client.post(
        "/api/v1/sso/back-channel-logout",
        json={
            "user_id": user_id,
            "timestamp": ts,
            "signature": _sign(user_id, ts, secret="wrong-secret"),
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_signature"


@respx.mock
async def test_back_channel_logout_expired_timestamp_401(client: AsyncClient) -> None:
    user_id = str(CENTRAL_USER["userId"])
    ts = int(time.time() * 1000) - 31_000  # 超過 30s drift
    resp = await client.post(
        "/api/v1/sso/back-channel-logout",
        json={"user_id": user_id, "timestamp": ts, "signature": _sign(user_id, ts)},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "timestamp_expired"


@respx.mock
async def test_back_channel_logout_does_not_affect_other_user(client: AsyncClient) -> None:
    """模式 B:back-channel 只撤銷該 user 的 SSO session,其他使用者不受影響。"""
    _mock_central_ok()
    await _sso_login(client)
    other_id = "azure-oid-999"
    ts = int(time.time() * 1000)
    resp = await client.post(
        "/api/v1/sso/back-channel-logout",
        json={"user_id": other_id, "timestamp": ts, "signature": _sign(other_id, ts)},
    )
    assert resp.status_code == 200
    assert (await client.get("/api/v1/sso/me")).status_code == 200


# ── /logout:通知中央 + 跟隨 logout_url + 刪 cookie ──────────────────────
@respx.mock
async def test_logout_follows_central_logout_url_and_clears_cookie(
    client: AsyncClient,
) -> None:
    _mock_central_ok()
    logout_route = respx.post(f"{SSO_BASE}/api/auth/logout").mock(
        return_value=httpx.Response(200, json={"logout_url": f"{SSO_BASE}/ad-logout"})
    )
    await _sso_login(client)
    resp = await client.get("/api/v1/sso/logout")
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{SSO_BASE}/ad-logout"
    # 契約 #2:必先 POST 中央(Bearer 帶中央 token)
    assert logout_route.called
    auth_header = logout_route.calls.last.request.headers["Authorization"]
    assert auth_header == "Bearer central-token-1"
    # 同一 response 刪本地 cookie → 再打 me 回 no_token
    assert "access_token" not in client.cookies
    assert (await client.get("/api/v1/sso/me")).json()["detail"] == "no_token"


@respx.mock
async def test_logout_central_unreachable_falls_back_and_clears_cookie(
    client: AsyncClient,
) -> None:
    _mock_central_ok()
    respx.post(f"{SSO_BASE}/api/auth/logout").mock(side_effect=httpx.ConnectError("boom"))
    await _sso_login(client)
    resp = await client.get("/api/v1/sso/logout")
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/login?logged_out=1"
    assert "access_token" not in client.cookies


async def test_logout_without_cookie_redirects_fallback(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/sso/logout")
    assert resp.status_code == 302
    assert resp.headers["location"] == f"{FRONTEND_URL}/login?logged_out=1"


# ── 通用守衛 provider 分流(模式 B 契約 #1;fixed.md §8 收口)──────────────
@respx.mock
async def test_general_api_with_sso_token_revalidates_central(client: AsyncClient) -> None:
    """SSO token 走一般 API(/auth/me)也回源中央;成功時 provider=sso。"""
    _mock_central_ok()
    await _sso_login(client)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["provider"] == "sso"
    assert data["role"] == "viewer"


@respx.mock
async def test_general_api_sso_token_central_401_rejected(client: AsyncClient) -> None:
    """中央 session 已清 → 一般 API 立即 401,不等 JWT 過期(契約:清 session 即失效)。"""
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(200, json={"token": "central-token-1"})
    )
    respx.get(f"{SSO_BASE}/api/auth/me").mock(
        side_effect=[
            httpx.Response(200, json={"user": CENTRAL_USER}),  # callback 期間
            httpx.Response(401, json={"error": "session_expired"}),
        ]
    )
    await _sso_login(client)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@respx.mock
async def test_general_api_sso_token_central_unreachable_502(client: AsyncClient) -> None:
    """中央不可達 → 502(不視為登出)。"""
    respx.post(f"{SSO_BASE}/api/auth/sso/exchange").mock(
        return_value=httpx.Response(200, json={"token": "central-token-1"})
    )
    respx.get(f"{SSO_BASE}/api/auth/me").mock(
        side_effect=[
            httpx.Response(200, json={"user": CENTRAL_USER}),  # callback 期間
            httpx.ConnectError("boom"),
        ]
    )
    await _sso_login(client)
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 502


@respx.mock
async def test_general_api_sso_token_after_back_channel_revoke_401(
    client: AsyncClient,
) -> None:
    """back-channel 撤銷後,一般 API 對既發 SSO token 一律 401。"""
    _mock_central_ok()  # 中央 me 持續 200 → 失效必來自本地撤銷
    await _sso_login(client)
    assert (await client.get("/api/v1/auth/me")).status_code == 200
    user_id = str(CENTRAL_USER["userId"])
    ts = int(time.time() * 1000)
    resp = await client.post(
        "/api/v1/sso/back-channel-logout",
        json={"user_id": user_id, "timestamp": ts, "signature": _sign(user_id, ts)},
    )
    assert resp.status_code == 200
    assert (await client.get("/api/v1/auth/me")).status_code == 401


@respx.mock
async def test_general_api_with_local_token_skips_central(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """本地 token 走本地驗證,不打中央(respx 未 mock 任何路由,誤打即噴錯);provider=local。"""
    async with session_factory() as session:
        password_hash = await hash_password_async("local-password-123")
        await UserRepository(session).create(
            username="local-user", password_hash=password_hash, role="admin"
        )
        await session.commit()
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "local-user", "password": "local-password-123"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["provider"] == "local"
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["data"]["provider"] == "local"
