"""task-007 依表檢視 coverage API 測試(真實 PostgreSQL 測試 DB)。

涵蓋:未登入 401 / viewer 讀 OK 但 PATCH 403 / admin PATCH OK、
/schemas 概況與 has_enabled_schedule(有 / 無啟用排程)、
列表 included 判定、last_run_status 反映最新 log、
inclusion / last_result / keyword 篩選、分頁 total、
PATCH exclusion 切換與 DB 實際反映(禁物理刪除)。
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
from app.models import (  # noqa: E402
    Dataset,
    EtlRun,
    EtlRunLog,
    RdsTableMeta,
    Schedule,
)
from app.repositories.user_repo import UserRepository  # noqa: E402

_ACTOR_UID = uuid4()


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


# ── 測試資料塞入 ─────────────────────────────────────────────────────────
def _meta(
    schema: str,
    table: str,
    *,
    business_name: str | None = None,
    sync_excluded: bool = False,
    row_count: int = 10,
    last_synced_at: datetime | None = None,
) -> RdsTableMeta:
    return RdsTableMeta(
        uid=uuid4(),
        dataset=Dataset.SOURCE,
        schema_name=schema,
        table_name=table,
        business_name=business_name,
        column_count=3,
        row_count=row_count,
        sync_excluded=sync_excluded,
        last_synced_at=last_synced_at,
        created_by=_ACTOR_UID,
        updated_by=_ACTOR_UID,
    )


async def _seed_source_data(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    enabled_schedule: bool = True,
) -> dict[str, UUID]:
    """塞 3 張 public 表 + 1 張 sales 表;t_alpha 最新 success、t_beta failed、t_gamma 無 log。"""
    async with session_factory() as session:
        alpha = _meta(
            "public",
            "t_alpha",
            business_name="甲表",
            row_count=100,
            last_synced_at=datetime(2026, 1, 1, 12, 0, 0),
        )
        beta = _meta("public", "t_beta", business_name="測試乙表", sync_excluded=False)
        gamma = _meta("public", "t_gamma", row_count=0)
        sales = _meta("sales", "s_one", sync_excluded=True)
        session.add_all([alpha, beta, gamma, sales])

        if enabled_schedule:
            session.add(
                Schedule(
                    uid=uuid4(),
                    name="夜間增量",
                    cron_expr="0 2 * * *",
                    is_enabled=True,
                    created_by=_ACTOR_UID,
                    updated_by=_ACTOR_UID,
                )
            )

        run = EtlRun(
            uid=uuid4(),
            trigger_type="manual",
            status="partial",
            created_by=_ACTOR_UID,
            updated_by=_ACTOR_UID,
        )
        session.add(run)
        await session.flush()

        # t_alpha:先 failed(舊)後 success(新)→ 最新應為 success
        session.add_all(
            [
                EtlRunLog(
                    uid=uuid4(),
                    etl_run_pid=run.pid,
                    source_schema="public",
                    source_table="t_alpha",
                    status="failed",
                    created_by=_ACTOR_UID,
                    updated_by=_ACTOR_UID,
                ),
                EtlRunLog(
                    uid=uuid4(),
                    etl_run_pid=run.pid,
                    source_schema="public",
                    source_table="t_alpha",
                    status="success",
                    created_by=_ACTOR_UID,
                    updated_by=_ACTOR_UID,
                ),
                EtlRunLog(
                    uid=uuid4(),
                    etl_run_pid=run.pid,
                    source_schema="public",
                    source_table="t_beta",
                    status="failed",
                    created_by=_ACTOR_UID,
                    updated_by=_ACTOR_UID,
                ),
            ]
        )
        await session.commit()
        return {
            "alpha": alpha.uid,
            "beta": beta.uid,
            "gamma": gamma.uid,
            "sales": sales.uid,
        }


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_requires_login_401(client: AsyncClient) -> None:
    for path in (
        "/api/v1/schedule-coverage?schema=public",
        "/api/v1/schedule-coverage/schemas",
    ):
        resp = await client.get(path)
        assert resp.status_code == 401, path
        _assert_shell(resp.json(), success=False, response_code=401)


async def test_viewer_read_ok_patch_403(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    uids = await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    assert (
        await client.get("/api/v1/schedule-coverage/schemas")
    ).status_code == 200
    assert (
        await client.get("/api/v1/schedule-coverage", params={"schema": "public"})
    ).status_code == 200
    resp = await client.patch(
        f"/api/v1/schedule-coverage/tables/{uids['alpha']}/exclusion",
        json={"excluded": True},
    )
    assert resp.status_code == 403
    _assert_shell(resp.json(), success=False, response_code=403)


# ── /schemas 概況 ────────────────────────────────────────────────────────
async def test_schemas_summary_with_enabled_schedule(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory, enabled_schedule=True)
    await _login_as(client, session_factory, "viewer")
    body = (await client.get("/api/v1/schedule-coverage/schemas")).json()
    _assert_shell(body, success=True, response_code=200)
    data = body["data"]
    assert data["has_enabled_schedule"] is True
    assert len(data["schedules"]) == 1
    assert data["schedules"][0]["name"] == "夜間增量"
    assert data["schedules"][0]["cron_expr"] == "0 2 * * *"
    summary = {item["schema_name"]: item for item in data["items"]}
    assert summary["public"]["table_count"] == 3
    assert summary["public"]["excluded_count"] == 0
    assert summary["sales"]["table_count"] == 1
    assert summary["sales"]["excluded_count"] == 1


async def test_schemas_summary_without_enabled_schedule(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory, enabled_schedule=False)
    await _login_as(client, session_factory, "viewer")
    body = (await client.get("/api/v1/schedule-coverage/schemas")).json()
    data = body["data"]
    assert data["has_enabled_schedule"] is False
    assert data["schedules"] == []


# ── 列表 / included / last_run_status ────────────────────────────────────
async def test_list_included_and_last_status(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory, enabled_schedule=True)
    await _login_as(client, session_factory, "viewer")
    body = (
        await client.get("/api/v1/schedule-coverage", params={"schema": "public"})
    ).json()
    _assert_shell(body, success=True, response_code=200)
    data = body["data"]
    assert data["total"] == 3
    assert data["has_enabled_schedule"] is True
    by_table = {item["table_name"]: item for item in data["items"]}
    # 有啟用排程且未排除 → included=true
    assert by_table["t_alpha"]["included"] is True
    # 最新 log 為 success(舊 failed 被覆蓋)
    assert by_table["t_alpha"]["last_run_status"] == "success"
    assert by_table["t_alpha"]["last_synced_at"] is not None
    assert by_table["t_beta"]["last_run_status"] == "failed"
    # 無 log → None
    assert by_table["t_gamma"]["last_run_status"] is None
    assert by_table["t_gamma"]["included"] is True


async def test_list_included_false_without_schedule(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory, enabled_schedule=False)
    await _login_as(client, session_factory, "viewer")
    data = (
        await client.get("/api/v1/schedule-coverage", params={"schema": "public"})
    ).json()["data"]
    # 系統無啟用排程 → 全表未涵蓋
    assert all(item["included"] is False for item in data["items"])
    assert data["has_enabled_schedule"] is False


# ── 篩選 ────────────────────────────────────────────────────────────────
async def test_filter_inclusion_excluded(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    data = (
        await client.get(
            "/api/v1/schedule-coverage",
            params={"schema": "sales", "inclusion": "excluded"},
        )
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["table_name"] == "s_one"
    assert data["items"][0]["sync_excluded"] is True


async def test_filter_last_result_failed(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    data = (
        await client.get(
            "/api/v1/schedule-coverage",
            params={"schema": "public", "last_result": "failed"},
        )
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["table_name"] == "t_beta"


async def test_filter_last_result_never(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    data = (
        await client.get(
            "/api/v1/schedule-coverage",
            params={"schema": "public", "last_result": "never"},
        )
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["table_name"] == "t_gamma"


async def test_filter_keyword(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    # 業務名關鍵字命中 t_beta(business_name=測試乙表)
    data = (
        await client.get(
            "/api/v1/schedule-coverage",
            params={"schema": "public", "keyword": "乙表"},
        )
    ).json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["table_name"] == "t_beta"


async def test_list_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_source_data(session_factory)
    await _login_as(client, session_factory, "viewer")
    resp = await client.get(
        "/api/v1/schedule-coverage",
        params={"schema": "public", "page": 1, "page_size": 2},
    )
    data = resp.json()["data"]
    assert isinstance(data, dict)
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    resp2 = await client.get(
        "/api/v1/schedule-coverage",
        params={"schema": "public", "page": 2, "page_size": 2},
    )
    assert len(resp2.json()["data"]["items"]) == 1


# ── PATCH 排除切換 ───────────────────────────────────────────────────────
async def test_admin_toggle_exclusion(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    uids = await _seed_source_data(session_factory, enabled_schedule=True)
    await _login_as(client, session_factory, "admin")
    alpha_uid = uids["alpha"]

    # 排除 → sync_excluded=true、included=false
    resp = await client.patch(
        f"/api/v1/schedule-coverage/tables/{alpha_uid}/exclusion",
        json={"excluded": True},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sync_excluded"] is True
    assert data["included"] is False
    assert data["last_run_status"] == "success"

    # DB 實際反映(禁物理刪除,仍為同一列)
    async with session_factory() as session:
        row = (
            await session.execute(
                select(RdsTableMeta).where(RdsTableMeta.uid == alpha_uid)
            )
        ).scalar_one()
        assert row.sync_excluded is True
        assert row.is_deleted is False

    # 再納入 → 恢復 included=true
    resp = await client.patch(
        f"/api/v1/schedule-coverage/tables/{alpha_uid}/exclusion",
        json={"excluded": False},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sync_excluded"] is False
    assert data["included"] is True


async def test_toggle_exclusion_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.patch(
        f"/api/v1/schedule-coverage/tables/{uuid4()}/exclusion",
        json={"excluded": True},
    )
    assert resp.status_code == 404
    _assert_shell(resp.json(), success=False, response_code=404)
