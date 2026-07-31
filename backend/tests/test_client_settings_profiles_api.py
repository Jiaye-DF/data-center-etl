"""權限設定檔 / Role 管理 API 測試(v1.6.1 task-005)。

fixture 區塊與 test_client_settings_services_api.py 同構:真實本地 PostgreSQL 測試 DB
同時假扮「自有 DB」與「目標 RDS」;清理一律 DELETE 資料,**不做任何 DROP**。

涵蓋:非 admin 403、設定檔 CRUD、勾作業整批置換(含取消勾選連動清授權項)、授權矩陣整批
置換(未勾作業 409 / 超出作業範圍 422 / 非 confirmed 422 / 重複 422 / 非法 action 422)、
Role CRUD 必綁設定檔防呆、刪除防呆 409、稽核事件、失效扇出(綁該設定檔的 Role → Client)。
測試資料一律帶隨機前綴,避免與並行測試/他人資料互撞。
"""

from __future__ import annotations

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
from uuid import UUID, uuid4  # noqa: E402

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
from app.etl.client_setting_schema import ensure_client_setting_schema  # noqa: E402
from app.etl.semantic_schema import ensure_semantic_schema  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.client_setting import (  # noqa: E402
    CLIENT_SETTING_SCHEMA,
    CLIENT_SETTING_TABLES,
)
from app.repositories.client_setting_repo import (  # noqa: E402
    ClientSettingRepository,
    client_setting_session,
)
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services.permission_cache import effective_key  # noqa: E402

_BASE_PATH = "/api/v1/client-settings"
_SERVICES = f"{_BASE_PATH}/services"
_OPERATIONS = f"{_BASE_PATH}/operations"
_PROFILES = f"{_BASE_PATH}/profiles"
_ROLES = f"{_BASE_PATH}/roles"

ACTOR_UID = uuid4()


# ── fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建測試 DB(不存在才建)+ 自有 DB 表 + erp_metadata 語意表 + client_setting schema。

    全為冪等 DDL;不做任何 DROP。
    """

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
                await ensure_client_setting_schema(conn)
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
async def _cleanup(db_engine: AsyncEngine) -> AsyncIterator[None]:
    """每測試後清權限 12 表與語意映射(禁 DROP);users / audit_logs 靠隨機值隔離不清。"""
    yield
    async with db_engine.begin() as conn:
        for table in reversed(CLIENT_SETTING_TABLES):
            await conn.execute(text(f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table}"))
        await conn.execute(text("DELETE FROM erp_metadata.semantic_mappings"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """權限快取於 pytest 走記憶體 fake(core.redis);每測試換新份,狀態天然隔離。"""
    cache._client = None


@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效。每測試後 dispose + 清快取。"""
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


@pytest.fixture
def tag() -> str:
    """本測試專屬前綴:避免與並行測試 / 殘留資料撞唯一鍵。"""
    return uuid4().hex[:8]


