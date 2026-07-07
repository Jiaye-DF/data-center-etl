"""task-004 排程 API v1.3.1 重構測試(真實 PostgreSQL 測試 DB)。

涵蓋:
- GET /schedules(逐表視角:schema 必填、items 含 table_name/is_enabled/last_run_status;
  enabled / last_result / keyword 過濾 + 分頁)
- GET /schedules/schemas(各 schema 摘要:表數 / 已啟用排程數)
- PATCH /schedules/{uid}(cron / 啟停 / 描述;invalid cron 400;404)
- POST /schedules/{uid}/enable、/disable
- POST /schedules/batch-enabled(admin 回影響筆數;viewer 403)
- 已移除端點:POST /schedules(create)、DELETE /schedules/{uid} → 404/405
- 未登入 401、viewer 寫入 403
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
from datetime import datetime  # noqa: E402
from uuid import uuid4  # noqa: E402

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
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Dataset, EtlRun, EtlRunLog  # noqa: E402
from app.repositories.rds_table_meta_repo import RdsTableMetaRepository  # noqa: E402
from app.repositories.schedule_repo import ScheduleRepository  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.utils.datetime import db_now  # noqa: E402

_ACTOR = uuid4()


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
                # create_all 不會為既有表補欄位;測試 DB 為持久複用,補齊 task-001 欄位
                # (ADD COLUMN IF NOT EXISTS 為非破壞性、冪等操作;禁 DROP)
                await conn.execute(
                    text(
                        "ALTER TABLE schedules "
                        "ADD COLUMN IF NOT EXISTS source_schema VARCHAR(100)"
                    )
                )
                await conn.execute(
                    text(
                        "ALTER TABLE schedules "
                        "ADD COLUMN IF NOT EXISTS source_table VARCHAR(200)"
                    )
                )
                await conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS uq_schedules_source_table "
                        "ON schedules (source_schema, source_table) "
                        "WHERE is_deleted = false"
                    )
                )
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
        await conn.execute(text("DELETE FROM schedules"))
        await conn.execute(text("DELETE FROM etl_mappings"))
        await conn.execute(text("DELETE FROM etl_tables"))
        await conn.execute(text("DELETE FROM rds_table_meta"))
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


# ── helpers ─────────────────────────────────────────────────────────────
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


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    """斷言 ApiResponse 外殼:success / data / detail / response_code。"""
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


async def _snapshot(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema: str,
    table: str,
    business_name: str | None = None,
    row_count: int = 0,
    last_synced_at: datetime | None = None,
) -> None:
    async with session_factory() as session:
        meta = await RdsTableMetaRepository(session).upsert_snapshot(
            dataset=Dataset.SOURCE,
            schema_name=schema,
            table_name=table,
            business_name=business_name,
            column_count=1,
            row_count=row_count,
            snapshot_at=db_now(),
            actor_uid=_ACTOR,
        )
        if last_synced_at is not None:
            meta.last_synced_at = last_synced_at
        await session.commit()


async def _bind_schedule(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema: str,
    table: str,
    cron: str = "0 2 * * *",
    is_enabled: bool = True,
) -> str:
    async with session_factory() as session:
        sched = await ScheduleRepository(session).upsert_for_source_table(
            schema=schema,
            table=table,
            name=f"{schema}.{table}",
            cron_expr=cron,
            is_enabled=is_enabled,
            actor_uid=_ACTOR,
        )
        uid = str(sched.uid)
        await session.commit()
    return uid


async def _insert_log(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    schema: str,
    table: str,
    status: str,
) -> None:
    """插入一次 run + 一筆逐表 log(pid 遞增,較晚插入者為最新)。"""
    async with session_factory() as session:
        run = EtlRun(
            uid=uuid4(),
            trigger_type="manual",
            status="success",
            created_by=_ACTOR,
            updated_by=_ACTOR,
        )
        session.add(run)
        await session.flush()
        session.add(
            EtlRunLog(
                uid=uuid4(),
                etl_run_pid=run.pid,
                etl_table_pid=None,
                source_schema=schema,
                source_table=table,
                status=status,
                created_by=_ACTOR,
                updated_by=_ACTOR,
            )
        )
        await session.commit()


# ── 未登入 / viewer 權限 ────────────────────────────────────────────────
async def test_list_requires_login_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/schedules", params={"schema": "DS"})
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


async def test_viewer_can_read_but_writes_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    await _snapshot(session_factory, schema="DS", table="GAT_FILE")
    uid = await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    # 讀取 OK
    assert (
        await client.get("/api/v1/schedules", params={"schema": "DS"})
    ).status_code == 200
    assert (await client.get("/api/v1/schedules/schemas")).status_code == 200
    # 寫入類一律 403:patch / enable / disable / batch-enabled
    assert (
        await client.patch(f"/api/v1/schedules/{uid}", json={"description": "x"})
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/schedules/{uid}/enable")
    ).status_code == 403
    assert (
        await client.post(f"/api/v1/schedules/{uid}/disable")
    ).status_code == 403
    resp = await client.post("/api/v1/schedules/batch-enabled", json={"enabled": True})
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


# ── 已移除端點 ──────────────────────────────────────────────────────────
async def test_removed_create_and_delete_endpoints(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    # POST /schedules(create)已移除 → 405(該路徑僅註冊 GET)或 404
    create_resp = await client.post(
        "/api/v1/schedules",
        json={"name": "x", "cron_expr": "0 2 * * *", "is_enabled": True},
    )
    assert create_resp.status_code in (404, 405)
    # DELETE /schedules/{uid} 已移除 → 405(該路徑僅註冊 PATCH)或 404
    delete_resp = await client.delete(f"/api/v1/schedules/{uuid4()}")
    assert delete_resp.status_code in (404, 405)


# ── 逐表視角清單 ────────────────────────────────────────────────────────
async def test_list_tables_view_shell_and_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(
        session_factory, schema="DS", table="GAT_FILE", business_name="訂單", row_count=10
    )
    await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    # 先 failed 後 success → 最新應為 success
    await _insert_log(session_factory, schema="DS", table="GAT_FILE", status="failed")
    await _insert_log(session_factory, schema="DS", table="GAT_FILE", status="success")

    resp = await client.get("/api/v1/schedules", params={"schema": "DS"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    # data 禁直接為 array:必為 {items, total, ...}
    assert isinstance(body["data"], dict)
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["table_name"] == "GAT_FILE"
    assert item["business_name"] == "訂單"
    assert item["is_enabled"] is True
    assert item["cron_expr"] == "0 2 * * *"
    assert item["schedule_uid"] is not None
    assert item["last_run_status"] == "success"


async def test_list_tables_view_requires_schema_422(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.get("/api/v1/schedules")
    assert resp.status_code == 422


async def test_list_tables_view_no_schedule_null_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="NAKED")
    resp = await client.get("/api/v1/schedules", params={"schema": "DS"})
    item = resp.json()["data"]["items"][0]
    assert item["table_name"] == "NAKED"
    # 無排程 → schedule 欄位為 null
    assert item["schedule_uid"] is None
    assert item["is_enabled"] is None
    assert item["cron_expr"] is None
    assert item["last_run_status"] is None


async def test_list_tables_view_filters_and_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="orders", business_name="訂單")
    await _snapshot(session_factory, schema="DS", table="items", business_name="品項")
    await _snapshot(session_factory, schema="DS", table="logs", business_name="日誌")
    await _bind_schedule(session_factory, schema="DS", table="orders", is_enabled=True)
    await _bind_schedule(session_factory, schema="DS", table="items", is_enabled=False)
    await _insert_log(session_factory, schema="DS", table="orders", status="success")
    await _insert_log(session_factory, schema="DS", table="items", status="failed")

    async def _names(**params: object) -> set[str]:
        body = (
            await client.get(
                "/api/v1/schedules", params={"schema": "DS", **params}
            )
        ).json()
        return {i["table_name"] for i in body["data"]["items"]}

    assert await _names(enabled="enabled") == {"orders"}
    assert await _names(enabled="disabled") == {"items", "logs"}
    assert await _names(last_result="success") == {"orders"}
    assert await _names(last_result="failed") == {"items"}
    assert await _names(last_result="never") == {"logs"}
    assert await _names(keyword="訂單") == {"orders"}
    assert await _names(keyword="item") == {"items"}

    # 分頁:3 張表,page_size=2
    body = (
        await client.get(
            "/api/v1/schedules", params={"schema": "DS", "page": 1, "page_size": 2}
        )
    ).json()
    assert body["data"]["total"] == 3
    assert len(body["data"]["items"]) == 2
    body2 = (
        await client.get(
            "/api/v1/schedules", params={"schema": "DS", "page": 2, "page_size": 2}
        )
    ).json()
    assert len(body2["data"]["items"]) == 1


# ── schema 摘要 ─────────────────────────────────────────────────────────
async def test_schema_summaries(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="a")
    await _snapshot(session_factory, schema="DS", table="b")
    await _snapshot(session_factory, schema="sales", table="c")
    await _bind_schedule(session_factory, schema="DS", table="a", is_enabled=True)
    await _bind_schedule(session_factory, schema="DS", table="b", is_enabled=False)

    resp = await client.get("/api/v1/schedules/schemas")
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    assert isinstance(body["data"], dict)
    items = body["data"]["items"]
    assert items == [
        {"schema_name": "DS", "table_count": 2, "enabled_count": 1},
        {"schema_name": "sales", "table_count": 1, "enabled_count": 0},
    ]


# ── 更新(cron / 啟停 / 描述)────────────────────────────────────────────
async def test_patch_updates_cron_and_description(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="GAT_FILE")
    uid = await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    resp = await client.patch(
        f"/api/v1/schedules/{uid}",
        json={"cron_expr": "30 4 * * 1-5", "description": "改過", "is_enabled": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["cron_expr"] == "30 4 * * 1-5"
    assert data["description"] == "改過"
    assert data["is_enabled"] is False
    assert data["job_desc"] == "增量同步全部表"


async def test_patch_ignores_binding_change(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """禁改綁定表:即使帶 source_schema / source_table,綁定不變(欄位被忽略)。"""
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="GAT_FILE", business_name="訂單")
    uid = await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    resp = await client.patch(
        f"/api/v1/schedules/{uid}",
        json={"source_schema": "HACK", "source_table": "OTHER", "description": "x"},
    )
    assert resp.status_code == 200
    # 綁定未變:GAT_FILE 仍掛此排程
    item = (
        await client.get("/api/v1/schedules", params={"schema": "DS"})
    ).json()["data"]["items"][0]
    assert item["table_name"] == "GAT_FILE"
    assert item["schedule_uid"] == uid
    assert item["description"] == "x"


async def test_patch_invalid_cron_400(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="GAT_FILE")
    uid = await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    resp = await client.patch(f"/api/v1/schedules/{uid}", json={"cron_expr": "bad"})
    assert resp.status_code == 400
    _assert_shell(resp.json(), success=False, response_code=400)


async def test_patch_not_found_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.patch(
        f"/api/v1/schedules/{uuid4()}", json={"description": "x"}
    )
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)


# ── 啟用 / 停用 ─────────────────────────────────────────────────────────
async def test_disable_and_enable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="GAT_FILE")
    uid = await _bind_schedule(session_factory, schema="DS", table="GAT_FILE")
    resp = await client.post(f"/api/v1/schedules/{uid}/disable")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False
    resp = await client.post(f"/api/v1/schedules/{uid}/enable")
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is True


# ── 批次啟停 ────────────────────────────────────────────────────────────
async def test_batch_enabled_affected_count(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="a")
    await _snapshot(session_factory, schema="DS", table="b")
    await _snapshot(session_factory, schema="sales", table="c")
    await _bind_schedule(session_factory, schema="DS", table="a", is_enabled=True)
    await _bind_schedule(session_factory, schema="DS", table="b", is_enabled=True)
    await _bind_schedule(session_factory, schema="sales", table="c", is_enabled=True)

    # 停用 DS 2 張 → 影響 2
    resp = await client.post(
        "/api/v1/schedules/batch-enabled", json={"enabled": False, "schema": "DS"}
    )
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    assert body["data"]["affected"] == 2

    # 再次停用 DS → 無變更
    resp = await client.post(
        "/api/v1/schedules/batch-enabled", json={"enabled": False, "schema": "DS"}
    )
    assert resp.json()["data"]["affected"] == 0

    # 全部 schema 啟用 → DS 2 張變更(sales 本已啟用不變)= 2
    resp = await client.post(
        "/api/v1/schedules/batch-enabled", json={"enabled": True}
    )
    assert resp.json()["data"]["affected"] == 2


async def test_batch_enabled_respects_filters(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """僅啟停符合篩選(schema + 關鍵字)者;不命中的表不受影響。"""
    await _login_as(client, session_factory, "admin")
    await _snapshot(session_factory, schema="DS", table="orders", business_name="訂單")
    await _snapshot(session_factory, schema="DS", table="items", business_name="品項")
    await _bind_schedule(session_factory, schema="DS", table="orders", is_enabled=False)
    await _bind_schedule(session_factory, schema="DS", table="items", is_enabled=False)

    # 關鍵字「訂單」僅命中 orders → 啟用 1 筆
    resp = await client.post(
        "/api/v1/schedules/batch-enabled",
        json={"enabled": True, "schema": "DS", "filter_keyword": "訂單"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["affected"] == 1

    # 篩選 filter_enabled=disabled + 表名關鍵字「items」→ 啟用剩下的 items = 1
    resp = await client.post(
        "/api/v1/schedules/batch-enabled",
        json={
            "enabled": True,
            "schema": "DS",
            "filter_enabled": "disabled",
            "filter_keyword": "items",
        },
    )
    assert resp.json()["data"]["affected"] == 1

    # 兩張皆已啟用,再帶篩選啟用 → 0
    resp = await client.post(
        "/api/v1/schedules/batch-enabled",
        json={"enabled": True, "schema": "DS", "filter_keyword": "訂單"},
    )
    assert resp.json()["data"]["affected"] == 0
