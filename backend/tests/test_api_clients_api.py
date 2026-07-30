"""task-005 後台 API Client 管理 API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:非 admin 403;建立回明文 secret 且列表不再出現;列表不含 secret_hash / pid;
PATCH 限流參數與 status 生效;單一密鑰制:rotate 撤舊發新 active 恆 1(task-010);
軟刪 client 不出現在列表。

task-008 追加:密鑰清單端點(含 retired、欄位僅 uid/status/created_at、不存在 uid → 404)
與建立 / rotate 回應的 secret_uid 對得上清單列。

task-009 追加:secret 可逆加密入庫 + reveal 端點(明文與建立回應一致 / 舊列 NULL → 409 /
非 admin → 403 / audit 有 reveal 事件且 detail 無明文 / 清單含 revealable)。
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
# 本檔自帶 Fernet 測試金鑰,不依賴 backend/.env(reveal 的加解密須同一把)
CLIENT_SECRET_ENCRYPTION_KEY = "gV9B0ldDujaVk-KpKzDOSm6TSAFPgGIfNxu1NxLr8oY="
os.environ["CLIENT_SECRET_ENCRYPTION_KEY"] = CLIENT_SECRET_ENCRYPTION_KEY

from collections.abc import AsyncIterator  # noqa: E402

import pytest_asyncio  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.security import hash_password_async, verify_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import AuditLog  # noqa: E402
from app.models.api_client_secret import (  # noqa: E402
    SECRET_STATUS_ACTIVE,
    ApiClientSecret,
)
from app.models.api_client_user import ApiClientUser  # noqa: E402
from app.models.user import User  # noqa: E402
from app.repositories.api_client_repo import ApiClientRepository  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services.api_client_service import CLIENT_ID_PREFIX  # noqa: E402

_CLIENTS_URL = "/api/v1/api-clients"
_FAKE_UID = "00000000-0000-0000-0000-0000000000ff"


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
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM users"))


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
    # base_url 用 https:cookie 為 secure=True,走 http 不會被 client 回送
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
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


@pytest_asyncio.fixture
async def admin_client(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncClient:
    await _create_user(session_factory, "adam", "adam-password-123", "admin")
    await _login(client, "adam", "adam-password-123")
    return client


async def _create_api_client(
    client: AsyncClient,
    name: str = "ERP 報表系統",
    description: str | None = "對外供應",
) -> tuple[dict[str, object], str]:
    """建立一個 API Client,回 (client 物件, 明文 secret)。"""
    resp = await client.post(
        _CLIENTS_URL, json={"name": name, "description": description}
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    return data["client"], data["client_secret"]


# ── 權限 ─────────────────────────────────────────────────────────────────
async def test_requires_login(client: AsyncClient) -> None:
    assert (await client.get(_CLIENTS_URL)).status_code == 401


async def test_member_forbidden_on_all_endpoints(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _create_user(session_factory, "vera", "vera-password-123", "member")
    await _login(client, "vera", "vera-password-123")
    assert (await client.get(_CLIENTS_URL)).status_code == 403
    assert (await client.post(_CLIENTS_URL, json={"name": "x"})).status_code == 403
    assert (
        await client.patch(f"{_CLIENTS_URL}/{_FAKE_UID}", json={"name": "x"})
    ).status_code == 403
    assert (
        await client.post(f"{_CLIENTS_URL}/{_FAKE_UID}/rotate-secret")
    ).status_code == 403
    assert (
        await client.post(f"{_CLIENTS_URL}/{_FAKE_UID}/secrets/{_FAKE_UID}/retire")
    ).status_code == 403
    assert (await client.get(f"{_CLIENTS_URL}/{_FAKE_UID}/secrets")).status_code == 403
    assert (
        await client.get(f"{_CLIENTS_URL}/{_FAKE_UID}/secrets/{_FAKE_UID}/reveal")
    ).status_code == 403


# ── 建立 ─────────────────────────────────────────────────────────────────
async def test_create_returns_plaintext_secret_once(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created, plain_secret = await _create_api_client(admin_client)
    assert len(plain_secret) >= 32
    client_id = created["client_id"]
    assert isinstance(client_id, str)
    assert client_id.startswith(CLIENT_ID_PREFIX)
    assert len(client_id) == len(CLIENT_ID_PREFIX) + 24
    assert created["status"] == "enabled"
    assert created["rate_limit_per_minute"] == 30
    assert created["rate_limit_per_10min"] == 200
    assert created["active_secret_count"] == 1

    # 明文不再出現於後續讀取
    resp = await admin_client.get(_CLIENTS_URL)
    assert resp.status_code == 200
    assert plain_secret not in resp.text
    assert "client_secret" not in resp.text

    # 入庫只有 bcrypt 雜湊,且可驗證回原明文
    async with session_factory() as session:
        secret = (await session.execute(select(ApiClientSecret))).scalar_one()
        assert secret.secret_hash != plain_secret
        assert secret.secret_hash.startswith("$2b$")
        assert await verify_password_async(plain_secret, secret.secret_hash)


async def test_create_writes_audit_without_plaintext(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, plain_secret = await _create_api_client(admin_client)
    async with session_factory() as session:
        log = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "api_client_create")
            )
        ).scalar_one()
        assert log.target_type == "api_client"
        assert log.actor_username == "adam"
        assert log.detail is not None
        assert plain_secret not in log.detail


async def test_create_rejects_blank_name(admin_client: AsyncClient) -> None:
    resp = await admin_client.post(_CLIENTS_URL, json={"name": ""})
    assert resp.status_code == 422


# ── 列表 ─────────────────────────────────────────────────────────────────
async def test_list_excludes_internal_fields(admin_client: AsyncClient) -> None:
    await _create_api_client(admin_client)
    resp = await admin_client.get(_CLIENTS_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert {
        "uid",
        "client_id",
        "name",
        "description",
        "status",
        "rate_limit_per_minute",
        "rate_limit_per_10min",
        "active_secret_count",
        "created_at",
    } == set(item.keys())
    assert "secret_hash" not in resp.text
    assert "pid" not in item
    assert "is_deleted" not in item


async def test_list_excludes_soft_deleted(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    kept, _ = await _create_api_client(admin_client, name="留下的系統")
    gone, _ = await _create_api_client(admin_client, name="要軟刪的系統")
    gone_uid = gone["uid"]

    async with session_factory() as session:
        target = (
            await session.execute(
                select(ApiClientUser).where(ApiClientUser.uid == gone_uid)
            )
        ).scalar_one()
        await ApiClientRepository(session).soft_delete(
            target, actor_uid=target.created_by
        )
        await session.commit()

    body = (await admin_client.get(_CLIENTS_URL)).json()
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["uid"] == kept["uid"]

    # 軟刪後對該 uid 的操作一律 404
    assert (
        await admin_client.patch(f"{_CLIENTS_URL}/{gone_uid}", json={"name": "n"})
    ).status_code == 404
    assert (
        await admin_client.post(f"{_CLIENTS_URL}/{gone_uid}/rotate-secret")
    ).status_code == 404
    assert (
        await admin_client.get(f"{_CLIENTS_URL}/{gone_uid}/secrets")
    ).status_code == 404


# ── PATCH ────────────────────────────────────────────────────────────────
async def test_patch_updates_status_and_rate_limits(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created, _ = await _create_api_client(admin_client)
    uid = created["uid"]
    resp = await admin_client.patch(
        f"{_CLIENTS_URL}/{uid}",
        json={
            "name": "改名後的系統",
            "status": "disabled",
            "rate_limit_per_minute": 5,
            "rate_limit_per_10min": 50,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "改名後的系統"
    assert data["status"] == "disabled"
    assert data["rate_limit_per_minute"] == 5
    assert data["rate_limit_per_10min"] == 50
    assert data["client_id"] == created["client_id"]
    assert data["active_secret_count"] == 1

    # 再讀一次確認落庫
    listed = (await admin_client.get(_CLIENTS_URL)).json()["data"]["items"][0]
    assert listed["status"] == "disabled"
    assert listed["rate_limit_per_minute"] == 5

    async with session_factory() as session:
        row = (
            await session.execute(select(ApiClientUser).where(ApiClientUser.uid == uid))
        ).scalar_one()
        assert row.status == "disabled"
        assert row.rate_limit_per_10min == 50


async def test_patch_rejects_invalid_values(admin_client: AsyncClient) -> None:
    created, _ = await _create_api_client(admin_client)
    uid = created["uid"]
    assert (
        await admin_client.patch(
            f"{_CLIENTS_URL}/{uid}", json={"rate_limit_per_minute": 0}
        )
    ).status_code == 422
    assert (
        await admin_client.patch(f"{_CLIENTS_URL}/{uid}", json={"status": "paused"})
    ).status_code == 422

    # client_id 為未知欄位,忽略而不改動既有值
    resp = await admin_client.patch(
        f"{_CLIENTS_URL}/{uid}", json={"client_id": "dc_hack"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["client_id"] == created["client_id"]


async def test_patch_unknown_uid_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.patch(f"{_CLIENTS_URL}/{_FAKE_UID}", json={"name": "x"})
    assert resp.status_code == 404
    assert resp.json()["success"] is False


# ── 輪替 / 汰換(單一密鑰制)────────────────────────────────────────────────
async def test_rotate_retires_old_and_keeps_single_active(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created, first_secret = await _create_api_client(admin_client)
    uid = created["uid"]

    resp = await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")
    assert resp.status_code == 200, resp.text
    rotated = resp.json()["data"]
    assert rotated["active_secret_count"] == 1
    assert isinstance(rotated["client_secret"], str)
    assert rotated["client_secret"] != first_secret

    # 再輪替一次仍成功:active 恆 1,retired 逐次累積
    resp = await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active_secret_count"] == 1
    async with session_factory() as session:
        rows = (await session.execute(select(ApiClientSecret))).scalars().all()
        assert len(rows) == 3
        assert sorted(row.status for row in rows) == ["active", "retired", "retired"]


async def test_retire_then_rotate_restores_single_active(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created, _ = await _create_api_client(admin_client)
    uid = created["uid"]
    rotated = (await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")).json()[
        "data"
    ]
    secret_uid = rotated["secret_uid"]

    # 手動撤銷唯一 active → 歸零(該使用者無法取證)
    resp = await admin_client.post(f"{_CLIENTS_URL}/{uid}/secrets/{secret_uid}/retire")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active_secret_count"] == 0

    # retired 列仍在(軟性,不刪列)
    async with session_factory() as session:
        rows = (await session.execute(select(ApiClientSecret))).scalars().all()
        assert len(rows) == 2
        assert sorted(row.status for row in rows) == ["retired", "retired"]

    # 再輪替即恢復 1 把 active
    resp = await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active_secret_count"] == 1


async def test_retire_last_active_secret_allowed(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created, _ = await _create_api_client(admin_client)
    uid = created["uid"]
    async with session_factory() as session:
        secret = (
            await session.execute(
                select(ApiClientSecret).where(
                    ApiClientSecret.status == SECRET_STATUS_ACTIVE
                )
            )
        ).scalar_one()

    resp = await admin_client.post(f"{_CLIENTS_URL}/{uid}/secrets/{secret.uid}/retire")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["active_secret_count"] == 0


async def test_retire_secret_of_other_client_404(admin_client: AsyncClient) -> None:
    first, _ = await _create_api_client(admin_client, name="甲系統")
    second, _ = await _create_api_client(admin_client, name="乙系統")
    other_secret_uid = (
        await admin_client.post(f"{_CLIENTS_URL}/{second['uid']}/rotate-secret")
    ).json()["data"]["secret_uid"]

    resp = await admin_client.post(
        f"{_CLIENTS_URL}/{first['uid']}/secrets/{other_secret_uid}/retire"
    )
    assert resp.status_code == 404


# ── 密鑰清單(task-008)────────────────────────────────────────────────────
async def _create_api_client_full(
    client: AsyncClient, name: str = "密鑰清單系統"
) -> dict[str, object]:
    resp = await client.post(_CLIENTS_URL, json={"name": name})
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert isinstance(data, dict)
    return data


async def test_create_response_secret_uid_matches_db_row(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _create_api_client_full(admin_client)
    async with session_factory() as session:
        secret = (await session.execute(select(ApiClientSecret))).scalar_one()
    assert created["secret_uid"] == str(secret.uid)


async def test_secret_list_returns_active_and_retired_minimal_fields(
    admin_client: AsyncClient,
) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    uid = client_obj["uid"]
    initial_secret_uid = created["secret_uid"]
    initial_plain_secret = created["client_secret"]

    rotated = (await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")).json()[
        "data"
    ]
    rotated_secret_uid = rotated["secret_uid"]

    resp = await admin_client.get(f"{_CLIENTS_URL}/{uid}/secrets")
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["total"] == 2
    # 依核發時間升冪:初始密鑰先、輪替密鑰後
    assert [item["uid"] for item in body["items"]] == [
        initial_secret_uid,
        rotated_secret_uid,
    ]
    # 單一密鑰制:輪替後初始密鑰自動轉 retired,新密鑰為唯一 active
    assert {item["uid"]: item["status"] for item in body["items"]} == {
        initial_secret_uid: "retired",
        rotated_secret_uid: "active",
    }
    for item in body["items"]:
        assert set(item.keys()) == {"uid", "status", "created_at", "revealable"}
        assert isinstance(item["created_at"], str)
        assert item["revealable"] is True
    assert "secret_hash" not in resp.text
    assert "pid" not in resp.text
    assert "client_secret" not in resp.text
    assert initial_plain_secret not in resp.text
    assert rotated["client_secret"] not in resp.text

    # 手動汰換唯一 active:該列仍在,狀態轉 retired
    assert (
        await admin_client.post(
            f"{_CLIENTS_URL}/{uid}/secrets/{rotated_secret_uid}/retire"
        )
    ).status_code == 200
    body = (await admin_client.get(f"{_CLIENTS_URL}/{uid}/secrets")).json()["data"]
    assert body["total"] == 2
    assert {item["uid"]: item["status"] for item in body["items"]} == {
        initial_secret_uid: "retired",
        rotated_secret_uid: "retired",
    }


async def test_secret_list_scoped_to_one_client(admin_client: AsyncClient) -> None:
    first = await _create_api_client_full(admin_client, name="甲系統")
    second = await _create_api_client_full(admin_client, name="乙系統")
    first_client = first["client"]
    second_client = second["client"]
    assert isinstance(first_client, dict)
    assert isinstance(second_client, dict)

    body = (
        await admin_client.get(f"{_CLIENTS_URL}/{first_client['uid']}/secrets")
    ).json()["data"]
    assert [item["uid"] for item in body["items"]] == [first["secret_uid"]]
    assert second["secret_uid"] not in [item["uid"] for item in body["items"]]


async def test_secret_list_unknown_uid_404(admin_client: AsyncClient) -> None:
    resp = await admin_client.get(f"{_CLIENTS_URL}/{_FAKE_UID}/secrets")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False
    assert body["response_code"] == 404


# ── 明文檢視 reveal(task-009)──────────────────────────────────────────────
def _reveal_url(client_uid: object, secret_uid: object) -> str:
    return f"{_CLIENTS_URL}/{client_uid}/secrets/{secret_uid}/reveal"


async def _clear_encrypted_secret(
    session_factory: async_sessionmaker[AsyncSession], secret_uid: object
) -> None:
    """模擬 task-009 前核發的舊列(僅有 bcrypt 雜湊,無可逆加密明文)。"""
    async with session_factory() as session:
        await session.execute(
            text(
                "UPDATE api_client_secrets SET secret_encrypted = NULL "
                "WHERE uid = CAST(:uid AS uuid)"
            ),
            {"uid": str(secret_uid)},
        )
        await session.commit()


async def test_reveal_returns_same_plaintext_as_create(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    plain_secret = created["client_secret"]

    resp = await admin_client.get(_reveal_url(client_obj["uid"], created["secret_uid"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["response_code"] == 200
    assert body["data"]["secret_uid"] == created["secret_uid"]
    assert body["data"]["client_secret"] == plain_secret

    # 入庫是加密值(非明文),且 bcrypt 雜湊仍可驗證回同一把明文
    async with session_factory() as session:
        secret = (await session.execute(select(ApiClientSecret))).scalar_one()
        assert secret.secret_encrypted is not None
        assert secret.secret_encrypted != plain_secret
        assert isinstance(plain_secret, str)
        assert await verify_password_async(plain_secret, secret.secret_hash)


async def test_reveal_after_rotate_returns_each_secret(admin_client: AsyncClient) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    uid = client_obj["uid"]
    rotated = (await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")).json()[
        "data"
    ]

    first = (await admin_client.get(_reveal_url(uid, created["secret_uid"]))).json()["data"]
    second = (await admin_client.get(_reveal_url(uid, rotated["secret_uid"]))).json()["data"]
    assert first["client_secret"] == created["client_secret"]
    assert second["client_secret"] == rotated["client_secret"]
    assert first["client_secret"] != second["client_secret"]


async def test_reveal_legacy_row_without_encrypted_conflicts(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    await _clear_encrypted_secret(session_factory, created["secret_uid"])

    resp = await admin_client.get(_reveal_url(client_obj["uid"], created["secret_uid"]))
    assert resp.status_code == 409
    body = resp.json()
    assert body["success"] is False
    assert body["response_code"] == 409
    assert body["detail"] is not None


async def test_secret_list_marks_legacy_row_not_revealable(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    uid = client_obj["uid"]
    rotated = (await admin_client.post(f"{_CLIENTS_URL}/{uid}/rotate-secret")).json()[
        "data"
    ]
    await _clear_encrypted_secret(session_factory, created["secret_uid"])

    body = (await admin_client.get(f"{_CLIENTS_URL}/{uid}/secrets")).json()["data"]
    assert {item["uid"]: item["revealable"] for item in body["items"]} == {
        created["secret_uid"]: False,
        rotated["secret_uid"]: True,
    }


async def test_reveal_writes_audit_without_plaintext(
    admin_client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    plain_secret = created["client_secret"]
    assert isinstance(plain_secret, str)

    assert (
        await admin_client.get(_reveal_url(client_obj["uid"], created["secret_uid"]))
    ).status_code == 200

    async with session_factory() as session:
        log = (
            await session.execute(
                select(AuditLog).where(AuditLog.action == "api_client_secret_reveal")
            )
        ).scalar_one()
        assert log.target_type == "api_client"
        assert log.actor_username == "adam"
        assert log.detail is not None
        assert plain_secret not in log.detail
        assert str(created["secret_uid"]) in log.detail


async def test_reveal_unknown_and_cross_client_404(admin_client: AsyncClient) -> None:
    first = await _create_api_client_full(admin_client, name="甲系統")
    second = await _create_api_client_full(admin_client, name="乙系統")
    first_client = first["client"]
    assert isinstance(first_client, dict)

    # client 不存在
    assert (
        await admin_client.get(_reveal_url(_FAKE_UID, first["secret_uid"]))
    ).status_code == 404
    # secret 不存在
    assert (
        await admin_client.get(_reveal_url(first_client["uid"], _FAKE_UID))
    ).status_code == 404
    # 別的 client 的 secret
    assert (
        await admin_client.get(_reveal_url(first_client["uid"], second["secret_uid"]))
    ).status_code == 404


async def test_reveal_of_retired_secret_still_allowed(admin_client: AsyncClient) -> None:
    """已汰換密鑰仍可檢視明文(供比對確認哪把已失效);狀態不影響解密。"""
    created = await _create_api_client_full(admin_client)
    client_obj = created["client"]
    assert isinstance(client_obj, dict)
    uid = client_obj["uid"]
    assert (
        await admin_client.post(
            f"{_CLIENTS_URL}/{uid}/secrets/{created['secret_uid']}/retire"
        )
    ).status_code == 200

    resp = await admin_client.get(_reveal_url(uid, created["secret_uid"]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["client_secret"] == created["client_secret"]
