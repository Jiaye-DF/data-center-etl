"""執行紀錄 / 逐表詳細 log API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:run 清單分頁(最新在前)/ 狀態與觸發方式過濾、單 run 明細、
單 run 逐表 log 欄位齊全(筆數 / 耗時 / 狀態 / 錯誤含 stack trace)與狀態過濾、
viewer 可讀取清單 / 明細 / log。

v1.3.1:config-ETL 手動觸發(POST /runs/trigger)已隨 task-004/005 移除,對應測試刪除。
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
from app.models import EtlRun, EtlRunLog, Schedule  # noqa: E402
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
        await conn.execute(text("DELETE FROM schedules"))
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


def _assert_shell(body: dict[str, object], *, success: bool, response_code: int) -> None:
    """斷言 ApiResponse 外殼:success / data / detail / response_code。"""
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


async def _seed_schedule(
    session_factory: async_sessionmaker[AsyncSession], name: str = "夜間排程"
) -> tuple[int, str]:
    actor = uuid4()
    async with session_factory() as session:
        schedule = Schedule(
            uid=uuid4(),
            name=name,
            cron_expr="0 2 * * *",
            is_enabled=True,
            created_by=actor,
            updated_by=actor,
        )
        session.add(schedule)
        await session.flush()
        pid = schedule.pid
        uid = str(schedule.uid)
        await session.commit()
    return pid, uid


async def _seed_run(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    trigger_type: str = "manual",
    status: str = "success",
    schedule_pid: int | None = None,
    total_tables: int = 0,
    success_tables: int = 0,
    failed_tables: int = 0,
    error_message: str | None = None,
) -> str:
    actor = uuid4()
    async with session_factory() as session:
        run = EtlRun(
            uid=uuid4(),
            trigger_type=trigger_type,
            schedule_pid=schedule_pid,
            status=status,
            started_at=datetime(2026, 7, 3, 2, 0, 0),
            finished_at=datetime(2026, 7, 3, 2, 5, 0),
            total_tables=total_tables,
            success_tables=success_tables,
            failed_tables=failed_tables,
            error_message=error_message,
            created_by=actor,
            updated_by=actor,
        )
        session.add(run)
        await session.flush()
        uid = str(run.uid)
        await session.commit()
    return uid


async def _seed_log(
    session_factory: async_sessionmaker[AsyncSession],
    run_uid: str,
    *,
    source_table: str,
    status: str,
    row_count: int | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
    error_stack: str | None = None,
) -> None:
    actor = uuid4()
    async with session_factory() as session:
        run = (
            await session.execute(select(EtlRun).where(EtlRun.uid == UUID(run_uid)))
        ).scalar_one()
        session.add(
            EtlRunLog(
                uid=uuid4(),
                etl_run_pid=run.pid,
                source_schema="DS",
                source_table=source_table,
                status=status,
                row_count=row_count,
                duration_ms=duration_ms,
                started_at=datetime(2026, 7, 3, 2, 0, 0),
                finished_at=datetime(2026, 7, 3, 2, 1, 0),
                error_message=error_message,
                error_stack=error_stack,
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


# ── 未登入 / viewer 權限 ────────────────────────────────────────────────
async def test_list_requires_login_401(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


async def test_viewer_read_runs_forbidden_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """RBAC 收緊(task-003):runs 全端點 admin-only,viewer 一律 403。"""
    await _login_as(client, session_factory, "viewer")
    run_uid = await _seed_run(session_factory)
    list_resp = await client.get("/api/v1/runs")
    assert list_resp.status_code == 403
    _assert_shell(list_resp.json(), success=False, response_code=403)
    assert (await client.get(f"/api/v1/runs/{run_uid}")).status_code == 403
    assert (await client.get(f"/api/v1/runs/{run_uid}/logs")).status_code == 403


async def test_admin_read_runs_unchanged_200(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    run_uid = await _seed_run(session_factory)
    list_resp = await client.get("/api/v1/runs")
    assert list_resp.status_code == 200
    _assert_shell(list_resp.json(), success=True, response_code=200)
    assert (await client.get(f"/api/v1/runs/{run_uid}")).status_code == 200
    assert (await client.get(f"/api/v1/runs/{run_uid}/logs")).status_code == 200


# ── run 清單 ────────────────────────────────────────────────────────────
async def test_list_runs_pagination_latest_first(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    uid_old = await _seed_run(session_factory, status="failed")
    uid_mid = await _seed_run(session_factory, status="success")
    uid_new = await _seed_run(session_factory, status="running")
    resp = await client.get("/api/v1/runs", params={"page": 1, "page_size": 2})
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    # data 禁直接為 array:必為 {items, total, ...};最新在前
    assert isinstance(body["data"], dict)
    assert body["data"]["total"] == 3
    assert [item["uid"] for item in body["data"]["items"]] == [uid_new, uid_mid]
    resp2 = await client.get("/api/v1/runs", params={"page": 2, "page_size": 2})
    assert [item["uid"] for item in resp2.json()["data"]["items"]] == [uid_old]


async def test_list_runs_filter_by_status_and_trigger_type(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    schedule_pid, schedule_uid = await _seed_schedule(session_factory)
    uid_failed = await _seed_run(
        session_factory,
        trigger_type="schedule",
        status="failed",
        schedule_pid=schedule_pid,
        error_message="1 表失敗",
    )
    uid_manual = await _seed_run(session_factory, trigger_type="manual", status="success")
    # 狀態過濾
    body = (await client.get("/api/v1/runs", params={"status": "failed"})).json()
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["uid"] == uid_failed
    assert item["error_message"] == "1 表失敗"
    # 觸發方式過濾 + 來源排程參照(uid / 名稱,禁曝內部主鍵)
    body = (await client.get("/api/v1/runs", params={"trigger_type": "schedule"})).json()
    assert [i["uid"] for i in body["data"]["items"]] == [uid_failed]
    assert body["data"]["items"][0]["schedule_uid"] == schedule_uid
    assert body["data"]["items"][0]["schedule_name"] == "夜間排程"
    body = (await client.get("/api/v1/runs", params={"trigger_type": "manual"})).json()
    assert [i["uid"] for i in body["data"]["items"]] == [uid_manual]
    assert body["data"]["items"][0]["schedule_uid"] is None
    # 非法狀態值 → FastAPI schema 驗證 422
    resp = await client.get("/api/v1/runs", params={"status": "bogus"})
    assert resp.status_code == 422


# ── 單 run 明細 ─────────────────────────────────────────────────────────
async def test_get_run_detail_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    # partial 狀態已移除(scan AD-004):任一表失敗即整輪 failed
    run_uid = await _seed_run(
        session_factory,
        status="failed",
        total_tables=3,
        success_tables=2,
        failed_tables=1,
        error_message="1 表失敗",
    )
    resp = await client.get(f"/api/v1/runs/{run_uid}")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["uid"] == run_uid
    assert data["trigger_type"] == "manual"
    assert data["status"] == "failed"
    assert data["started_at"] is not None and data["finished_at"] is not None
    assert (data["total_tables"], data["success_tables"], data["failed_tables"]) == (3, 2, 1)
    assert data["error_message"] == "1 表失敗"


async def test_get_run_not_found_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.get(f"/api/v1/runs/{uuid4()}")
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)
    resp = await client.get(f"/api/v1/runs/{uuid4()}/logs")
    assert resp.status_code == 404


# ── 單 run 逐表詳細 log ─────────────────────────────────────────────────
async def test_run_logs_fields_complete(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    run_uid = await _seed_run(
        session_factory, status="failed", total_tables=2, success_tables=1, failed_tables=1
    )
    await _seed_log(
        session_factory,
        run_uid,
        source_table="GAT_FILE",
        status="success",
        row_count=120,
        duration_ms=1500,
    )
    await _seed_log(
        session_factory,
        run_uid,
        source_table="GAQ_FILE",
        status="failed",
        duration_ms=300,
        error_message="來源連線逾時",
        error_stack="Traceback (most recent call last): ...",
    )
    resp = await client.get(f"/api/v1/runs/{run_uid}/logs")
    assert resp.status_code == 200
    body = resp.json()
    _assert_shell(body, success=True, response_code=200)
    assert body["data"]["total"] == 2
    ok, bad = body["data"]["items"]
    # 逐表欄位齊全:表名 / 筆數 / 耗時 / 狀態 / 起訖
    assert ok["source_schema"] == "DS"
    assert ok["source_table"] == "GAT_FILE"
    assert ok["status"] == "success"
    assert ok["row_count"] == 120
    assert ok["duration_ms"] == 1500
    assert ok["started_at"] is not None and ok["finished_at"] is not None
    assert ok["error_message"] is None and ok["error_stack"] is None
    # 失敗表:錯誤明細含 stack trace
    assert bad["source_table"] == "GAQ_FILE"
    assert bad["status"] == "failed"
    assert bad["row_count"] is None
    assert bad["error_message"] == "來源連線逾時"
    assert "Traceback" in bad["error_stack"]


async def test_run_logs_filter_by_status_and_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    run_uid = await _seed_run(session_factory, status="failed", total_tables=3)
    await _seed_log(session_factory, run_uid, source_table="T1", status="success", row_count=1)
    await _seed_log(session_factory, run_uid, source_table="T2", status="failed")
    await _seed_log(session_factory, run_uid, source_table="T3", status="success", row_count=2)
    # 依狀態過濾
    body = (
        await client.get(f"/api/v1/runs/{run_uid}/logs", params={"status": "failed"})
    ).json()
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["source_table"] == "T2"
    # 分頁
    body = (
        await client.get(f"/api/v1/runs/{run_uid}/logs", params={"page": 2, "page_size": 2})
    ).json()
    assert body["data"]["total"] == 3
    assert [i["source_table"] for i in body["data"]["items"]] == ["T3"]


# ── 手動觸發端點已移除(v1.3.1):POST /runs/trigger 不存在 ────────────────
async def test_trigger_endpoint_removed(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.post("/api/v1/runs/trigger", json={"etl_table_uid": None})
    # 端點不存在 → 405(/{uid} 路由不吃 POST)或 404
    assert resp.status_code in (404, 405)