# ── helpers ─────────────────────────────────────────────────────────────
async def _login_as(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    username = f"{role}-{uuid4().hex[:10]}"
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


async def _seed_semantic(db_engine: AsyncEngine, tag: str) -> dict[str, str]:
    """種語意映射:`table1` 表層級 confirmed,含兩個 confirmed 欄與一個 draft 欄。

    `col_extra` 刻意 confirmed 卻不放進作業範圍,用來驗「∩ 作業範圍上限」是獨立的一關。
    """
    names = {
        "table1": f"tbl_one_{tag}",
        "col_ok": f"col_ok_{tag}",
        "col_extra": f"col_extra_{tag}",
        "col_draft": f"col_draft_{tag}",
        "table2": f"tbl_two_{tag}",
    }
    rows = [
        (f"RAW1_{tag}", "", names["table1"], "表一", "confirmed"),
        (f"RAW1_{tag}", "C11", names["col_ok"], "欄一", "confirmed"),
        (f"RAW1_{tag}", "C12", names["col_extra"], "欄二", "confirmed"),
        (f"RAW1_{tag}", "C13", names["col_draft"], "欄三", "draft"),
        (f"RAW2_{tag}", "", names["table2"], "表二", "draft"),
    ]
    async with db_engine.begin() as conn:
        for table_name, column_name, english_name, zh_name, status in rows:
            await conn.execute(
                text(
                    "INSERT INTO erp_metadata.semantic_mappings"
                    " (table_name, column_name, english_name, zh_name, status)"
                    " VALUES (:t, :c, :e, :z, :s)"
                ),
                {
                    "t": table_name,
                    "c": column_name,
                    "e": english_name,
                    "z": zh_name,
                    "s": status,
                },
            )
    return names


async def _create_service(client: AsyncClient, tag: str) -> dict[str, str]:
    resp = await client.post(
        _SERVICES, json={"code": f"svc-{tag}", "name": f"系統別 {tag}"}
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _create_operation(
    client: AsyncClient, service_uid: str, name: str
) -> dict[str, str]:
    resp = await client.post(_OPERATIONS, json={"service_uid": service_uid, "name": name})
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _set_operation_scope(
    client: AsyncClient, operation_uid: str, items: list[dict[str, str]]
) -> None:
    resp = await client.put(f"{_OPERATIONS}/{operation_uid}/items", json={"items": items})
    assert resp.status_code == 200, resp.text


async def _create_profile(client: AsyncClient, name: str) -> dict[str, str]:
    resp = await client.post(_PROFILES, json={"name": name, "description": "測試"})
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _create_role(
    client: AsyncClient, profile_uid: str, name: str
) -> dict[str, str]:
    resp = await client.post(
        _ROLES, json={"permission_profile_uid": profile_uid, "name": name}
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _grant_operations(
    client: AsyncClient, profile_uid: str, operation_uids: list[str]
) -> None:
    resp = await client.put(
        f"{_PROFILES}/{profile_uid}/operations", json={"operation_uids": operation_uids}
    )
    assert resp.status_code == 200, resp.text


def _items_path(profile_uid: str, operation_uid: str) -> str:
    return f"{_PROFILES}/{profile_uid}/operations/{operation_uid}/items"


async def _audit_details(db_engine: AsyncEngine, action: str, target_uid: str) -> list[str]:
    async with db_engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        "SELECT detail FROM audit_logs"
                        " WHERE action = :a AND target_uid = :u ORDER BY pid"
                    ),
                    {"a": action, "u": target_uid},
                )
            )
            .scalars()
            .all()
        )
    return [str(row) for row in rows]


async def _profile_names(client: AsyncClient) -> set[str]:
    resp = await client.get(_PROFILES)
    assert resp.status_code == 200, resp.text
    return {str(item["name"]) for item in resp.json()["data"]["items"]}


async def _role_names(client: AsyncClient) -> set[str]:
    resp = await client.get(_ROLES)
    assert resp.status_code == 200, resp.text
    return {str(item["name"]) for item in resp.json()["data"]["items"]}


async def _granted_operation_uids(client: AsyncClient, profile_uid: str) -> set[str]:
    resp = await client.get(f"{_PROFILES}/{profile_uid}/operations")
    assert resp.status_code == 200, resp.text
    return {str(item["operation_uid"]) for item in resp.json()["data"]["items"]}


async def _granted_items(
    client: AsyncClient, profile_uid: str, operation_uid: str
) -> set[tuple[str, str, str]]:
    resp = await client.get(_items_path(profile_uid, operation_uid))
    assert resp.status_code == 200, resp.text
    return {
        (str(i["table_name"]), str(i["column_name"]), str(i["action"]))
        for i in resp.json()["data"]["items"]
    }


