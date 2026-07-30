"""task-002 對外 API Client 命名空間核心測試:JWT 簽發 / 本地驗簽、統一封套、/api/client 掛載。"""

import json
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

os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")
os.environ["CLIENT_JWT_SECRET"] = CLIENT_JWT_SECRET

from collections.abc import AsyncIterator  # noqa: E402
from datetime import UTC, datetime  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.api_client_router.common.auth import (  # noqa: E402
    CLIENT_JWT_ALGORITHM,
    CLIENT_JWT_EXPIRE_SECONDS,
    CLIENT_JWT_ISSUER,
    sign_client_jwt,
    verify_client_jwt,
)
from app.api_client_router.common.envelope import client_error, client_success  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402

_ENVELOPE_KEYS = {"success", "response_code", "detail", "data"}


def _body(response: object) -> dict[str, object]:
    raw: bytes = response.body  # type: ignore[attr-defined]
    parsed: dict[str, object] = json.loads(raw)
    return parsed


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


# ── JWT 簽發 / 本地驗簽 ──────────────────────────────────────────────────
def test_sign_then_verify_roundtrip() -> None:
    token, expires_in = sign_client_jwt("client-abc")
    assert expires_in == 900
    payload = verify_client_jwt(token)
    assert payload["sub"] == "client-abc"
    assert payload["iss"] == CLIENT_JWT_ISSUER
    assert isinstance(payload["iat"], int)
    assert isinstance(payload["exp"], int)
    assert payload["exp"] - payload["iat"] == 900


def test_signed_token_uses_hs256() -> None:
    token, _ = sign_client_jwt("client-abc")
    assert jwt.get_unverified_header(token)["alg"] == "HS256"


def test_expired_token_rejected_when_verify_exp_true() -> None:
    token = _expired_token("client-abc")
    with pytest.raises(jwt.ExpiredSignatureError):
        verify_client_jwt(token)


def test_expired_token_accepted_when_verify_exp_false() -> None:
    token = _expired_token("client-abc")
    payload = verify_client_jwt(token, verify_exp=False)
    assert payload["sub"] == "client-abc"


def test_tampered_token_fails_verification() -> None:
    token, _ = sign_client_jwt("client-abc")
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{signature[:-3]}xyz"
    with pytest.raises(jwt.PyJWTError):
        verify_client_jwt(tampered)


def test_token_signed_with_other_secret_fails_verification() -> None:
    token = _expired_token("client-abc", secret="another-secret-at-least-32-characters")
    with pytest.raises(jwt.PyJWTError):
        verify_client_jwt(token, verify_exp=False)


def test_garbage_token_fails_verification() -> None:
    with pytest.raises(jwt.PyJWTError):
        verify_client_jwt("not-a-jwt-at-all")


# ── 統一封套 ────────────────────────────────────────────────────────────
def test_envelope_success_structure() -> None:
    response = client_success([{"access_token": "x", "token_type": "Bearer", "expires_in": 900}])
    assert response.status_code == 200
    body = _body(response)
    assert set(body) == _ENVELOPE_KEYS
    assert body["success"] is True
    assert body["response_code"] == 200
    assert isinstance(body["detail"], str)
    assert isinstance(body["data"], list)
    assert body["data"][0]["expires_in"] == 900  # type: ignore[index]


def test_envelope_success_data_defaults_to_empty_list() -> None:
    body = _body(client_success())
    assert body["data"] == []
    assert isinstance(body["data"], list)


def test_envelope_error_structure_and_status_matches_response_code() -> None:
    response = client_error("invalid_client", response_code=401)
    assert response.status_code == 401
    body = _body(response)
    assert set(body) == _ENVELOPE_KEYS
    assert body["success"] is False
    assert body["response_code"] == 401
    assert body["detail"] == "invalid_client"
    assert body["data"] == []


def test_envelope_error_supports_extra_headers() -> None:
    response = client_error("rate_limited", response_code=429, headers={"Retry-After": "30"})
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "30"
    assert _body(response)["data"] == []


# ── Settings fail-fast:CLIENT_JWT_SECRET 缺值 / 過短 ────────────────────
def _settings_kwargs() -> dict[str, str]:
    return {
        "DATABASE_URL": TEST_DATABASE_URL,
        "INIT_ADMIN_USERNAME": "ok-admin",
        "INIT_ADMIN_PASSWORD": "ok-password-123",
    }


def test_settings_missing_client_jwt_secret_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIENT_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        # 隔離本機 .env,只看 env 變數(缺 CLIENT_JWT_SECRET 必須驗證失敗)
        Settings(_env_file=None, **_settings_kwargs())  # type: ignore[call-arg]
    assert "CLIENT_JWT_SECRET" in str(exc_info.value)


def test_settings_short_client_jwt_secret_fail_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIENT_JWT_SECRET", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(  # type: ignore[call-arg]
            _env_file=None, CLIENT_JWT_SECRET="a" * 31, **_settings_kwargs()
        )
    assert "CLIENT_JWT_SECRET" in str(exc_info.value)


def test_settings_invalid_fernet_encryption_key_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AD-137:長度過驗但非合法 Fernet 金鑰(44 字元非法字串)須啟動即 fail-fast。"""
    monkeypatch.delenv("CLIENT_SECRET_ENCRYPTION_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(  # type: ignore[call-arg]
            _env_file=None,
            CLIENT_SECRET_ENCRYPTION_KEY="x" * 44,
            **_settings_kwargs(),
        )
    errors = exc_info.value.errors()
    assert any(
        "CLIENT_SECRET_ENCRYPTION_KEY 非合法 Fernet 金鑰" in error["msg"] for error in errors
    )
    # 我們 raise 的錯誤訊息禁含 key 內容(pydantic 另行回顯的 input_value 不在此列)
    assert all("x" * 44 not in error["msg"] for error in errors)


def test_settings_valid_client_jwt_secret_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLIENT_JWT_SECRET", raising=False)
    settings = Settings(  # type: ignore[call-arg]
        _env_file=None, CLIENT_JWT_SECRET="b" * 32, **_settings_kwargs()
    )
    assert settings.CLIENT_JWT_SECRET == "b" * 32


# ── /api/client/v1.0 命名空間存在 + 後台 /api/v1 行為不變 ────────────────
@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # 不進 lifespan(不建 init admin / 不需 DB);僅驗路由掛載與回應外殼
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


@pytest.mark.parametrize("path", ["/api/client/v1.0/token", "/api/client/v1.0/refresh_token"])
async def test_client_namespace_is_reachable(client: AsyncClient, path: str) -> None:
    resp = await client.post(path, json={})
    assert resp.status_code != 404
    body = resp.json()
    assert set(body) == _ENVELOPE_KEYS
    assert body["response_code"] == resp.status_code
    assert body["data"] == []


async def test_unknown_client_version_is_404(client: AsyncClient) -> None:
    assert (await client.post("/api/client/v9.9/token")).status_code == 404


async def test_backoffice_health_unchanged(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health")
    # 既有行為:後台 ApiResponse 外殼(DB 不可達時為 503,見 app/api/v1/health.py)
    assert resp.status_code in (200, 503)
    body = resp.json()
    assert set(body) == {"success", "data", "detail", "response_code"}
    assert body["response_code"] == resp.status_code
