"""task-004 對外 token 端點測試(真實 PostgreSQL 測試 DB + 記憶體 Redis 替身)。

涵蓋:正常取證與 JWT 內容;四種失敗回應體同構且皆 401 invalid_client;/refresh_token
四情境;雙密鑰並存與汰換;停用即時生效;限流與連續失敗鎖定回 429 + Retry-After。
"""

import os

# app.core.config / app.core.db 於 import 時即讀 env → 必須先注入測試 env,再 import app 模組
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/data_center_etl_test"
)
CLIENT_JWT_SECRET = "test-client-jwt-secret-at-least-32-chars"

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")
os.environ["CLIENT_JWT_SECRET"] = CLIENT_JWT_SECRET

import math  # noqa: E402
from collections.abc import AsyncIterator, Sequence  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from uuid import UUID  # noqa: E402

import bcrypt  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.api_client_router.common import rate_limit  # noqa: E402
from app.api_client_router.common.auth import (  # noqa: E402
    CLIENT_JWT_ALGORITHM,
    CLIENT_JWT_EXPIRE_SECONDS,
    CLIENT_JWT_ISSUER,
    sign_client_jwt,
    verify_client_jwt,
)
from app.api_client_router.common.rate_limit import (  # noqa: E402
    AUTH_FAIL_THRESHOLD,
    AUTH_LOCK_TTL_SECONDS,
    DEFAULT_LIMIT_PER_MINUTE,
)
from app.main import create_app  # noqa: E402
from app.models.api_client_user import (  # noqa: E402
    CLIENT_STATUS_DISABLED,
    CLIENT_STATUS_ENABLED,
)
from app.repositories.api_client_repo import ApiClientRepository  # noqa: E402

_TOKEN_URL = "/api/client/v1.0/token"
_REFRESH_URL = "/api/client/v1.0/refresh_token"
_ENVELOPE_KEYS = {"success", "response_code", "detail", "data"}
_ACTOR_UID = UUID("00000000-0000-0000-0000-000000000000")
# 測試專用低成本雜湊:限流測試需連發 31 次取證,預設 rounds 會讓單檔跑數十秒
_BCRYPT_TEST_ROUNDS = 4

CLIENT_A = "dc_client_a"
CLIENT_B = "dc_client_b"
SECRET_A = "secret-alpha-0123456789"
SECRET_B = "secret-beta-0123456789"


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_TEST_ROUNDS)).decode(
        "ascii"
    )


class FakeRedis:
    """記憶體 Redis 替身:實作限流模組用到的 ZSET / 字串 / TTL 指令子集(時鐘固定不前進)。"""

    def __init__(self) -> None:
        self.clock_ms = 1_700_000_000_000
        self._zsets: dict[str, dict[str, float]] = {}
        self._values: dict[str, str] = {}
        self._expire_at: dict[str, int] = {}

    @staticmethod
    def _bound(raw: str | float | int, fallback: float) -> float:
        if isinstance(raw, str) and raw.lstrip("+-").lower() == "inf":
            return fallback
        return float(raw)

    def _in_range(self, key: str, min: str | float, max: str | float) -> list[tuple[str, float]]:
        lo = self._bound(min, float("-inf"))
        hi = self._bound(max, float("inf"))
        pairs = [(m, s) for m, s in self._zsets.get(key, {}).items() if lo <= s <= hi]
        return sorted(pairs, key=lambda pair: (pair[1], pair[0]))

    async def zadd(self, name: str, mapping: dict[str, float]) -> int:
        zset = self._zsets.setdefault(name, {})
        for member, score in mapping.items():
            zset[member] = float(score)
        return len(mapping)

    async def zremrangebyscore(self, name: str, min: str | float, max: str | float) -> int:
        doomed = self._in_range(name, min, max)
        for member, _ in doomed:
            del self._zsets[name][member]
        return len(doomed)

    async def zcount(self, name: str, min: str | float, max: str | float) -> int:
        return len(self._in_range(name, min, max))

    async def zrangebyscore(
        self,
        name: str,
        min: str | float,
        max: str | float,
        start: int | None = None,
        num: int | None = None,
        withscores: bool = False,
    ) -> list[tuple[str, float]] | list[str]:
        pairs = self._in_range(name, min, max)
        if start is not None and num is not None:
            pairs = pairs[start : start + num]
        return pairs if withscores else [member for member, _ in pairs]

    async def get(self, name: str) -> str | None:
        return self._values.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self._values[name] = value
        if ex is not None:
            self._expire_at[name] = self.clock_ms + ex * 1000
        return True

    async def incr(self, name: str) -> int:
        value = int(self._values.get(name, "0")) + 1
        self._values[name] = str(value)
        return value

    async def expire(self, name: str, seconds: int) -> bool:
        if name not in self._zsets and name not in self._values:
            return False
        self._expire_at[name] = self.clock_ms + seconds * 1000
        return True

    async def ttl(self, name: str) -> int:
        if name not in self._zsets and name not in self._values:
            return -2
        expire_at = self._expire_at.get(name)
        if expire_at is None:
            return -1
        return math.ceil((expire_at - self.clock_ms) / 1000)

    async def delete(self, *names: str) -> int:
        removed = 0
        for name in names:
            if name in self._zsets or name in self._values:
                self._zsets.pop(name, None)
                self._values.pop(name, None)
                self._expire_at.pop(name, None)
                removed += 1
        return removed


