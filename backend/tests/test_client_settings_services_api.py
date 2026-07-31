"""系統別 / 作業管理 API 測試(v1.6.1 task-004)。

對齊 test_client_setting_repo.py / test_semantic_mappings_api.py 模式:連真實本地
PostgreSQL 測試 DB 同時假扮「自有 DB」與「目標 RDS」(env 指向 data_center_etl_test,
不觸碰真正 AWS RDS)。清理一律 DELETE 資料,**不做任何 DROP**。

涵蓋:非 admin 403、系統別 / 作業 CRUD 正流程、code 與作業名唯一 409、刪除防呆 409、
範圍整批置換 + 非 confirmed 語意映射 422、稽核事件、寫後清單讀到新值(快取失效)。
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
from httpx import ASGITransport, AsyncClient, Response  # noqa: E402
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

_BASE_PATH = "/api/v1/client-settings"
_SERVICES = f"{_BASE_PATH}/services"
_OPERATIONS = f"{_BASE_PATH}/operations"

ACTOR_UID = uuid4()

# 本測試(單一 pytest 進程內序列執行,無併發風險)以 `_login_as` 建立的 admin uid;
# 該 uid 即透過 API 建立資料的 created_by,清理時併入過濾條件,避免動到併行測試檔的資料
_test_actor_uids: list[UUID] = []


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
    `semantic_mappings` 無 created_by 欄位,改以本測試專屬 `tag` 前綴比對(見 `_seed_semantic`)。
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
        user = await UserRepository(session).create(
            username=username, password_hash=password_hash, role=role
        )
        await session.commit()
    _test_actor_uids.append(user.uid)
    resp = await client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text


async def _seed_semantic(db_engine: AsyncEngine, tag: str) -> dict[str, str]:
    """種一組語意映射,回傳英文名對照。

    - `T1`(confirmed 表層級 + 一 confirmed 欄 + 一 draft 欄)→ 可授權,draft 欄不可
    - `T2`(draft 表層級 + confirmed 欄)→ 表未定稿,整表不可授權
    """
    names = {
        "table1": f"tbl_one_{tag}",
        "col_ok": f"col_ok_{tag}",
        "col_draft": f"col_draft_{tag}",
        "table2": f"tbl_two_{tag}",
    }
    rows = [
        (f"RAW1_{tag}", "", names["table1"], "表一", "confirmed"),
        (f"RAW1_{tag}", "C11", names["col_ok"], "欄一", "confirmed"),
        (f"RAW1_{tag}", "C12", names["col_draft"], "欄二", "draft"),
        (f"RAW2_{tag}", "", names["table2"], "表二", "draft"),
        (f"RAW2_{tag}", "C21", f"col_alpha_{tag}", "欄甲", "confirmed"),
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


async def _create_service(client: AsyncClient, tag: str, suffix: str = "") -> dict[str, str]:
    resp = await client.post(
        _SERVICES,
        json={"code": f"svc-{tag}{suffix}", "name": f"系統別 {tag}{suffix}", "description": "測試"},
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


async def _create_operation(
    client: AsyncClient, service_uid: str, name: str
) -> dict[str, str]:
    resp = await client.post(
        _OPERATIONS, json={"service_uid": service_uid, "name": name}
    )
    assert resp.status_code == 201, resp.text
    data: dict[str, str] = resp.json()["data"]
    return data


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


def _codes(response: Response) -> set[str]:
    """系統別清單回應內的 code 集合(以成員關係斷言,不受並行測試殘留資料影響)。"""
    return {str(item["code"]) for item in response.json()["data"]["items"]}


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_member_forbidden_on_every_endpoint(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "member")
    some_uid = str(uuid4())
    for method, path, kwargs in [
        ("GET", _SERVICES, {}),
        ("POST", _SERVICES, {"json": {"code": "erp", "name": "ERP"}}),
        ("PATCH", f"{_SERVICES}/{some_uid}", {"json": {"name": "X"}}),
        ("DELETE", f"{_SERVICES}/{some_uid}", {}),
        ("GET", _OPERATIONS, {}),
        ("POST", _OPERATIONS, {"json": {"service_uid": some_uid, "name": "O1"}}),
        ("PATCH", f"{_OPERATIONS}/{some_uid}", {"json": {"name": "X"}}),
        ("DELETE", f"{_OPERATIONS}/{some_uid}", {}),
        ("GET", f"{_OPERATIONS}/{some_uid}/items", {}),
        ("PUT", f"{_OPERATIONS}/{some_uid}/items", {"json": {"items": []}}),
    ]:
        resp = await client.request(method, path, **kwargs)
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"


# ── 系統別 CRUD ─────────────────────────────────────────────────────────
async def test_service_crud_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    created = await _create_service(client, tag)
    uid = created["uid"]
    assert created["code"] == f"svc-{tag}"
    assert UUID(uid)

    listed = await client.get(_SERVICES)
    assert listed.status_code == 200, listed.text
    assert f"svc-{tag}" in _codes(listed)

    patched = await client.patch(f"{_SERVICES}/{uid}", json={"name": "改名後"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == "改名後"

    # 寫入後清單即讀到新值(快取已失效)
    listed = await client.get(_SERVICES)
    names = {i["code"]: i["name"] for i in listed.json()["data"]["items"]}
    assert names[f"svc-{tag}"] == "改名後"

    deleted = await client.delete(f"{_SERVICES}/{uid}")
    assert deleted.status_code == 200, deleted.text
    listed = await client.get(_SERVICES)
    assert f"svc-{tag}" not in _codes(listed)

    for action in (
        "client_setting.service_create",
        "client_setting.service_update",
        "client_setting.service_delete",
    ):
        assert len(await _audit_details(db_engine, action, uid)) == 1, action


async def test_service_code_must_be_unique(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_service(client, tag)
    resp = await client.post(_SERVICES, json={"code": f"svc-{tag}", "name": "重複"})
    assert resp.status_code == 409, resp.text


async def test_service_code_is_not_patchable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    """`code` 為路由分段契約:帶了也不生效(schema 不收),其餘欄位照常更新。"""
    await _login_as(client, session_factory, "admin")
    created = await _create_service(client, tag)
    resp = await client.patch(
        f"{_SERVICES}/{created['uid']}", json={"code": "hacked", "name": "新名"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["code"] == f"svc-{tag}"
    assert resp.json()["data"]["name"] == "新名"


async def test_service_invalid_code_rejected(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post(_SERVICES, json={"code": "ERP 系統", "name": "X"})
    assert resp.status_code == 422, resp.text


async def test_service_delete_blocked_while_operations_exist(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")

    blocked = await client.delete(f"{_SERVICES}/{service['uid']}")
    assert blocked.status_code == 409, blocked.text
    assert f"svc-{tag}" in _codes(await client.get(_SERVICES))

    assert (await client.delete(f"{_OPERATIONS}/{operation['uid']}")).status_code == 200
    assert (await client.delete(f"{_SERVICES}/{service['uid']}")).status_code == 200


async def test_service_not_found_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.patch(f"{_SERVICES}/{uuid4()}", json={"name": "X"})
    assert resp.status_code == 404, resp.text


# ── 作業 CRUD ───────────────────────────────────────────────────────────
async def test_operation_crud_and_service_filter(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    service_a = await _create_service(client, tag, suffix="a")
    service_b = await _create_service(client, tag, suffix="b")
    op_a = await _create_operation(client, service_a["uid"], f"O1-{tag}")
    await _create_operation(client, service_b["uid"], f"O2-{tag}")
    assert op_a["service_uid"] == service_a["uid"]

    filtered = await client.get(_OPERATIONS, params={"service_uid": service_a["uid"]})
    assert filtered.status_code == 200, filtered.text
    assert [i["name"] for i in filtered.json()["data"]["items"]] == [f"O1-{tag}"]

    all_ops = {i["name"] for i in (await client.get(_OPERATIONS)).json()["data"]["items"]}
    assert {f"O1-{tag}", f"O2-{tag}"} <= all_ops

    patched = await client.patch(
        f"{_OPERATIONS}/{op_a['uid']}", json={"name": f"O1x-{tag}", "description": "說明"}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["name"] == f"O1x-{tag}"
    # 歸屬系統別不因 PATCH 改變
    assert patched.json()["data"]["service_uid"] == service_a["uid"]

    deleted = await client.delete(f"{_OPERATIONS}/{op_a['uid']}")
    assert deleted.status_code == 200, deleted.text
    remaining = {i["name"] for i in (await client.get(_OPERATIONS)).json()["data"]["items"]}
    assert f"O1x-{tag}" not in remaining

    for action in (
        "client_setting.operation_create",
        "client_setting.operation_update",
        "client_setting.operation_delete",
    ):
        assert len(await _audit_details(db_engine, action, op_a["uid"])) == 1, action


async def test_operation_name_unique_within_service_only(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    service_a = await _create_service(client, tag, suffix="a")
    service_b = await _create_service(client, tag, suffix="b")
    await _create_operation(client, service_a["uid"], f"O1-{tag}")

    duplicated = await client.post(
        _OPERATIONS, json={"service_uid": service_a["uid"], "name": f"O1-{tag}"}
    )
    assert duplicated.status_code == 409, duplicated.text

    # 不同系統別同名可建
    await _create_operation(client, service_b["uid"], f"O1-{tag}")


async def test_operation_create_with_unknown_service_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post(
        _OPERATIONS, json={"service_uid": str(uuid4()), "name": f"O1-{tag}"}
    )
    assert resp.status_code == 404, resp.text


async def test_operation_delete_blocked_when_referenced(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    """被權限設定檔勾選的作業不得刪(設定檔管理端點屬 task-005,此處直接以 repo 建關聯)。"""
    await _login_as(client, session_factory, "admin")
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")

    async with client_setting_session() as session:
        repo = ClientSettingRepository(session)
        target = await repo.get_operation_by_uid(UUID(operation["uid"]))
        assert target is not None
        profile = await repo.create_permission_profile(
            name=f"P-{tag}", actor_uid=ACTOR_UID
        )
        await repo.replace_profile_operations(
            profile.pid, [target.pid], actor_uid=ACTOR_UID
        )
        await session.commit()

    blocked = await client.delete(f"{_OPERATIONS}/{operation['uid']}")
    assert blocked.status_code == 409, blocked.text
    names = {i["name"] for i in (await client.get(_OPERATIONS)).json()["data"]["items"]}
    assert f"O1-{tag}" in names


# ── 作業範圍 items + semantic 驗證 ──────────────────────────────────────
async def test_replace_operation_items_round_trip(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names = await _seed_semantic(db_engine, tag)
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")
    items_path = f"{_OPERATIONS}/{operation['uid']}/items"

    assert (await client.get(items_path)).json()["data"] == {"items": [], "total": 0}

    replaced = await client.put(
        items_path,
        json={
            "items": [
                {"table_name": names["table1"], "column_name": names["col_ok"]},
                {"table_name": names["table1"], "column_name": "*"},
            ]
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["total"] == 2

    listed = await client.get(items_path)
    assert {
        (i["table_name"], i["column_name"]) for i in listed.json()["data"]["items"]
    } == {(names["table1"], names["col_ok"]), (names["table1"], "*")}

    # 再次置換:舊集合整批換掉,不殘留
    again = await client.put(
        items_path,
        json={"items": [{"table_name": names["table1"], "column_name": "*"}]},
    )
    assert again.status_code == 200, again.text
    listed = await client.get(items_path)
    assert [
        (i["table_name"], i["column_name"]) for i in listed.json()["data"]["items"]
    ] == [(names["table1"], "*")]

    # 空陣列 = 清空範圍
    assert (await client.put(items_path, json={"items": []})).status_code == 200
    assert (await client.get(items_path)).json()["data"]["total"] == 0

    details = await _audit_details(
        db_engine, "client_setting.operation_items_replace", operation["uid"]
    )
    assert len(details) == 3
    assert "共 2 項" in details[0]


async def test_replace_operation_items_rejects_non_confirmed(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    """非 confirmed 的表 / 欄位一律 422 並逐筆列明;失敗時範圍原封不動。"""
    await _login_as(client, session_factory, "admin")
    names = await _seed_semantic(db_engine, tag)
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")
    items_path = f"{_OPERATIONS}/{operation['uid']}/items"

    ok = await client.put(
        items_path,
        json={"items": [{"table_name": names["table1"], "column_name": names["col_ok"]}]},
    )
    assert ok.status_code == 200, ok.text

    for bad_item in (
        # 欄位為 draft
        {"table_name": names["table1"], "column_name": names["col_draft"]},
        # 表層級為 draft(整表不可授權,`*` 亦然)
        {"table_name": names["table2"], "column_name": "*"},
        # 表根本不存在
        {"table_name": f"no_such_table_{tag}", "column_name": "*"},
        # 欄位不存在
        {"table_name": names["table1"], "column_name": f"no_such_col_{tag}"},
    ):
        resp = await client.put(items_path, json={"items": [bad_item]})
        assert resp.status_code == 422, resp.text
        assert f"{bad_item['table_name']}.{bad_item['column_name']}" in resp.json()["detail"]

    # 多筆非法一次列明
    resp = await client.put(
        items_path,
        json={
            "items": [
                {"table_name": names["table1"], "column_name": names["col_ok"]},
                {"table_name": names["table1"], "column_name": names["col_draft"]},
                {"table_name": names["table2"], "column_name": "*"},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    assert names["col_draft"] in resp.json()["detail"]
    assert names["table2"] in resp.json()["detail"]

    # 全程失敗 → 原範圍不變
    listed = await client.get(items_path)
    assert [
        (i["table_name"], i["column_name"]) for i in listed.json()["data"]["items"]
    ] == [(names["table1"], names["col_ok"])]


async def test_replace_operation_items_rejects_duplicates(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
    tag: str,
) -> None:
    await _login_as(client, session_factory, "admin")
    names = await _seed_semantic(db_engine, tag)
    service = await _create_service(client, tag)
    operation = await _create_operation(client, service["uid"], f"O1-{tag}")

    resp = await client.put(
        f"{_OPERATIONS}/{operation['uid']}/items",
        json={
            "items": [
                {"table_name": names["table1"], "column_name": "*"},
                {"table_name": names["table1"], "column_name": "*"},
            ]
        },
    )
    assert resp.status_code == 422, resp.text
    assert "重複" in resp.json()["detail"]


async def test_operation_items_unknown_operation_returns_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    assert (await client.get(f"{_OPERATIONS}/{uuid4()}/items")).status_code == 404
    resp = await client.put(f"{_OPERATIONS}/{uuid4()}/items", json={"items": []})
    assert resp.status_code == 404, resp.text


# ── 快取行為(cache-aside + 異動即失效)────────────────────────────────
async def test_service_list_uses_cache_until_write_invalidates(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession], tag: str
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_service(client, tag, suffix="a")

    # 第一次讀取回源並回填
    assert f"svc-{tag}a" in _codes(await client.get(_SERVICES))

    # 繞過 API 直改 RDS(模擬他機寫入):快取未失效 → 仍讀到舊值
    async with client_setting_session() as session:
        await ClientSettingRepository(session).create_service(
            code=f"svc-{tag}b", name="繞過 API", actor_uid=ACTOR_UID
        )
        await session.commit()
    assert f"svc-{tag}b" not in _codes(await client.get(_SERVICES))

    # 經 API 寫入 → 失效扇出 → 兩筆皆讀得到
    await _create_service(client, tag, suffix="c")
    codes = _codes(await client.get(_SERVICES))
    assert {f"svc-{tag}a", f"svc-{tag}b", f"svc-{tag}c"} <= codes
