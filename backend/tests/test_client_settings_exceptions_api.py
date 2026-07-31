"""特例權限組 / API Client 指派 API 測試(v1.6.1 task-006)。

fixture 區塊與 test_client_settings_profiles_api.py 同構:真實本地 PostgreSQL 測試 DB
同時假扮「自有 DB」與「目標 RDS」;清理一律 DELETE 資料,**不做任何 DROP**。

涵蓋:非 admin 403、特例組 CRUD(名稱唯一 409 / 未過期綁定擋刪 409)、勾作業與授權矩陣
整批置換(未勾作業 409 / 超出作業範圍 422 / 非 confirmed 422 / 重複 422)、Role 指派
冪等置換 0..1 與解除、特例綁定含效期(過期標示 / 重複 409 / 解除 / 跨 Client 定位 404)、
指派不存在或已軟刪的 Client → 404、稽核事件、失效扇出(指派 / 綁定 → 該 Client;特例組
內容異動 → 綁該組的 Client)。測試資料一律帶隨機前綴,避免與並行測試/他人資料互撞。
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
from app.repositories.api_client_repo import ApiClientRepository  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services.permission_cache import effective_key  # noqa: E402

_BASE_PATH = "/api/v1/client-settings"
_SERVICES = f"{_BASE_PATH}/services"
_OPERATIONS = f"{_BASE_PATH}/operations"
_PROFILES = f"{_BASE_PATH}/profiles"
_ROLES = f"{_BASE_PATH}/roles"
_EXCEPTION_SETS = f"{_BASE_PATH}/exception-sets"
_CLIENTS = f"{_BASE_PATH}/clients"

ACTOR_UID = uuid4()

# 本測試(單一 pytest 進程內序列執行,無併發風險)以 `_login_as` 建立的 admin uid;
# 該 uid 即透過 API 建立資料的 created_by,清理時併入過濾條件,避免動到併行測試檔的資料
_test_actor_uids: list[UUID] = []

# 效期界線(naive UTC+8 wall-clock;測試不依賴當下時鐘)
_PAST = "2020-01-01T00:00:00"
_FUTURE = "2999-12-31T23:59:59"


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
async def _cleanup(db_engine: AsyncEngine, tag: str) -> AsyncIterator[None]:
    """每測試後只刪本測試建立的列(禁 DROP);與併行測試檔共用測試 DB 亦互不干擾。

    12 張權限表以 `created_by`(ACTOR_UID + 本測試 `_login_as` 建立的 admin uid)過濾;
    `semantic_mappings` 無 created_by 欄位,改以本測試專屬 `tag` 前綴比對(見 `_seed_semantic`);
    `api_client_users` 一律以 `_create_api_client` 明綁 `ACTOR_UID` 建立,沿用同一過濾條件即可。
    """
    _test_actor_uids.clear()
    yield
    actors = [str(ACTOR_UID), *(str(uid) for uid in _test_actor_uids)]
    async with db_engine.begin() as conn:
        for table in reversed(CLIENT_SETTING_TABLES):
            await conn.execute(
                text(
                    f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table}"
                    " WHERE created_by = ANY(:actors)"
                ),
                {"actors": actors},
            )
        await conn.execute(
            text("DELETE FROM erp_metadata.semantic_mappings WHERE table_name LIKE :pattern"),
            {"pattern": f"%{tag}%"},
        )
        await conn.execute(
            text("DELETE FROM api_client_users WHERE created_by = :actor"),
            {"actor": str(ACTOR_UID)},
        )
    _test_actor_uids.clear()


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
    """本測試專屬前綴:避免與並行測試 / 殘留資料撞唯一鍵(轉純小寫字母,服務代碼僅允許 a-z 與底線)。"""
    return uuid4().hex[:8].translate(str.maketrans("0123456789", "ghijklmnop"))


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
        user = await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()
    _test_actor_uids.append(user.uid)
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


async def _create_api_client(session_factory: async_sessionmaker[AsyncSession]) -> str:
    """在**自有 DB** 建一個 API Client(RDS 端只留冷關聯 uid)。"""
    async with session_factory() as session:
        row = await ApiClientRepository(session).create(
            client_id=f"dc_{uuid4().hex[:24]}",
            name=f"指派測試 Client {uuid4().hex[:6]}",
            actor_uid=ACTOR_UID,
        )
        await session.commit()
        return str(row.uid)


async def _soft_delete_api_client(db_engine: AsyncEngine, client_uid: str) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(
            text("UPDATE api_client_users SET is_deleted = true WHERE uid = :uid"),
            {"uid": client_uid},
        )


async def _seed_semantic(db_engine: AsyncEngine, tag: str) -> dict[str, str]:
    """種語意映射:`table1` 表層級 confirmed,含兩個 confirmed 欄與一個 draft 欄。

    `col_extra` 刻意 confirmed 卻不放進作業範圍,用來驗「∩ 作業範圍上限」是獨立的一關。
    """
    names = {
        "table1": f"tbl_one_{tag}",
        "col_ok": f"col_ok_{tag}",
        "col_extra": f"col_extra_{tag}",
        "col_draft": f"col_draft_{tag}",
    }
    rows = [
        (f"RAW1_{tag}", "", names["table1"], "表一", "confirmed"),
        (f"RAW1_{tag}", "C11", names["col_ok"], "欄一", "confirmed"),
        (f"RAW1_{tag}", "C12", names["col_extra"], "欄二", "confirmed"),
        (f"RAW1_{tag}", "C13", names["col_draft"], "欄三", "draft"),
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
    resp = await client.post(_SERVICES, json={"code": f"svc_{tag}", "name": f"系統別 {tag}"})
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


async def _create_exception_set(client: AsyncClient, name: str) -> dict[str, str]:
    resp = await client.post(_EXCEPTION_SETS, json={"name": name, "description": "臨時分派"})
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _create_role(client: AsyncClient, tag: str, suffix: str) -> dict[str, str]:
    profile = await client.post(_PROFILES, json={"name": f"P-{tag}-{suffix}"})
    assert profile.status_code == 201, profile.text
    resp = await client.post(
        _ROLES,
        json={
            "permission_profile_uid": profile.json()["data"]["uid"],
            "name": f"R-{tag}-{suffix}",
        },
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _grant_operations(
    client: AsyncClient, set_uid: str, operation_uids: list[str]
) -> None:
    resp = await client.put(
        f"{_EXCEPTION_SETS}/{set_uid}/operations", json={"operation_uids": operation_uids}
    )
    assert resp.status_code == 200, resp.text


def _items_path(set_uid: str, operation_uid: str) -> str:
    return f"{_EXCEPTION_SETS}/{set_uid}/operations/{operation_uid}/items"


def _bindings_path(client_uid: str) -> str:
    return f"{_CLIENTS}/{client_uid}/exception-sets"


def _role_path(client_uid: str) -> str:
    return f"{_CLIENTS}/{client_uid}/role"


async def _grant_row_states(
    db_engine: AsyncEngine, table: str, client_uid: str
) -> list[bool]:
    """該 Client 在 RDS 某張指派 / 綁定表上的全部列的 `is_deleted`(繞過 API 直查真身)。"""
    async with db_engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        f"SELECT is_deleted FROM {CLIENT_SETTING_SCHEMA}.{table}"
                        " WHERE api_client_uid = :uid ORDER BY pid"
                    ),
                    {"uid": client_uid},
                )
            )
            .scalars()
            .all()
        )
    return [bool(row) for row in rows]


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


async def _exception_set_names(client: AsyncClient) -> set[str]:
    resp = await client.get(_EXCEPTION_SETS)
    assert resp.status_code == 200, resp.text
    return {str(item["name"]) for item in resp.json()["data"]["items"]}


async def _granted_operation_uids(client: AsyncClient, set_uid: str) -> set[str]:
    resp = await client.get(f"{_EXCEPTION_SETS}/{set_uid}/operations")
    assert resp.status_code == 200, resp.text
    return {str(item["operation_uid"]) for item in resp.json()["data"]["items"]}


async def _granted_items(
    client: AsyncClient, set_uid: str, operation_uid: str
) -> set[tuple[str, str, str]]:
    resp = await client.get(_items_path(set_uid, operation_uid))
    assert resp.status_code == 200, resp.text
    return {
        (str(i["table_name"]), str(i["column_name"]), str(i["action"]))
        for i in resp.json()["data"]["items"]
    }


async def _bindings(client: AsyncClient, client_uid: str) -> list[dict[str, object]]:
    resp = await client.get(_bindings_path(client_uid))
    assert resp.status_code == 200, resp.text
    items: list[dict[str, object]] = resp.json()["data"]["items"]
    return items


async def _matrix_fixture(
    client: AsyncClient, db_engine: AsyncEngine, tag: str
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """一組可用的矩陣場景:作業範圍只開 `table1.col_ok`,特例組已勾選該作業。"""
    names = await _seed_semantic(db_engine, tag)
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")
    await _set_operation_scope(
        client,
        operation["uid"],
        [{"table_name": names["table1"], "column_name": names["col_ok"]}],
    )
    exception_set = await _create_exception_set(client, f"E-{tag}")
    await _grant_operations(client, exception_set["uid"], [operation["uid"]])
    return names, operation, exception_set


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_member_forbidden_on_exception_and_assignment_endpoints(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "member")
    some_uid = str(uuid4())
    other_uid = str(uuid4())
    for method, path, kwargs in [
        ("GET", _EXCEPTION_SETS, {}),
        ("POST", _EXCEPTION_SETS, {"json": {"name": "E"}}),
        ("PATCH", f"{_EXCEPTION_SETS}/{some_uid}", {"json": {"name": "X"}}),
        ("DELETE", f"{_EXCEPTION_SETS}/{some_uid}", {}),
        ("GET", f"{_EXCEPTION_SETS}/{some_uid}/operations", {}),
        (
            "PUT",
            f"{_EXCEPTION_SETS}/{some_uid}/operations",
            {"json": {"operation_uids": []}},
        ),
        ("GET", _items_path(some_uid, other_uid), {}),
        ("PUT", _items_path(some_uid, other_uid), {"json": {"items": []}}),
        ("PUT", _role_path(some_uid), {"json": {"role_uid": other_uid}}),
        ("DELETE", _role_path(some_uid), {}),
        ("GET", _bindings_path(some_uid), {}),
        (
            "POST",
            _bindings_path(some_uid),
            {"json": {"exception_set_uid": other_uid}},
        ),
        ("DELETE", f"{_bindings_path(some_uid)}/{other_uid}", {}),
    ]:
        resp = await client.request(method, path, **kwargs)
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"


# ── 特例組 CRUD ─────────────────────────────────────────────────────────
async def test_exception_set_crud_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    created = await _create_exception_set(client, f"E-{tag}")
    uid = created["uid"]
    assert UUID(uid)
    assert f"E-{tag}" in await _exception_set_names(client)

    patched = await client.patch(f"{_EXCEPTION_SETS}/{uid}", json={"name": f"E-{tag}-改"})
    assert patched.status_code == 200, patched.text
    # 寫入後清單即讀到新值(快取已失效)
    names = await _exception_set_names(client)
    assert f"E-{tag}-改" in names and f"E-{tag}" not in names

    deleted = await client.delete(f"{_EXCEPTION_SETS}/{uid}")
    assert deleted.status_code == 200, deleted.text
    assert f"E-{tag}-改" not in await _exception_set_names(client)

    for action in (
        "client_setting.exception_set_create",
        "client_setting.exception_set_update",
        "client_setting.exception_set_delete",
    ):
        assert len(await _audit_details(db_engine, action, uid)) == 1, action


async def test_exception_set_name_must_be_unique(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_exception_set(client, f"E-{tag}")
    resp = await client.post(_EXCEPTION_SETS, json={"name": f"E-{tag}"})
    assert resp.status_code == 409, resp.text


async def test_exception_set_not_found_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    missing = str(uuid4())
    patched = await client.patch(f"{_EXCEPTION_SETS}/{missing}", json={"name": "X"})
    assert patched.status_code == 404, patched.text
    assert (await client.delete(f"{_EXCEPTION_SETS}/{missing}")).status_code == 404
    assert (await client.get(f"{_EXCEPTION_SETS}/{missing}/operations")).status_code == 404
    resp = await client.put(
        f"{_EXCEPTION_SETS}/{missing}/operations", json={"operation_uids": []}
    )
    assert resp.status_code == 404, resp.text


# ── 特例組勾選作業 / 授權矩陣 ───────────────────────────────────────────
async def test_replace_exception_operations_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names, operation, exception_set = await _matrix_fixture(client, db_engine, tag)
    service_uid = (await client.get(_OPERATIONS)).json()["data"]["items"][0]["service_uid"]
    operation_b = await _create_operation(client, service_uid, f"O2-{tag}")

    assert await _granted_operation_uids(client, exception_set["uid"]) == {operation["uid"]}

    # 先給 O1 授權,再把勾選換成 O2 → O1 的授權項同交易被清掉
    granted = await client.put(
        _items_path(exception_set["uid"], operation["uid"]),
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
    assert len(await _granted_items(client, exception_set["uid"], operation["uid"])) == 1

    await _grant_operations(client, exception_set["uid"], [operation_b["uid"]])
    assert await _granted_operation_uids(client, exception_set["uid"]) == {
        operation_b["uid"]
    }
    assert await _granted_items(client, exception_set["uid"], operation["uid"]) == set()

    # 空陣列 = 全部取消勾選
    await _grant_operations(client, exception_set["uid"], [])
    assert await _granted_operation_uids(client, exception_set["uid"]) == set()

    details = await _audit_details(
        db_engine, "client_setting.exception_operations_replace", exception_set["uid"]
    )
    assert len(details) == 3
    assert "共 0 項" in details[-1]


async def test_replace_exception_items_requires_granted_operation(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """作業未先勾選 → 409(特例同樣遵守「開門與授權缺一不可」)。"""
    await _login_as(client, session_factory, "admin")
    names, operation, exception_set = await _matrix_fixture(client, db_engine, tag)
    service_uid = (await client.get(_OPERATIONS)).json()["data"]["items"][0]["service_uid"]
    ungranted = await _create_operation(client, service_uid, f"O2-{tag}")
    await _set_operation_scope(
        client, ungranted["uid"], [{"table_name": names["table1"], "column_name": "*"}]
    )
    payload = {
        "items": [{"table_name": names["table1"], "column_name": "*", "action": "read"}]
    }

    resp = await client.put(_items_path(exception_set["uid"], ungranted["uid"]), json=payload)
    assert resp.status_code == 409, resp.text

    # 勾選之後同一請求即可通過
    await _grant_operations(
        client, exception_set["uid"], [operation["uid"], ungranted["uid"]]
    )
    ok = await client.put(_items_path(exception_set["uid"], ungranted["uid"]), json=payload)
    assert ok.status_code == 200, ok.text


async def test_replace_exception_items_enforces_scope_and_semantic(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """特例不是繞過作業範圍的後門:超範圍 / 非 confirmed / 重複一律 422,且原授權不動。"""
    await _login_as(client, session_factory, "admin")
    names, operation, exception_set = await _matrix_fixture(client, db_engine, tag)
    path = _items_path(exception_set["uid"], operation["uid"])

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

    # 全程失敗 → 原授權不變
    assert await _granted_items(client, exception_set["uid"], operation["uid"]) == {
        (names["table1"], names["col_ok"], "read")
    }

    details = await _audit_details(
        db_engine, "client_setting.exception_items_replace", exception_set["uid"]
    )
    assert len(details) == 1
    assert "共 1 項" in details[0]


async def test_exception_items_unknown_uid_returns_404(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    _, operation, exception_set = await _matrix_fixture(client, db_engine, tag)
    ghost = str(uuid4())

    assert (await client.get(_items_path(ghost, operation["uid"]))).status_code == 404
    assert (await client.get(_items_path(exception_set["uid"], ghost))).status_code == 404
    resp = await client.put(_items_path(exception_set["uid"], ghost), json={"items": []})
    assert resp.status_code == 404, resp.text


# ── Role 指派(0..1 冪等置換)───────────────────────────────────────────
async def test_client_role_assign_is_idempotent_replacement(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    role_a = await _create_role(client, tag, "a")
    role_b = await _create_role(client, tag, "b")

    first = await client.put(_role_path(client_uid), json={"role_uid": role_a["uid"]})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["role_uid"] == role_a["uid"]
    assert first.json()["data"]["api_client_uid"] == client_uid

    # 重下同一請求:冪等(仍是 0..1,且指派同一 Role)
    again = await client.put(_role_path(client_uid), json={"role_uid": role_a["uid"]})
    assert again.status_code == 200, again.text
    assert again.json()["data"]["role_uid"] == role_a["uid"]

    # 改指派:舊指派同交易被置換,Role A 因而可刪(不再被任何 Client 指派)
    replaced = await client.put(_role_path(client_uid), json={"role_uid": role_b["uid"]})
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["role_uid"] == role_b["uid"]
    assert (await client.delete(f"{_ROLES}/{role_a['uid']}")).status_code == 200
    assert (await client.delete(f"{_ROLES}/{role_b['uid']}")).status_code == 409

    removed = await client.delete(_role_path(client_uid))
    assert removed.status_code == 200, removed.text
    assert removed.json()["data"]["role_uid"] == role_b["uid"]
    # 解除後 Role B 不再被指派 → 可刪
    assert (await client.delete(f"{_ROLES}/{role_b['uid']}")).status_code == 200

    # 本來就沒指派 → 404
    assert (await client.delete(_role_path(client_uid))).status_code == 404

    assert len(
        await _audit_details(db_engine, "client_setting.client_role_assign", client_uid)
    ) == 3
    assert len(
        await _audit_details(db_engine, "client_setting.client_role_remove", client_uid)
    ) == 1


async def test_client_role_assign_unknown_role_returns_404(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    resp = await client.put(_role_path(client_uid), json={"role_uid": str(uuid4())})
    assert resp.status_code == 404, resp.text


async def test_assignment_endpoints_require_existing_client(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """Client 不存在 / 已軟刪一律 404(冷關聯無 FK,防呆只能靠這關)。"""
    await _login_as(client, session_factory, "admin")
    role = await _create_role(client, tag, "a")
    exception_set = await _create_exception_set(client, f"E-{tag}")
    ghost = str(uuid4())
    deleted_client_uid = await _create_api_client(session_factory)
    await _soft_delete_api_client(db_engine, deleted_client_uid)

    for client_uid in (ghost, deleted_client_uid):
        for method, path, kwargs in [
            ("PUT", _role_path(client_uid), {"json": {"role_uid": role["uid"]}}),
            ("DELETE", _role_path(client_uid), {}),
            ("GET", _bindings_path(client_uid), {}),
            (
                "POST",
                _bindings_path(client_uid),
                {"json": {"exception_set_uid": exception_set["uid"]}},
            ),
            ("DELETE", f"{_bindings_path(client_uid)}/{uuid4()}", {}),
        ]:
            resp = await client.request(method, path, **kwargs)
            assert resp.status_code == 404, f"{method} {path}: {resp.text}"


# ── 特例綁定(0..N,各自效期)──────────────────────────────────────────
async def test_bind_exception_set_with_expiry_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    set_never = await _create_exception_set(client, f"E-{tag}-never")
    set_expired = await _create_exception_set(client, f"E-{tag}-expired")

    assert await _bindings(client, client_uid) == []

    # 不帶 expires_at = 不設限
    never = await client.post(
        _bindings_path(client_uid), json={"exception_set_uid": set_never["uid"]}
    )
    assert never.status_code == 201, never.text
    assert never.json()["data"]["expires_at"] is None
    assert never.json()["data"]["is_expired"] is False
    assert never.json()["data"]["exception_set_name"] == f"E-{tag}-never"

    # 過去時間亦允許(綁完即失效),清單以 is_expired 標示
    expired = await client.post(
        _bindings_path(client_uid),
        json={"exception_set_uid": set_expired["uid"], "expires_at": _PAST},
    )
    assert expired.status_code == 201, expired.text
    assert expired.json()["data"]["is_expired"] is True

    items = await _bindings(client, client_uid)
    assert {(str(i["exception_set_uid"]), bool(i["is_expired"])) for i in items} == {
        (set_never["uid"], False),
        (set_expired["uid"], True),
    }

    # 重複綁同一組(即使已過期)→ 409,須先解除再重綁以續期
    duplicated = await client.post(
        _bindings_path(client_uid),
        json={"exception_set_uid": set_expired["uid"], "expires_at": _FUTURE},
    )
    assert duplicated.status_code == 409, duplicated.text

    binding_uid = str(expired.json()["data"]["uid"])
    unbound = await client.delete(f"{_bindings_path(client_uid)}/{binding_uid}")
    assert unbound.status_code == 200, unbound.text
    assert {str(i["exception_set_uid"]) for i in await _bindings(client, client_uid)} == {
        set_never["uid"]
    }

    # 解除後可重綁(續期路徑)
    rebound = await client.post(
        _bindings_path(client_uid),
        json={"exception_set_uid": set_expired["uid"], "expires_at": _FUTURE},
    )
    assert rebound.status_code == 201, rebound.text
    assert rebound.json()["data"]["is_expired"] is False

    # 同一筆解除兩次 → 404
    assert (
        await client.delete(f"{_bindings_path(client_uid)}/{binding_uid}")
    ).status_code == 404

    assert len(
        await _audit_details(db_engine, "client_setting.client_exception_bind", client_uid)
    ) == 3
    assert len(
        await _audit_details(db_engine, "client_setting.client_exception_unbind", client_uid)
    ) == 1


async def test_bind_exception_set_not_found_and_cross_client_unbind(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    tag: str,
) -> None:
    """綁不存在的特例組 404;拿別的 Client 的綁定 uid 解除同樣 404(不得跨 Client 操作)。"""
    await _login_as(client, session_factory, "admin")
    owner_uid = await _create_api_client(session_factory)
    other_uid = await _create_api_client(session_factory)
    exception_set = await _create_exception_set(client, f"E-{tag}")

    missing = await client.post(
        _bindings_path(owner_uid), json={"exception_set_uid": str(uuid4())}
    )
    assert missing.status_code == 404, missing.text

    bound = await client.post(
        _bindings_path(owner_uid), json={"exception_set_uid": exception_set["uid"]}
    )
    assert bound.status_code == 201, bound.text
    binding_uid = str(bound.json()["data"]["uid"])

    resp = await client.delete(f"{_bindings_path(other_uid)}/{binding_uid}")
    assert resp.status_code == 404, resp.text
    assert len(await _bindings(client, owner_uid)) == 1


async def test_bind_expires_at_accepts_timezone_aware_input(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    """帶時區的效期換算為 UTC+8 wall-clock 後入庫(禁前後端各轉一次)。"""
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    exception_set = await _create_exception_set(client, f"E-{tag}")

    resp = await client.post(
        _bindings_path(client_uid),
        json={
            "exception_set_uid": exception_set["uid"],
            "expires_at": "2030-01-01T00:00:00+00:00",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["expires_at"] == "2030-01-01T08:00:00"
    assert (await _bindings(client, client_uid))[0]["expires_at"] == "2030-01-01T08:00:00"


async def test_exception_set_delete_blocked_while_active_binding(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    """未過期綁定擋刪 409;已過期綁定不擋(該綁定本就不生效)。"""
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    active_set = await _create_exception_set(client, f"E-{tag}-active")
    expired_set = await _create_exception_set(client, f"E-{tag}-expired")

    for target, expires_at in ((active_set, _FUTURE), (expired_set, _PAST)):
        bound = await client.post(
            _bindings_path(client_uid),
            json={"exception_set_uid": target["uid"], "expires_at": expires_at},
        )
        assert bound.status_code == 201, bound.text

    blocked = await client.delete(f"{_EXCEPTION_SETS}/{active_set['uid']}")
    assert blocked.status_code == 409, blocked.text
    assert f"E-{tag}-active" in await _exception_set_names(client)

    assert (await client.delete(f"{_EXCEPTION_SETS}/{expired_set['uid']}")).status_code == 200
    # 特例組已軟刪 → 該綁定不再出現在綁定清單(與預覽同一語意)
    assert {str(i["exception_set_uid"]) for i in await _bindings(client, client_uid)} == {
        active_set["uid"]
    }


async def test_exception_set_delete_soft_deletes_leftover_bindings(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """AD-156:特例組軟刪時,其殘留(已過期)綁定一併軟刪,不留看不到又解不掉的殭屍列。"""
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    expired_set = await _create_exception_set(client, f"E-{tag}-expired")

    bound = await client.post(
        _bindings_path(client_uid),
        json={"exception_set_uid": expired_set["uid"], "expires_at": _PAST},
    )
    assert bound.status_code == 201, bound.text
    assert await _grant_row_states(db_engine, "client_exception_sets", client_uid) == [False]

    assert (await client.delete(f"{_EXCEPTION_SETS}/{expired_set['uid']}")).status_code == 200
    assert await _grant_row_states(db_engine, "client_exception_sets", client_uid) == [True]


# ── 註銷連動(AD-152)────────────────────────────────────────────────────
async def test_api_client_delete_clears_rds_grants_and_frees_role_and_set(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """註銷 API Client → RDS 指派 / 綁定同步軟刪、快取失效,Role 與特例組因而刪得掉。"""
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    unrelated_uid = str(uuid4())
    role = await _create_role(client, tag, "a")
    exception_set = await _create_exception_set(client, f"E-{tag}")

    assert (
        await client.put(_role_path(client_uid), json={"role_uid": role["uid"]})
    ).status_code == 200
    bound = await client.post(
        _bindings_path(client_uid), json={"exception_set_uid": exception_set["uid"]}
    )
    assert bound.status_code == 201, bound.text
    # 註銷前:Role 被指派、特例組被未過期綁定引用 → 兩者都刪不掉
    assert (await client.delete(f"{_ROLES}/{role['uid']}")).status_code == 409
    assert (await client.delete(f"{_EXCEPTION_SETS}/{exception_set['uid']}")).status_code == 409

    for uid in (client_uid, unrelated_uid):
        await cache.cache_set(effective_key(uid), "{}", ttl_seconds=300)

    deleted = await client.delete(f"/api/v1/api-clients/{client_uid}")
    assert deleted.status_code == 200, deleted.text

    # RDS 兩表該 Client 的列皆已軟刪(直查真身,不經 API 過濾)
    assert await _grant_row_states(db_engine, "client_roles", client_uid) == [True]
    assert await _grant_row_states(db_engine, "client_exception_sets", client_uid) == [True]
    # 該 Client 的最終權限快取已失效,其他 Client 不受影響
    assert await cache.cache_get(effective_key(client_uid)) is None
    assert await cache.cache_get(effective_key(unrelated_uid)) is not None
    # 孤兒清乾淨 → 不再是「UI 說請先解除指派、清單裡卻沒有 Client 可解」的死路
    assert (await client.delete(f"{_ROLES}/{role['uid']}")).status_code == 200
    assert (await client.delete(f"{_EXCEPTION_SETS}/{exception_set['uid']}")).status_code == 200


async def test_release_paths_still_work_for_soft_deleted_client(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """AD-152(b):Client 已軟刪(例:舊資料無連動清理)時,解除指派 / 解綁仍須放行。

    新增路徑(指派 / 綁定)的存在性防呆不受影響,仍為 404。
    """
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    role = await _create_role(client, tag, "a")
    exception_set = await _create_exception_set(client, f"E-{tag}")

    assert (
        await client.put(_role_path(client_uid), json={"role_uid": role["uid"]})
    ).status_code == 200
    bound = await client.post(
        _bindings_path(client_uid), json={"exception_set_uid": exception_set["uid"]}
    )
    assert bound.status_code == 201, bound.text
    binding_uid = str(bound.json()["data"]["uid"])

    # 繞過 service 直接軟刪 → RDS 側的指派 / 綁定成為孤兒
    await _soft_delete_api_client(db_engine, client_uid)

    assert (await client.delete(_role_path(client_uid))).status_code == 200
    unbound = await client.delete(f"{_bindings_path(client_uid)}/{binding_uid}")
    assert unbound.status_code == 200, unbound.text
    assert await _grant_row_states(db_engine, "client_roles", client_uid) == [True]
    assert await _grant_row_states(db_engine, "client_exception_sets", client_uid) == [True]

    # 新增路徑仍擋(已註銷的 Client 不得再被授權)
    assert (
        await client.put(_role_path(client_uid), json={"role_uid": role["uid"]})
    ).status_code == 404
    assert (
        await client.post(
            _bindings_path(client_uid), json={"exception_set_uid": exception_set["uid"]}
        )
    ).status_code == 404


# ── 失效扇出 ────────────────────────────────────────────────────────────
async def test_assignment_and_binding_writes_invalidate_client_cache(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    client_uid = await _create_api_client(session_factory)
    unrelated_uid = str(uuid4())
    role = await _create_role(client, tag, "a")
    exception_set = await _create_exception_set(client, f"E-{tag}")

    async def _seed() -> None:
        for uid in (client_uid, unrelated_uid):
            await cache.cache_set(effective_key(uid), "{}", ttl_seconds=300)

    async def _assert_invalidated() -> None:
        assert await cache.cache_get(effective_key(client_uid)) is None
        assert await cache.cache_get(effective_key(unrelated_uid)) is not None

    await _seed()
    assigned = await client.put(_role_path(client_uid), json={"role_uid": role["uid"]})
    assert assigned.status_code == 200, assigned.text
    await _assert_invalidated()

    await _seed()
    assert (await client.delete(_role_path(client_uid))).status_code == 200
    await _assert_invalidated()

    await _seed()
    bound = await client.post(
        _bindings_path(client_uid), json={"exception_set_uid": exception_set["uid"]}
    )
    assert bound.status_code == 201, bound.text
    await _assert_invalidated()

    await _seed()
    binding_uid = str(bound.json()["data"]["uid"])
    assert (
        await client.delete(f"{_bindings_path(client_uid)}/{binding_uid}")
    ).status_code == 200
    await _assert_invalidated()


async def test_exception_set_write_invalidates_bound_client_cache(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """特例組內容 / 名稱異動 → 反查綁該組的 Client 失效,其他 Client 不受影響。"""
    await _login_as(client, session_factory, "admin")
    names, operation, exception_set = await _matrix_fixture(client, db_engine, tag)
    bound_client_uid = await _create_api_client(session_factory)
    unrelated_uid = str(uuid4())
    bound = await client.post(
        _bindings_path(bound_client_uid),
        json={"exception_set_uid": exception_set["uid"]},
    )
    assert bound.status_code == 201, bound.text

    async def _seed() -> None:
        for uid in (bound_client_uid, unrelated_uid):
            await cache.cache_set(effective_key(uid), "{}", ttl_seconds=300)

    async def _assert_invalidated() -> None:
        assert await cache.cache_get(effective_key(bound_client_uid)) is None
        assert await cache.cache_get(effective_key(unrelated_uid)) is not None

    # 授權矩陣異動
    await _seed()
    granted = await client.put(
        _items_path(exception_set["uid"], operation["uid"]),
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
    await _assert_invalidated()

    # 勾選作業異動
    await _seed()
    await _grant_operations(client, exception_set["uid"], [])
    await _assert_invalidated()

    # 改名(名稱會進 effective 快取內容)
    await _seed()
    renamed = await client.patch(
        f"{_EXCEPTION_SETS}/{exception_set['uid']}", json={"name": f"E-{tag}-改"}
    )
    assert renamed.status_code == 200, renamed.text
    await _assert_invalidated()