# ── fixtures(建庫 / create_all 由 tests/conftest.py 中央處理)──────────────
@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean_tables(db_engine: AsyncEngine) -> None:
    # 僅測試 DB;非業務環境的物理刪除(先子表後父表)
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM api_client_secrets"))
        await conn.execute(text("DELETE FROM api_client_users"))


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    # 每個測試一份新替身:限流計數 / 失敗計數天然隔離(core.redis fake 未實作 ZSET)
    fake = FakeRedis()
    monkeypatch.setattr(rate_limit, "get_redis", lambda: fake)
    monkeypatch.setattr(rate_limit, "_now_ms", lambda: fake.clock_ms)
    return fake


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def app(session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    fastapi_app = create_app()

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


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


# ── 輔助 ─────────────────────────────────────────────────────────────────
async def _seed_client(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    client_id: str = CLIENT_A,
    secrets: Sequence[str] = (SECRET_A,),
    status: str = CLIENT_STATUS_ENABLED,
    soft_deleted: bool = False,
    rate_limit_per_minute: int = DEFAULT_LIMIT_PER_MINUTE,
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        seeded = await repo.create(
            client_id=client_id,
            name=f"測試系統 {client_id}",
            status=status,
            rate_limit_per_minute=rate_limit_per_minute,
            actor_uid=_ACTOR_UID,
        )
        for plain in secrets:
            await repo.add_secret(seeded, secret_hash=_hash(plain), actor_uid=_ACTOR_UID)
        if soft_deleted:
            await repo.soft_delete(seeded, actor_uid=_ACTOR_UID)
        await session.commit()


async def _set_status(
    session_factory: async_sessionmaker[AsyncSession], client_id: str, status: str
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        record = await repo.get_by_client_id(client_id)
        assert record is not None
        await repo.update(record[0], status=status, actor_uid=_ACTOR_UID)
        await session.commit()


async def _retire_oldest_secret(
    session_factory: async_sessionmaker[AsyncSession], client_id: str
) -> None:
    async with session_factory() as session:
        repo = ApiClientRepository(session)
        record = await repo.get_by_client_id(client_id)
        assert record is not None
        await repo.retire_secret(record[1][0], actor_uid=_ACTOR_UID)
        await session.commit()


def _expired_token(client_id: str, *, secret: str = CLIENT_JWT_SECRET) -> str:
    issued_at = int(datetime.now(UTC).timestamp()) - CLIENT_JWT_EXPIRE_SECONDS * 2
    return jwt.encode(
        {
            "sub": client_id,
            "iat": issued_at,
            "exp": issued_at + CLIENT_JWT_EXPIRE_SECONDS,
            "iss": CLIENT_JWT_ISSUER,
        },
        secret,
        algorithm=CLIENT_JWT_ALGORITHM,
    )


# ── 正常取證 ─────────────────────────────────────────────────────────────
async def test_token_success_returns_envelope_and_jwt(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    resp = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["success"] is True
    assert body["response_code"] == 200
    assert isinstance(body["detail"], str)

    assert len(body["data"]) == 1
    issued = body["data"][0]
    assert set(issued) == {"access_token", "token_type", "expires_in"}
    assert issued["token_type"] == "Bearer"
    assert issued["expires_in"] == CLIENT_JWT_EXPIRE_SECONDS

    payload = verify_client_jwt(str(issued["access_token"]))
    assert payload["sub"] == CLIENT_A
    assert payload["exp"] - payload["iat"] == CLIENT_JWT_EXPIRE_SECONDS  # type: ignore[operator]


async def test_secret_via_query_string_is_rejected(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    resp = await client.post(
        f"{_TOKEN_URL}?client_id={CLIENT_A}&client_secret={SECRET_A}", json={}
    )
    assert resp.status_code == 422
    body = resp.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["success"] is False
    assert body["response_code"] == 422
    assert body["data"] == []


async def test_incomplete_body_returns_client_envelope_422(client: AsyncClient) -> None:
    resp = await client.post(_TOKEN_URL, json={"client_id": CLIENT_A})
    assert resp.status_code == 422
    assert resp.json()["data"] == []


# ── 401 四情境同構(防列舉)────────────────────────────────────────────────
async def test_all_auth_failures_are_indistinguishable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory, client_id=CLIENT_A)
    await _seed_client(session_factory, client_id="dc_disabled", status=CLIENT_STATUS_DISABLED)
    await _seed_client(session_factory, client_id="dc_deleted", soft_deleted=True)

    cases = [
        (CLIENT_A, "wrong-secret"),  # 密碼錯
        ("dc_unknown", SECRET_A),  # client 不存在
        ("dc_disabled", SECRET_A),  # 已停用
        ("dc_deleted", SECRET_A),  # 已軟刪
    ]
    bodies: list[dict[str, object]] = []
    for client_id, secret in cases:
        resp = await client.post(
            _TOKEN_URL, json={"client_id": client_id, "client_secret": secret}
        )
        assert resp.status_code == 401
        bodies.append(resp.json())

    assert bodies[0] == {
        "success": False,
        "response_code": 401,
        "detail": "invalid_client",
        "data": [],
    }
    assert all(body == bodies[0] for body in bodies)


async def test_disabled_after_success_rejects_next_call(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    first = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert first.status_code == 200

    await _set_status(session_factory, CLIENT_A, CLIENT_STATUS_DISABLED)
    second = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert second.status_code == 401
    assert second.json()["detail"] == "invalid_client"


# ── 雙密鑰並存 / 汰換 ─────────────────────────────────────────────────────
async def test_both_active_secrets_work_and_retired_one_rejected(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory, secrets=(SECRET_A, SECRET_B))
    for secret in (SECRET_A, SECRET_B):
        resp = await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": secret}
        )
        assert resp.status_code == 200, resp.text

    await _retire_oldest_secret(session_factory, CLIENT_A)
    old = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert old.status_code == 401
    new = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_B}
    )
    assert new.status_code == 200, new.text


# ── /refresh_token ───────────────────────────────────────────────────────
async def test_refresh_with_expired_token_issues_new_token(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    expired = _expired_token(CLIENT_A)
    resp = await client.post(
        _REFRESH_URL,
        json={
            "client_id": CLIENT_A,
            "client_secret": SECRET_A,
            "access_token": expired,
        },
    )
    assert resp.status_code == 200, resp.text
    issued = resp.json()["data"][0]
    payload = verify_client_jwt(str(issued["access_token"]))
    assert payload["sub"] == CLIENT_A
    assert issued["expires_in"] == CLIENT_JWT_EXPIRE_SECONDS
    old_payload = verify_client_jwt(expired, verify_exp=False)
    assert payload["exp"] > old_payload["exp"]  # type: ignore[operator]


async def test_refresh_with_tampered_signature_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    token, _ = sign_client_jwt(CLIENT_A)
    header, payload, signature = token.split(".")
    resp = await client.post(
        _REFRESH_URL,
        json={
            "client_id": CLIENT_A,
            "client_secret": SECRET_A,
            "access_token": f"{header}.{payload}.{signature[:-3]}xyz",
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_client"


async def test_refresh_with_other_clients_token_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory, client_id=CLIENT_A, secrets=(SECRET_A,))
    await _seed_client(session_factory, client_id=CLIENT_B, secrets=(SECRET_B,))
    token_a, _ = sign_client_jwt(CLIENT_A)
    resp = await client.post(
        _REFRESH_URL,
        json={
            "client_id": CLIENT_B,
            "client_secret": SECRET_B,
            "access_token": token_a,
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_client"


async def test_refresh_with_valid_token_but_wrong_secret_401(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    token, _ = sign_client_jwt(CLIENT_A)
    resp = await client.post(
        _REFRESH_URL,
        json={
            "client_id": CLIENT_A,
            "client_secret": "wrong-secret",
            "access_token": token,
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_client"


# ── 限流 / 連續失敗鎖定 ───────────────────────────────────────────────────
async def test_rate_limit_blocks_request_over_minute_limit(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    for _ in range(DEFAULT_LIMIT_PER_MINUTE):
        resp = await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
        )
        assert resp.status_code == 200, resp.text

    blocked = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    body = blocked.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["success"] is False
    assert body["response_code"] == 429
    assert body["data"] == []


async def test_rate_limit_uses_per_client_db_limit(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory, rate_limit_per_minute=2)
    for _ in range(2):
        assert (
            await client.post(
                _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
            )
        ).status_code == 200
    assert (
        await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
        )
    ).status_code == 429


async def test_unknown_client_id_uses_default_limit(
    client: AsyncClient, fake_redis: FakeRedis
) -> None:
    # 未知 client 一律用預設上限計數(防列舉爆破:不因查無此人而跳過限流)
    for _ in range(AUTH_FAIL_THRESHOLD):
        assert (
            await client.post(
                _TOKEN_URL, json={"client_id": "dc_unknown", "client_secret": "x"}
            )
        ).status_code == 401
    counted = await fake_redis.zcount(rate_limit.rate_limit_key("dc_unknown"), "-inf", "+inf")
    assert counted == AUTH_FAIL_THRESHOLD


async def test_locked_after_consecutive_auth_failures(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_client(session_factory)
    for _ in range(AUTH_FAIL_THRESHOLD):
        resp = await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": "wrong-secret"}
        )
        assert resp.status_code == 401

    # 第 6 次即使密碼正確也被鎖定擋下(429 + Retry-After 為鎖剩餘秒數)
    locked = await client.post(
        _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
    )
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) == AUTH_LOCK_TTL_SECONDS
    assert locked.json()["data"] == []


async def test_successful_token_clears_failure_counter(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], fake_redis: FakeRedis
) -> None:
    await _seed_client(session_factory)
    for _ in range(AUTH_FAIL_THRESHOLD - 1):
        await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": "wrong-secret"}
        )
    assert await fake_redis.get(rate_limit.auth_fail_key(CLIENT_A)) is not None

    assert (
        await client.post(
            _TOKEN_URL, json={"client_id": CLIENT_A, "client_secret": SECRET_A}
        )
    ).status_code == 200
    assert await fake_redis.get(rate_limit.auth_fail_key(CLIENT_A)) is None