async def _matrix_fixture(
    client: AsyncClient, db_engine: AsyncEngine, tag: str
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """一組可用的矩陣場景:作業範圍只開 `table1.col_ok`,設定檔已勾選該作業。"""
    names = await _seed_semantic(db_engine, tag)
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")
    await _set_operation_scope(
        client,
        operation["uid"],
        [{"table_name": names["table1"], "column_name": names["col_ok"]}],
    )
    profile = await _create_profile(client, f"P-{tag}")
    await _grant_operations(client, profile["uid"], [operation["uid"]])
    return names, operation, profile


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_member_forbidden_on_profile_and_role_endpoints(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "member")
    some_uid = str(uuid4())
    other_uid = str(uuid4())
    for method, path, kwargs in [
        ("GET", _PROFILES, {}),
        ("POST", _PROFILES, {"json": {"name": "P"}}),
        ("PATCH", f"{_PROFILES}/{some_uid}", {"json": {"name": "X"}}),
        ("DELETE", f"{_PROFILES}/{some_uid}", {}),
        ("GET", f"{_PROFILES}/{some_uid}/operations", {}),
        ("PUT", f"{_PROFILES}/{some_uid}/operations", {"json": {"operation_uids": []}}),
        ("GET", _items_path(some_uid, other_uid), {}),
        ("PUT", _items_path(some_uid, other_uid), {"json": {"items": []}}),
        ("GET", _ROLES, {}),
        ("POST", _ROLES, {"json": {"permission_profile_uid": some_uid, "name": "R"}}),
        ("PATCH", f"{_ROLES}/{some_uid}", {"json": {"name": "X"}}),
        ("DELETE", f"{_ROLES}/{some_uid}", {}),
    ]:
        resp = await client.request(method, path, **kwargs)
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"


# ── 設定檔 CRUD ─────────────────────────────────────────────────────────
async def test_profile_crud_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    created = await _create_profile(client, f"P-{tag}")
    uid = created["uid"]
    assert UUID(uid)
    assert f"P-{tag}" in await _profile_names(client)

    patched = await client.patch(f"{_PROFILES}/{uid}", json={"name": f"P-{tag}-改"})
    assert patched.status_code == 200, patched.text
    # 寫入後清單即讀到新值(快取已失效)
    names = await _profile_names(client)
    assert f"P-{tag}-改" in names and f"P-{tag}" not in names

    deleted = await client.delete(f"{_PROFILES}/{uid}")
    assert deleted.status_code == 200, deleted.text
    assert f"P-{tag}-改" not in await _profile_names(client)

    for action in (
        "client_setting.profile_create",
        "client_setting.profile_update",
        "client_setting.profile_delete",
    ):
        assert len(await _audit_details(db_engine, action, uid)) == 1, action


async def test_profile_name_must_be_unique(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_profile(client, f"P-{tag}")
    resp = await client.post(_PROFILES, json={"name": f"P-{tag}"})
    assert resp.status_code == 409, resp.text


async def test_profile_not_found_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    missing = str(uuid4())
    assert (await client.patch(f"{_PROFILES}/{missing}", json={"name": "X"})).status_code == 404
    assert (await client.delete(f"{_PROFILES}/{missing}")).status_code == 404
    assert (await client.get(f"{_PROFILES}/{missing}/operations")).status_code == 404
    resp = await client.put(
        f"{_PROFILES}/{missing}/operations", json={"operation_uids": []}
    )
    assert resp.status_code == 404, resp.text


async def test_profile_delete_blocked_while_role_bound(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    profile = await _create_profile(client, f"P-{tag}")
    role = await _create_role(client, profile["uid"], f"R-{tag}")

    blocked = await client.delete(f"{_PROFILES}/{profile['uid']}")
    assert blocked.status_code == 409, blocked.text
    assert f"P-{tag}" in await _profile_names(client)

    assert (await client.delete(f"{_ROLES}/{role['uid']}")).status_code == 200
    assert (await client.delete(f"{_PROFILES}/{profile['uid']}")).status_code == 200


# ── 勾選作業整批置換 ────────────────────────────────────────────────────
async def test_replace_profile_operations_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    service_uid = (await client.get(_OPERATIONS)).json()["data"]["items"][0]["service_uid"]
    operation_b = await _create_operation(client, service_uid, f"O2-{tag}")

    assert await _granted_operation_uids(client, profile["uid"]) == {operation["uid"]}

    # 先給 O1 授權,再把勾選換成 O2 → O1 的授權項同交易被清掉
    granted = await client.put(
        _items_path(profile["uid"], operation["uid"]),
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "read",
                }
            ]
        },
    )
    assert granted.status_code == 200, granted.text
    assert len(await _granted_items(client, profile["uid"], operation["uid"])) == 1

    await _grant_operations(client, profile["uid"], [operation_b["uid"]])
    assert await _granted_operation_uids(client, profile["uid"]) == {operation_b["uid"]}
    assert await _granted_items(client, profile["uid"], operation["uid"]) == set()

    # 空陣列 = 全部取消勾選
    await _grant_operations(client, profile["uid"], [])
    assert await _granted_operation_uids(client, profile["uid"]) == set()

    details = await _audit_details(
        db_engine, "client_setting.profile_operations_replace", profile["uid"]
    )
    assert len(details) == 3
    assert "共 0 項" in details[-1]


