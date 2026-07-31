"""語意映射管理 API 測試(v1.5.1 task-004;真實本地 PostgreSQL 測試 DB 假扮目標 RDS)。

涵蓋:列表分頁 / 表名精準 / 狀態 / 關鍵字篩選、PATCH 更新(含 404 / 422 驗證)、
confirm-table 整表轉態(冪等)、sync-views 派工 202 / 進行中 409(AD-122/120)、
semantic_apply task 持鎖略過、寫入類稽核(AD-123)、member 403。
對齊 test_view_generator.py 模式:AWS_RDS_* 指向本地測試 DB,不觸碰真正 AWS RDS;
teardown 僅清資料(DELETE)不刪結構(禁 DROP)。
"""

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
from app.core import db as core_db  # noqa: E402
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
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.worker import tasks  # noqa: E402

_BASE_PATH = "/api/v1/semantic-mappings"


# ── fixtures(對齊 test_snapshot_refresh_progress.py 慣例)──────────────
@pytest.fixture(scope="session", autouse=True)
def _prepare_test_db() -> None:
    """建立測試 DB(不存在才建)+ metadata 建 schema + erp_metadata 語意表 + client_setting
    權限表(english_name 改名的下游引用檢核要查它);全為冪等 DDL,不做任何 DROP。"""

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
async def _clean_tables(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM erp_metadata.semantic_mappings"))
        await conn.execute(text("DELETE FROM semantic_mappings"))  # 自有 DB 本地副本
        await conn.execute(text("DELETE FROM users"))
        await conn.execute(text("DELETE FROM audit_logs"))  # 稽核斷言決定性(AD-123)
        for table in reversed(CLIENT_SETTING_TABLES):  # 引用檢核用的權限列(禁 DROP)
            await conn.execute(text(f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table}"))


@pytest_asyncio.fixture(autouse=True)
async def _dispose_global_engine() -> AsyncIterator[None]:
    # semantic_apply(taskiq 就地執行)自開 AsyncSessionLocal → 走全域 engine 連線池;
    # pytest-asyncio 每測試換 event loop,不釋放會跨 loop 重用連線而失敗
    yield
    await core_db.engine.dispose()


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    cache._client = None


@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效。每測試後 dispose + 清快取(對齊 test_data_query_api.py)。"""
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


async def _login_as(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role: str,
) -> None:
    username = f"{role}-user"
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


async def _seed_rows(db_engine: AsyncEngine) -> None:
    """兩表五列樣本:BMA_FILE(表層級+兩欄,confirmed 混 draft)、GAT06(表層級+一欄)。"""
    rows = [
        ("BMA_FILE", "", "bma_file", "品號主檔", "confirmed"),
        ("BMA_FILE", "BMA001", "part_number", "品號", "confirmed"),
        ("BMA_FILE", "BMA002", "part_name", "品名", "draft"),
        ("GAT06", "", "voucher_type_config", "單別設定", "draft"),
        ("GAT06", "GAT061", "voucher_type", "單別", "draft"),
    ]
    async with db_engine.begin() as conn:
        for t, c, e, z, s in rows:
            await conn.execute(
                text(
                    "INSERT INTO erp_metadata.semantic_mappings"
                    " (table_name, column_name, english_name, zh_name, status)"
                    " VALUES (:t, :c, :e, :z, :s)"
                ),
                {"t": t, "c": c, "e": e, "z": z, "s": s},
            )


async def _seed_operation_scope(
    db_engine: AsyncEngine, table_name: str, column_name: str
) -> None:
    """在 RDS `client_setting` 種一筆作業範圍項,模擬「該英文名已被權限設定引用」。

    授權以英文名純字串儲存、與語意映射無 FK(AD-154)→ 改名檢核只能靠反查這三張 items 表。
    """
    async with db_engine.begin() as conn:
        service_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.services (code, name)"
                    " VALUES (:code, :name) RETURNING pid"
                ),
                {"code": f"svc_{uuid4().hex[:8]}", "name": "引用測試服務"},
            )
        ).scalar_one()
        operation_pid = (
            await conn.execute(
                text(
                    f"INSERT INTO {CLIENT_SETTING_SCHEMA}.operations (service_pid, name)"
                    " VALUES (:s, :n) RETURNING pid"
                ),
                {"s": service_pid, "n": f"O-{uuid4().hex[:6]}"},
            )
        ).scalar_one()
        await conn.execute(
            text(
                f"INSERT INTO {CLIENT_SETTING_SCHEMA}.operation_items"
                " (operation_pid, table_name, column_name) VALUES (:o, :t, :c)"
            ),
            {"o": operation_pid, "t": table_name, "c": column_name},
        )


# ── 列表 / 篩選 ─────────────────────────────────────────────────────────
async def test_list_mappings_pagination_and_filters(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.get(_BASE_PATH, params={"page": 1, "page_size": 3})
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["total"] == 5
    assert len(data["items"]) == 3

    resp = await client.get(_BASE_PATH, params={"table": "BMA_FILE"})
    assert {i["table_name"] for i in resp.json()["data"]["items"]} == {"BMA_FILE"}
    assert resp.json()["data"]["total"] == 3

    resp = await client.get(_BASE_PATH, params={"status": "draft"})
    assert resp.json()["data"]["total"] == 3

    resp = await client.get(_BASE_PATH, params={"keyword": "part_"})
    names = {i["english_name"] for i in resp.json()["data"]["items"]}
    assert names == {"part_number", "part_name"}

    # 中英皆可:表名子字串 / 中文名子字串皆可命中
    resp = await client.get(_BASE_PATH, params={"keyword": "GAT06"})
    assert resp.json()["data"]["total"] == 2
    resp = await client.get(_BASE_PATH, params={"keyword": "品號"})
    names = {i["english_name"] for i in resp.json()["data"]["items"]}
    assert names == {"bma_file", "part_number"}


async def test_list_tables_with_status_counts(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.get(f"{_BASE_PATH}/tables")
    assert resp.status_code == 200, resp.text
    by_name = {i["table_name"]: i for i in resp.json()["data"]["items"]}
    assert by_name["BMA_FILE"]["confirmed_count"] == 2
    assert by_name["BMA_FILE"]["draft_count"] == 1
    assert by_name["GAT06"]["draft_count"] == 2
    # 表層級中英文名帶出(供前端表名 combobox 中英搜尋)
    assert by_name["BMA_FILE"]["zh_name"] == "品號主檔"
    assert by_name["BMA_FILE"]["english_name"] == "bma_file"


# ── PATCH 更新 ──────────────────────────────────────────────────────────
async def test_patch_updates_fields_and_actor(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA002",
            "english_name": "part_display_name",
            "status": "confirmed",
        },
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["data"]
    assert item["english_name"] == "part_display_name"
    assert item["status"] == "confirmed"
    assert item["updated_by"] is not None

    # 稽核事件(AD-123):action + 定位 + 異動欄位入 detail
    async with db_engine.connect() as conn:
        detail = (
            await conn.execute(
                text(
                    "SELECT detail FROM audit_logs"
                    " WHERE action = 'semantic_mapping.update'"
                )
            )
        ).scalar_one()
    assert "BMA_FILE.BMA002" in str(detail)
    assert "english_name" in str(detail)
    assert "status" in str(detail)


async def test_patch_missing_row_returns_404(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.patch(
        _BASE_PATH,
        json={"table_name": "NOPE", "column_name": "X", "english_name": "abc"},
    )
    assert resp.status_code == 404, resp.text


async def test_patch_invalid_english_name_returns_422(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.patch(
        _BASE_PATH,
        json={"table_name": "BMA_FILE", "column_name": "BMA002", "english_name": "Bad Name"},
    )
    assert resp.status_code == 422, resp.text


async def test_patch_without_updatable_fields_returns_422(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.patch(
        _BASE_PATH, json={"table_name": "BMA_FILE", "column_name": "BMA002"}
    )
    assert resp.status_code == 422, resp.text


# ── english_name 改名防護(v1.6.1 fixed AD-154 + AD-150)────────────────
async def test_patch_english_name_blocked_when_referenced_by_grant(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    """confirmed 列的英文名已被權限設定引用 → 409(改名會靜默作廢 / 錯接既有授權)。"""
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    # 表層級英文名 bma_file 被授權引用(`*` 代表全欄位,不指名欄位)
    await _seed_operation_scope(db_engine, "bma_file", "*")

    blocked = await client.patch(
        _BASE_PATH,
        json={"table_name": "BMA_FILE", "column_name": "", "english_name": "renamed_file"},
    )
    assert blocked.status_code == 409, blocked.text
    assert "權限設定引用" in str(blocked.json()["detail"])

    # 未被引用的欄位仍可改名(引用檢核只擋真正有下游授權的名字)
    allowed = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA001",
            "english_name": "part_no",
        },
    )
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["data"]["english_name"] == "part_no"


async def test_patch_column_english_name_blocked_when_referenced_by_grant(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    """欄位級改名以 (表英文名, 欄位英文名) 反查引用 → 命中即 409。"""
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    await _seed_operation_scope(db_engine, "bma_file", "part_number")

    blocked = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA001",
            "english_name": "part_no",
        },
    )
    assert blocked.status_code == 409, blocked.text

    # 同表另一欄未被引用 → 放行(且該列為 draft,本就不可能被授權)
    allowed = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA002",
            "english_name": "part_desc",
        },
    )
    assert allowed.status_code == 200, allowed.text


async def test_patch_english_name_rejects_duplicates(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    """AD-150:表層級英文名全域唯一、欄位英文名同表唯一,撞名一律 409。"""
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    # 表層級:改成另一張表已用的表英文名
    resp = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "",
            "english_name": "voucher_type_config",
        },
    )
    assert resp.status_code == 409, resp.text

    # 欄位級:改成同表另一欄已用的英文名
    resp = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "BMA_FILE",
            "column_name": "BMA002",
            "english_name": "part_number",
        },
    )
    assert resp.status_code == 409, resp.text

    # 跨表同名欄位合法(對外 key 是 表.欄位)
    resp = await client.patch(
        _BASE_PATH,
        json={
            "table_name": "GAT06",
            "column_name": "GAT061",
            "english_name": "part_number",
        },
    )
    assert resp.status_code == 200, resp.text


# ── confirm-table ───────────────────────────────────────────────────────
async def test_confirm_table_idempotent(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.post(
        f"{_BASE_PATH}/confirm-table", json={"table_name": "GAT06"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["affected"] == 2

    resp = await client.post(
        f"{_BASE_PATH}/confirm-table", json={"table_name": "GAT06"}
    )
    assert resp.json()["data"]["affected"] == 0

    resp = await client.get(_BASE_PATH, params={"table": "GAT06", "status": "draft"})
    assert resp.json()["data"]["total"] == 0

    # 稽核事件(AD-123):兩次呼叫各一列,detail 帶 affected
    async with db_engine.connect() as conn:
        details = (
            await conn.execute(
                text(
                    "SELECT detail FROM audit_logs"
                    " WHERE action = 'semantic_mapping.confirm_table' ORDER BY pid"
                )
            )
        ).scalars().all()
    assert len(details) == 2
    assert "GAT06" in str(details[0])
    assert "affected=2" in str(details[0])
    assert "affected=0" in str(details[1])


# ── sync-views(AD-122:派工 worker,202 受理)────────────────────────────
async def test_sync_views_returns_202_and_replaces_replica(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)

    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 202, resp.text
    assert resp.json()["data"] == {"queued": True}

    # InMemoryBroker await_inplace:派工當下已就地執行完畢 → 副本已整表重灌
    async with db_engine.connect() as conn:
        replica_total = (
            await conn.execute(text("SELECT count(*) FROM semantic_mappings"))
        ).scalar_one()
    assert int(replica_total) == 5

    # 稽核事件已寫 audit_logs(AD-123)
    async with db_engine.connect() as conn:
        audit_total = (
            await conn.execute(
                text(
                    "SELECT count(*) FROM audit_logs"
                    " WHERE action = 'semantic_mapping.sync_views'"
                )
            )
        ).scalar_one()
    assert int(audit_total) == 1

    # 前次已結束(鎖已釋放)→ 可再次派工
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 202, resp.text


async def test_sync_views_conflict_when_apply_in_progress(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    # 模擬另一 process(worker)持鎖進行中 → 派工前預檢 409
    await cache.cache_set(tasks.APPLY_LOCK_KEY, "1", ttl_seconds=60)
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 409, resp.text
    await cache.cache_delete(tasks.APPLY_LOCK_KEY)

    # 進度 key 存在(執行中)亦視為進行中
    await tasks._report_apply_progress("views", 1, 10)
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 409, resp.text


# ── semantic_apply task:持鎖略過(AD-120 跨 process 互斥)────────────────
async def test_semantic_apply_task_skips_when_locked(
    db_engine: AsyncEngine,
) -> None:
    await _seed_rows(db_engine)
    assert await tasks.acquire_apply_lock() is True
    try:
        task = await tasks.semantic_apply.kiq()
        result = await task.wait_result(timeout=10)
        assert not result.is_err, result.error
        assert result.return_value == {"skipped": "locked"}
    finally:
        await tasks.release_apply_lock()
    # 持鎖期間未執行副本重灌
    async with db_engine.connect() as conn:
        replica_total = (
            await conn.execute(text("SELECT count(*) FROM semantic_mappings"))
        ).scalar_one()
    assert int(replica_total) == 0


# ── 套用進度(聚合進度端點 /progress 的 apply 欄位)──────────────────────
async def test_apply_progress_idle_and_running(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "admin")
    resp = await client.get("/api/v1/progress")
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["apply"]["active"] is False

    await tasks._report_apply_progress("views", 120, 1284)
    resp = await client.get("/api/v1/progress")
    data = resp.json()["data"]["apply"]
    assert data == {"active": True, "phase": "views", "done": 120, "total": 1284}


async def test_sync_views_clears_apply_progress_key(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    db_engine: AsyncEngine,
) -> None:
    await _login_as(client, session_factory, "admin")
    await _seed_rows(db_engine)
    resp = await client.post(f"{_BASE_PATH}/sync-views")
    assert resp.status_code == 202, resp.text
    # 套用結束後進度 key 已清 → 閒置 inactive
    resp = await client.get("/api/v1/progress")
    assert resp.json()["data"]["apply"]["active"] is False


# ── 權限 ────────────────────────────────────────────────────────────────
async def test_member_forbidden(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _login_as(client, session_factory, "member")
    for method, path, kwargs in [
        ("GET", _BASE_PATH, {}),
        ("GET", f"{_BASE_PATH}/tables", {}),
        (
            "PATCH",
            _BASE_PATH,
            {"json": {"table_name": "X", "column_name": "", "english_name": "abc"}},
        ),
        ("POST", f"{_BASE_PATH}/confirm-table", {"json": {"table_name": "X"}}),
        ("POST", f"{_BASE_PATH}/sync-views", {}),
    ]:
        resp = await client.request(method, path, **kwargs)
        assert resp.status_code == 403, f"{method} {path}: {resp.text}"
