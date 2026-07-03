"""task-004 ETL 設定管理 API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:CRUD、停用後清單狀態正確、mapping 缺 comment 回 400、viewer 寫入 403、
ApiResponse 外殼、軟刪除(資料仍在 DB,is_deleted=true)、最近執行狀態。
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
from uuid import UUID, uuid4  # noqa: E402

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
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import EtlMapping, EtlRun, EtlRunLog, EtlTable  # noqa: E402
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
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))
        await conn.execute(text("DELETE FROM etl_mappings"))
        await conn.execute(text("DELETE FROM etl_tables"))
        await conn.execute(text("DELETE FROM users"))


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


def _table_payload(suffix: str = "a") -> dict[str, object]:
    return {
        "source_schema": "DS",
        "source_table": f"SRC_TABLE_{suffix}",
        "target_schema": "public",
        "target_table": f"tgt_table_{suffix}",
        "description": f"測試表 {suffix}",
        "is_enabled": True,
        "mappings": [
            {
                "source_column": "COL_A",
                "target_column": "col_a",
                "transform_type": "str",
                "comment": "欄位 A / Column A",
                "sort_order": 1,
            },
            {
                "source_column": "COL_QTY",
                "target_column": "col_qty",
                "transform_type": "int",
                "comment": "數量 / Quantity",
                "sort_order": 2,
            },
        ],
    }


async def _create_table(client: AsyncClient, suffix: str = "a") -> str:
    resp = await client.post("/api/v1/etl-tables", json=_table_payload(suffix))
    assert resp.status_code == 201, resp.text
    uid = resp.json()["data"]["uid"]
    assert isinstance(uid, str)
    return uid


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    """斷言 ApiResponse 外殼:success / data / detail / response_code。"""
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


# ── 未登入 / viewer 權限 ────────────────────────────────────────────────
async def test_list_requires_login_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/etl-tables")
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


async def test_viewer_can_read_but_writes_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    # 讀取 OK
    resp = await client.get("/api/v1/etl-tables")
    assert resp.status_code == 200
    # 寫入類一律 403:create / patch / delete / enable / disable / mappings
    fake_uid = str(uuid4())
    assert (
        await client.post("/api/v1/etl-tables", json=_table_payload())
    ).status_code == 403
    assert (
        await client.patch(f"/api/v1/etl-tables/{fake_uid}", json={"description": "x"})
    ).status_code == 403
    assert (await client.delete(f"/api/v1/etl-tables/{fake_uid}")).status_code == 403
    assert (await client.post(f"/api/v1/etl-tables/{fake_uid}/enable")).status_code == 403
    assert (await client.post(f"/api/v1/etl-tables/{fake_uid}/disable")).status_code == 403
    resp = await client.put(
        f"/api/v1/etl-tables/{fake_uid}/mappings", json={"mappings": []}
    )
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


# ── CRUD ────────────────────────────────────────────────────────────────
async def test_create_table_201_with_mappings(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post("/api/v1/etl-tables", json=_table_payload())
    assert resp.status_code == 201
    body = resp.json()
    _assert_shell(body, success=True, response_code=201)
    data = body["data"]
    assert data["source_schema"] == "DS"
    assert data["is_enabled"] is True
    assert data["mapping_count"] == 2
    assert [m["target_column"] for m in data["mappings"]] == ["col_a", "col_qty"]
    assert all(m["comment"] for m in data["mappings"])


async def test_create_duplicate_source_409(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _create_table(client, "dup")
    resp = await client.post("/api/v1/etl-tables", json=_table_payload("dup"))
    assert resp.status_code == 409
    _assert_shell(resp.json(), success=False, response_code=409)


async def test_list_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    for suffix in ("p1", "p2", "p3"):
        await _create_table(client, suffix)
    resp = await client.get("/api/v1/etl-tables", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    # data 禁直接為 array:必為 {items, total, ...}
    assert isinstance(body["data"], dict)
    assert body["data"]["total"] == 3
    assert len(body["data"]["items"]) == 2
    assert body["data"]["page"] == 1
    assert body["data"]["page_size"] == 2
    resp2 = await client.get("/api/v1/etl-tables", params={"page": 2, "page_size": 2})
    assert len(resp2.json()["data"]["items"]) == 1


async def test_get_detail_includes_mappings(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.get(f"/api/v1/etl-tables/{uid}")
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    mappings = body["data"]["mappings"]
    assert len(mappings) == 2
    assert mappings[0]["source_column"] == "COL_A"
    assert mappings[0]["transform_type"] == "str"
    assert mappings[0]["comment"] == "欄位 A / Column A"


async def test_get_detail_not_found_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.get(f"/api/v1/etl-tables/{uuid4()}")
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)


async def test_patch_updates_target_and_description(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.patch(
        f"/api/v1/etl-tables/{uid}",
        json={"target_table": "tgt_renamed", "description": "改過的描述"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["target_table"] == "tgt_renamed"
    assert data["description"] == "改過的描述"
    # 未帶欄位不變
    assert data["target_schema"] == "public"


async def test_delete_is_soft_delete(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.delete(f"/api/v1/etl-tables/{uid}")
    assert resp.status_code == 200
    _assert_shell(resp.json(), success=True, response_code=200)
    # 清單與明細都看不到
    assert (await client.get(f"/api/v1/etl-tables/{uid}")).status_code == 404
    list_body = (await client.get("/api/v1/etl-tables")).json()
    assert list_body["data"]["total"] == 0
    # DB 資料仍在(軟刪除,禁物理刪除),mappings 一併軟刪
    async with session_factory() as session:
        table = (
            await session.execute(select(EtlTable).where(EtlTable.uid == UUID(uid)))
        ).scalar_one()
        assert table.is_deleted is True
        rows = (
            await session.execute(
                select(EtlMapping).where(EtlMapping.etl_table_pid == table.pid)
            )
        ).scalars().all()
        assert len(rows) == 2
        assert all(m.is_deleted for m in rows)


# ── 啟用 / 停用 ─────────────────────────────────────────────────────────
async def test_disable_then_list_status_correct(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid_a = await _create_table(client, "on")
    uid_b = await _create_table(client, "off")
    resp = await client.post(f"/api/v1/etl-tables/{uid_b}/disable")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False
    # 停用後清單狀態正確:停用者 false、其餘 true,且仍在清單內
    list_body = (await client.get("/api/v1/etl-tables")).json()
    by_uid = {item["uid"]: item for item in list_body["data"]["items"]}
    assert list_body["data"]["total"] == 2
    assert by_uid[uid_a]["is_enabled"] is True
    assert by_uid[uid_b]["is_enabled"] is False
    # 重新啟用
    resp = await client.post(f"/api/v1/etl-tables/{uid_b}/enable")
    assert resp.json()["data"]["is_enabled"] is True


# ── mapping 更新 ────────────────────────────────────────────────────────
async def test_mappings_missing_comment_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    # comment 缺值(None)→ 400
    resp = await client.put(
        f"/api/v1/etl-tables/{uid}/mappings",
        json={
            "mappings": [
                {"source_column": "COL_X", "target_column": "col_x", "comment": None}
            ]
        },
    )
    assert resp.status_code == 400
    body = resp.json()
    _assert_shell(body, success=False, response_code=400)
    assert "comment" in str(body["detail"]).lower()
    # comment 空白字串 → 同樣 400,不可靜默通過
    resp = await client.put(
        f"/api/v1/etl-tables/{uid}/mappings",
        json={
            "mappings": [
                {"source_column": "COL_X", "target_column": "col_x", "comment": "   "}
            ]
        },
    )
    assert resp.status_code == 400
    # 驗證失敗不得動到既有 mapping
    detail = (await client.get(f"/api/v1/etl-tables/{uid}")).json()["data"]
    assert detail["mapping_count"] == 2


async def test_create_table_mapping_missing_comment_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    payload = _table_payload("nc")
    mappings = payload["mappings"]
    assert isinstance(mappings, list)
    mappings[0]["comment"] = ""
    resp = await client.post("/api/v1/etl-tables", json=payload)
    assert resp.status_code == 400
    _assert_shell(resp.json(), success=False, response_code=400)


async def test_mappings_invalid_transform_type_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.put(
        f"/api/v1/etl-tables/{uid}/mappings",
        json={
            "mappings": [
                {
                    "source_column": "COL_X",
                    "target_column": "col_x",
                    "transform_type": "datetime",
                    "comment": "欄位 X",
                }
            ]
        },
    )
    assert resp.status_code == 400


async def test_mappings_duplicate_target_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.put(
        f"/api/v1/etl-tables/{uid}/mappings",
        json={
            "mappings": [
                {"source_column": "A", "target_column": "same", "comment": "甲"},
                {"source_column": "B", "target_column": "same", "comment": "乙"},
            ]
        },
    )
    assert resp.status_code == 400


async def test_mappings_replace_success_and_soft_delete_old(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    resp = await client.put(
        f"/api/v1/etl-tables/{uid}/mappings",
        json={
            "mappings": [
                {
                    "source_column": "COL_NEW",
                    "target_column": "col_new",
                    "transform_type": "float",
                    "comment": "新欄位 / New column",
                    "sort_order": 1,
                }
            ]
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    data = body["data"]
    assert data["mapping_count"] == 1
    assert data["mappings"][0]["target_column"] == "col_new"
    assert data["mappings"][0]["comment"] == "新欄位 / New column"
    # 舊 mappings 為軟刪除(仍在 DB,is_deleted=true)
    async with session_factory() as session:
        table = (
            await session.execute(select(EtlTable).where(EtlTable.uid == UUID(uid)))
        ).scalar_one()
        rows = (
            await session.execute(
                select(EtlMapping).where(EtlMapping.etl_table_pid == table.pid)
            )
        ).scalars().all()
        assert len(rows) == 3  # 舊 2(軟刪)+ 新 1
        assert sum(1 for m in rows if m.is_deleted) == 2


# ── 最近執行狀態 ────────────────────────────────────────────────────────
async def test_list_shows_latest_run_status(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid = await _create_table(client)
    actor = uuid4()
    async with session_factory() as session:
        table = (
            await session.execute(select(EtlTable).where(EtlTable.uid == UUID(uid)))
        ).scalar_one()
        run = EtlRun(
            uid=uuid4(),
            trigger_type="manual",
            status="partial",
            created_by=actor,
            updated_by=actor,
        )
        session.add(run)
        await session.flush()
        # 先失敗、後成功:清單須顯示最新一筆(success)
        for status in ("failed", "success"):
            session.add(
                EtlRunLog(
                    uid=uuid4(),
                    etl_run_pid=run.pid,
                    etl_table_pid=table.pid,
                    source_schema=table.source_schema,
                    source_table=table.source_table,
                    status=status,
                    created_by=actor,
                    updated_by=actor,
                )
            )
            await session.flush()
        await session.commit()

    list_body = (await client.get("/api/v1/etl-tables")).json()
    item = list_body["data"]["items"][0]
    assert item["last_run_status"] == "success"
    detail = (await client.get(f"/api/v1/etl-tables/{uid}")).json()["data"]
    assert detail["last_run_status"] == "success"