async def test_replace_profile_operations_rejects_duplicate_and_unknown(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    _, operation, profile = await _matrix_fixture(client, db_engine, tag)

    duplicated = await client.put(
        f"{_PROFILES}/{profile['uid']}/operations",
        json={"operation_uids": [operation["uid"], operation["uid"]]},
    )
    assert duplicated.status_code == 422, duplicated.text
    assert "重複" in duplicated.json()["detail"]

    ghost = str(uuid4())
    unknown = await client.put(
        f"{_PROFILES}/{profile['uid']}/operations",
        json={"operation_uids": [operation["uid"], ghost]},
    )
    assert unknown.status_code == 422, unknown.text
    assert ghost in unknown.json()["detail"]

    # 失敗不改動原勾選
    assert await _granted_operation_uids(client, profile["uid"]) == {operation["uid"]}


# ── 授權矩陣整批置換 ────────────────────────────────────────────────────
async def test_replace_profile_items_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    path = _items_path(profile["uid"], operation["uid"])

    assert (await client.get(path)).json()["data"] == {"items": [], "total": 0}

    replaced = await client.put(
        path,
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "read",
                },
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "edit",
                },
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["total"] == 2
    assert await _granted_items(client, profile["uid"], operation["uid"]) == {
        (names["table1"], names["col_ok"], "read"),
        (names["table1"], names["col_ok"], "edit"),
    }

    # 再次置換:舊集合整批換掉,不殘留
    again = await client.put(
        path,
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "edit",
                }
            ]
        },
    )
    assert again.status_code == 200, again.text
    assert await _granted_items(client, profile["uid"], operation["uid"]) == {
        (names["table1"], names["col_ok"], "edit")
    }

    # 空陣列 = 該作業下無任何欄位授權(default-closed)
    assert (await client.put(path, json={"items": []})).status_code == 200
    assert (await client.get(path)).json()["data"]["total"] == 0

    details = await _audit_details(
        db_engine, "client_setting.profile_items_replace", profile["uid"]
    )
    assert len(details) == 3
    assert "共 2 項" in details[0]


async def test_replace_profile_items_requires_granted_operation(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """作業未先勾選 → 409(開門與授權缺一不可,授權不得憑空建立入口)。"""
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    service_uid = (await client.get(_OPERATIONS)).json()["data"]["items"][0]["service_uid"]
    ungranted = await _create_operation(client, service_uid, f"O2-{tag}")
    await _set_operation_scope(
        client,
        ungranted["uid"],
        [{"table_name": names["table1"], "column_name": "*"}],
    )

    resp = await client.put(
        _items_path(profile["uid"], ungranted["uid"]),
        json={
            "items": [
                {"table_name": names["table1"], "column_name": "*", "action": "read"}
            ]
        },
    )
    assert resp.status_code == 409, resp.text

    # 勾選之後同一請求即可通過
    await _grant_operations(client, profile["uid"], [operation["uid"], ungranted["uid"]])
    ok = await client.put(
        _items_path(profile["uid"], ungranted["uid"]),
        json={
            "items": [
                {"table_name": names["table1"], "column_name": "*", "action": "read"}
            ]
        },
    )
    assert ok.status_code == 200, ok.text


async def test_replace_profile_items_enforces_scope_and_semantic(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """超出作業範圍上限 / 非 confirmed / 重複 / 非法 action 一律 422,且原授權不動。"""
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    path = _items_path(profile["uid"], operation["uid"])

    baseline = {
        "table_name": names["table1"],
        "column_name": names["col_ok"],
        "action": "read",
    }
    assert (await client.put(path, json={"items": [baseline]})).status_code == 200

    # confirmed 但不在作業範圍內(範圍只開 col_ok)
    out_of_scope = await client.put(
        path,
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_extra"],
                    "action": "read",
                }
            ]
        },
    )
    assert out_of_scope.status_code == 422, out_of_scope.text
    assert "超出作業範圍" in out_of_scope.json()["detail"]
    assert names["col_extra"] in out_of_scope.json()["detail"]

    # 範圍是列舉欄位時,授權寫 `*` 等於超出上限
    wildcard = await client.put(
        path,
        json={
            "items": [
                {"table_name": names["table1"], "column_name": "*", "action": "read"}
            ]
        },
    )
    assert wildcard.status_code == 422, wildcard.text
    assert "超出作業範圍" in wildcard.json()["detail"]

    # 非 confirmed 語意映射
    unconfirmed = await client.put(
        path,
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_draft"],
                    "action": "read",
                }
            ]
        },
    )
    assert unconfirmed.status_code == 422, unconfirmed.text
    assert "confirmed" in unconfirmed.json()["detail"]

    # 同一請求內重複(表 × 欄位 × 動作)
    duplicated = await client.put(path, json={"items": [baseline, dict(baseline)]})
    assert duplicated.status_code == 422, duplicated.text
    assert "重複" in duplicated.json()["detail"]

    # action 不在 read / edit(schema Literal 擋下)
    bad_action = await client.put(
        path,
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "delete",
                }
            ]
        },
    )
    assert bad_action.status_code == 422, bad_action.text

    # 全程失敗 → 原授權不變
    assert await _granted_items(client, profile["uid"], operation["uid"]) == {
        (names["table1"], names["col_ok"], "read")
    }


