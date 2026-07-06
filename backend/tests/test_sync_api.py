"""task-004 同步觸發 API 測試(真實 PostgreSQL 測試 DB;mirror 以 fake 注入,不打 RDS)。

涵蓋:單表 / 全量同步 enqueue(InMemoryBroker 就地執行)回 202 + ApiResponse 外殼與 run uid、
run 落 DB 狀態 success 且逐表 log 齊全、來源快照 last_synced_at / row_count 更新、
viewer 呼叫同步一律 403。
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
from app.core import db as core_db  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.rds_table_meta import Dataset, RdsTableMeta  # noqa: E402
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.worker import tasks  # noqa: E402


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
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM etl_run_logs"))
        await conn.execute(text("DELETE FROM etl_runs"))
        await conn.execute(text("DELETE FROM rds_table_meta"))
        await conn.execute(text("DELETE FROM audit_logs"))
        await conn.execute(text("DELETE FROM users"))


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine() -> AsyncIterator[None]:
    # mirror_sync(taskiq 就地執行)走全域 engine 連線池;
    # pytest-asyncio 每測試換 event loop,不釋放會跨 loop 重用連線而失敗
    yield
    await core_db.engine.dispose()


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


# ── fake mirror(不打 RDS)────────────────────────────────────────────────
class FakeMirror:
    """結構相容 MirrorEngine:list_source_tables / mirror_table / dispose。"""

    def __init__(self, tables: list[tuple[str, str]], *, written: int = 3) -> None:
        self._tables = tables
        self._written = written
        self.mirrored: list[tuple[str, str]] = []
        self.disposed = False

    async def list_source_tables(self) -> list[tuple[str, str]]:
        return list(self._tables)

    async def mirror_table(
        self, schema: str, table: str, *, batch_size: int = 1000
    ) -> int:
        self.mirrored.append((schema, table))
        return self._written

    async def dispose(self) -> None:
        self.disposed = True


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
    assert set(body.keys()) == {"success", "data", "detail", "response_code"}
    assert body["success"] is success
    assert body["response_code"] == response_code


async def _seed_source_meta(
    session_factory: async_sessionmaker[AsyncSession], schema: str, table: str
) -> None:
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            RdsTableMeta(
                uid=uuid4(),
                dataset=Dataset.SOURCE,
                schema_name=schema,
                table_name=table,
                column_count=5,
                row_count=0,
                snapshot_at=datetime(2026, 7, 3, 2, 0, 0),
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()


async def _get_source_meta(
    session_factory: async_sessionmaker[AsyncSession], schema: str, table: str
) -> RdsTableMeta:
    async with session_factory() as session:
        return (
            await session.execute(
                select(RdsTableMeta).where(
                    RdsTableMeta.dataset == Dataset.SOURCE,
                    RdsTableMeta.schema_name == schema,
                    RdsTableMeta.table_name == table,
                )
            )
        ).scalar_one()


# ── 權限:viewer 一律 403 ───────────────────────────────────────────────
async def test_viewer_sync_forbidden_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "viewer")
    resp = await client.post(
        "/api/v1/sync/table", json={"schema": "DS", "table": "AAA_FILE"}
    )
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)
    resp_all = await client.post("/api/v1/sync/all")
    assert resp_all.status_code == 403
    _assert_shell(resp_all.json(), success=False, response_code=403)


async def test_sync_requires_login_401(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/sync/table", json={"schema": "DS", "table": "AAA_FILE"}
    )
    assert resp.status_code == 401
    _assert_shell(resp.json(), success=False, response_code=401)


# ── 單表同步:enqueue → run success + 快照更新 ─────────────────────────
async def test_sync_table_enqueues_and_updates_meta(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_source_meta(session_factory, "DS", "AAA_FILE")
    fake = FakeMirror([("DS", "AAA_FILE")], written=7)
    monkeypatch.setattr(tasks, "make_mirror", lambda: fake)

    resp = await client.post(
        "/api/v1/sync/table", json={"schema": "DS", "table": "AAA_FILE"}
    )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    _assert_shell(body, success=True, response_code=202)
    data = body["data"]
    assert data["task_id"]
    assert data["scope"] == "table"
    run_uid = data["run_uid"]
    assert run_uid is not None
    # fake mirror 確有被呼叫該表
    assert fake.mirrored == [("DS", "AAA_FILE")]

    # run 落 DB:manual 觸發、1 表成功
    detail = (await client.get(f"/api/v1/runs/{run_uid}")).json()["data"]
    assert detail["trigger_type"] == "manual"
    assert detail["status"] == "success"
    assert (detail["total_tables"], detail["success_tables"]) == (1, 1)
    # 逐表 log:AAA_FILE success + 寫入筆數
    logs = (await client.get(f"/api/v1/runs/{run_uid}/logs")).json()["data"]
    assert logs["total"] == 1
    log = logs["items"][0]
    assert (log["source_schema"], log["source_table"]) == ("DS", "AAA_FILE")
    assert log["status"] == "success"
    assert log["row_count"] == 7

    # 來源快照:last_synced_at / last_transformed_at 非空,row_count 取實寫筆數
    meta = await _get_source_meta(session_factory, "DS", "AAA_FILE")
    assert meta.last_synced_at is not None
    assert meta.last_transformed_at is not None
    assert meta.row_count == 7


# ── 全量同步:enqueue → run success(DS 優先由 mirror.list_source_tables 保證)──
async def test_sync_all_enqueues(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    fake = FakeMirror([("DS", "GAT_FILE"), ("M2201", "MOCK_FILE")], written=2)
    monkeypatch.setattr(tasks, "make_mirror", lambda: fake)

    resp = await client.post("/api/v1/sync/all")
    assert resp.status_code == 202, resp.text
    body = resp.json()
    _assert_shell(body, success=True, response_code=202)
    data = body["data"]
    assert data["scope"] == "all"
    run_uid = data["run_uid"]
    assert run_uid is not None
    # 全量取 fake 清單全部表
    assert fake.mirrored == [("DS", "GAT_FILE"), ("M2201", "MOCK_FILE")]

    detail = (await client.get(f"/api/v1/runs/{run_uid}")).json()["data"]
    assert detail["status"] == "success"
    assert (detail["total_tables"], detail["success_tables"]) == (2, 2)


# ── 篩選同步:只鏡像符合條件的表；無符合 → 不觸發 ────────────────────────
async def test_sync_filtered_enqueues_matching_only(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_source_meta(session_factory, "DS", "AAA_FILE")  # row_count=0(空表)
    actor = uuid4()
    async with session_factory() as session:
        session.add(
            RdsTableMeta(
                uid=uuid4(),
                dataset=Dataset.SOURCE,
                schema_name="DS",
                table_name="GAT_FILE",
                column_count=3,
                row_count=900,
                snapshot_at=datetime(2026, 7, 3, 2, 0, 0),
                created_by=actor,
                updated_by=actor,
            )
        )
        await session.commit()
    fake = FakeMirror([], written=5)
    monkeypatch.setattr(tasks, "make_mirror", lambda: fake)

    # rows=nonempty → 只有 GAT_FILE 符合
    resp = await client.post(
        "/api/v1/sync/filtered", json={"schema": "DS", "rows": "nonempty"}
    )
    assert resp.status_code == 202, resp.text
    data = resp.json()["data"]
    assert data["scope"] == "filtered"
    assert data["matched"] == 1
    assert fake.mirrored == [("DS", "GAT_FILE")]

    # 關鍵字無符合 → matched=0、task_id 空、mirror 完全不被呼叫(不建空 run)
    fake_none = FakeMirror([], written=5)
    monkeypatch.setattr(tasks, "make_mirror", lambda: fake_none)
    resp0 = await client.post(
        "/api/v1/sync/filtered",
        json={"schema": "DS", "keyword": "NO_SUCH_TABLE"},
    )
    assert resp0.status_code == 202, resp0.text
    data0 = resp0.json()["data"]
    assert data0["matched"] == 0
    assert data0["task_id"] == ""
    assert fake_none.mirrored == []