async def test_profile_items_wildcard_scope_allows_any_column(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """作業範圍為 `*` 時,該表任一 confirmed 欄位(含 `*`)皆可授權。"""
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    await _set_operation_scope(
        client, operation["uid"], [{"table_name": names["table1"], "column_name": "*"}]
    )

    resp = await client.put(
        _items_path(profile["uid"], operation["uid"]),
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_extra"],
                    "action": "edit",
                },
                {"table_name": names["table1"], "column_name": "*", "action": "read"},
            ]
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["total"] == 2


async def test_profile_items_unknown_uid_returns_404(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    _, operation, profile = await _matrix_fixture(client, db_engine, tag)
    ghost = str(uuid4())

    assert (await client.get(_items_path(ghost, operation["uid"]))).status_code == 404
    assert (await client.get(_items_path(profile["uid"], ghost))).status_code == 404
    resp = await client.put(_items_path(profile["uid"], ghost), json={"items": []})
    assert resp.status_code == 404, resp.text


# ── Role CRUD + 必綁防呆 ────────────────────────────────────────────────
async def test_role_crud_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    profile_a = await _create_profile(client, f"P-{tag}-a")
    profile_b = await _create_profile(client, f"P-{tag}-b")
    created = await _create_role(client, profile_a["uid"], f"R-{tag}")
    uid = created["uid"]
    assert created["permission_profile_uid"] == profile_a["uid"]
    assert f"R-{tag}" in await _role_names(client)

    # 改綁設定檔(仍必有值)
    patched = await client.patch(
        f"{_ROLES}/{uid}",
        json={"permission_profile_uid": profile_b["uid"], "name": f"R-{tag}-改"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["permission_profile_uid"] == profile_b["uid"]
    assert f"R-{tag}-改" in await _role_names(client)

    deleted = await client.delete(f"{_ROLES}/{uid}")
    assert deleted.status_code == 200, deleted.text
    assert f"R-{tag}-改" not in await _role_names(client)

    for action in (
        "client_setting.role_create",
        "client_setting.role_update",
        "client_setting.role_delete",
    ):
        assert len(await _audit_details(db_engine, action, uid)) == 1, action


async def test_role_must_bind_permission_profile(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    profile = await _create_profile(client, f"P-{tag}")

    # 建立時未帶設定檔 → 422
    assert (await client.post(_ROLES, json={"name": f"R-{tag}"})).status_code == 422
    # 顯式 null 同樣 422
    resp = await client.post(
        _ROLES, json={"permission_profile_uid": None, "name": f"R-{tag}"}
    )
    assert resp.status_code == 422, resp.text
    # 設定檔不存在 → 404
    resp = await client.post(
        _ROLES, json={"permission_profile_uid": str(uuid4()), "name": f"R-{tag}"}
    )
    assert resp.status_code == 404, resp.text

    role = await _create_role(client, profile["uid"], f"R-{tag}")
    # PATCH 顯式清空 → 422(必綁)
    cleared = await client.patch(
        f"{_ROLES}/{role['uid']}", json={"permission_profile_uid": None}
    )
    assert cleared.status_code == 422, cleared.text
    # 省略即不變更
    kept = await client.patch(f"{_ROLES}/{role['uid']}", json={"description": "只改說明"})
    assert kept.status_code == 200, kept.text
    assert kept.json()["data"]["permission_profile_uid"] == profile["uid"]
    # 改綁到不存在的設定檔 → 404
    resp = await client.patch(
        f"{_ROLES}/{role['uid']}", json={"permission_profile_uid": str(uuid4())}
    )
    assert resp.status_code == 404, resp.text


async def test_role_name_must_be_unique(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    profile = await _create_profile(client, f"P-{tag}")
    await _create_role(client, profile["uid"], f"R-{tag}")
    resp = await client.post(
        _ROLES, json={"permission_profile_uid": profile["uid"], "name": f"R-{tag}"}
    )
    assert resp.status_code == 409, resp.text


async def test_role_not_found_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    missing = str(uuid4())
    assert (await client.patch(f"{_ROLES}/{missing}", json={"name": "X"})).status_code == 404
    assert (await client.delete(f"{_ROLES}/{missing}")).status_code == 404


async def test_role_delete_blocked_while_client_assigned(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    """被 API Client 指派的 Role 不得刪(指派端點屬 task-006,此處直接以 repo 建關聯)。"""
    await _login_as(client, session_factory, "admin")
    profile = await _create_profile(client, f"P-{tag}")
    role = await _create_role(client, profile["uid"], f"R-{tag}")

    async with client_setting_session() as session:
        repo = ClientSettingRepository(session)
        target = await repo.get_role_by_uid(UUID(role["uid"]))
        assert target is not None
        await repo.assign_client_role(uuid4(), target.pid, actor_uid=ACTOR_UID)
        await session.commit()

    blocked = await client.delete(f"{_ROLES}/{role['uid']}")
    assert blocked.status_code == 409, blocked.text
    assert f"R-{tag}" in await _role_names(client)


# ── 失效扇出(設定檔 / Role 異動 → 綁定該檔的 Client)──────────────────
async def test_profile_write_invalidates_bound_client_effective_cache(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names, operation, profile = await _matrix_fixture(client, db_engine, tag)
    role = await _create_role(client, profile["uid"], f"R-{tag}")
    bound_client_uid = uuid4()
    unrelated_client_uid = uuid4()

    async with client_setting_session() as session:
        repo = ClientSettingRepository(session)
        target = await repo.get_role_by_uid(UUID(role["uid"]))
        assert target is not None
        await repo.assign_client_role(bound_client_uid, target.pid, actor_uid=ACTOR_UID)
        await session.commit()

    async def _seed_effective_cache() -> None:
        for uid in (bound_client_uid, unrelated_client_uid):
            await cache.cache_set(effective_key(uid), "{}", ttl_seconds=300)

    # 授權矩陣異動 → 綁該設定檔的 Client 被失效,其他 Client 不受影響
    await _seed_effective_cache()
    granted = await client.put(
        _items_path(profile["uid"], operation["uid"]),
        json={
            "items": [
                {
                    "table_name": names["table1"],
                    "column_name": names["col_ok"],
                    "action": "read",
                }
            ]
        },
    )
    assert granted.status_code == 200, granted.text
    assert await cache.cache_get(effective_key(bound_client_uid)) is None
    assert await cache.cache_get(effective_key(unrelated_client_uid)) is not None

    # 勾選作業異動同樣扇出
    await _seed_effective_cache()
    await _grant_operations(client, profile["uid"], [])
    assert await cache.cache_get(effective_key(bound_client_uid)) is None

    # 設定檔改名(名稱會進 effective 快取內容)同樣扇出
    await _seed_effective_cache()
    renamed = await client.patch(
        f"{_PROFILES}/{profile['uid']}", json={"name": f"P-{tag}-改"}
    )
    assert renamed.status_code == 200, renamed.text
    assert await cache.cache_get(effective_key(bound_client_uid)) is None

    # Role 改綁設定檔 → 指派該 Role 的 Client 被失效
    await _seed_effective_cache()
    other_profile = await _create_profile(client, f"P-{tag}-other")
    rebound = await client.patch(
        f"{_ROLES}/{role['uid']}", json={"permission_profile_uid": other_profile["uid"]}
    )
    assert rebound.status_code == 200, rebound.text
    assert await cache.cache_get(effective_key(bound_client_uid)) is None
    assert await cache.cache_get(effective_key(unrelated_client_uid)) is not None
