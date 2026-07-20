"""task-007 B2 測試:rds_table_meta 加 module_code(GAT_FILE.GAT06)+ datasets API 模組篩選。

涵蓋 Acceptance:
- dictionary.fetch_table_modules 單元測試(繁優先缺退簡、字典缺 graceful 回空)
- SnapshotService._collect_from_rds 實際串接 fetch_table_modules(不 monkeypatch 整個
  _collect_from_rds,驗證真正的組裝邏輯)
- refresh 落地 module_code(含字典缺對應為 null)
- list_tables `module` 等值篩選 + Redis cache key 依 module 區分
- datasets API `?module=` 查詢參數與回應 `module_code` 欄位
"""

import asyncio
import os

# app.core.db 於 import 時即建立 engine → 先注入測試 env 再 import app 模組
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

from collections.abc import AsyncIterator, Mapping, Sequence  # noqa: E402
from typing import Any  # noqa: E402
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
from app.core import redis as cache  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.etl import introspect  # noqa: E402
from app.etl.dictionary import fetch_table_modules  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Dataset, RdsTableMeta  # noqa: E402
from app.repositories.rds_table_meta_repo import (  # noqa: E402
    UNCLASSIFIED_MODULE_SENTINEL,
    RdsTableMetaRepository,
)
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services.snapshot_service import (  # noqa: E402
    SnapshotService,
    TableFilters,
    _CollectedTable,
)


# ── fixtures(對齊 test_snapshot_service.py 既有模式)────────────────────
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
                # 跨 run 複用既有 rds_table_meta 表時,補齊 v1.5.0 欄位(非破壞性)
                await conn.execute(
                    text("ALTER TABLE rds_table_meta ADD COLUMN IF NOT EXISTS module_code TEXT")
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
    async with db_engine.begin() as conn:
        await conn.execute(text("DELETE FROM rds_table_meta"))
        await conn.execute(text("DELETE FROM users"))


@pytest.fixture(autouse=True)
def _reset_cache() -> None:
    """每測試重置 redis 記憶體 fake(避免跨測試髒讀)。"""
    cache._client = None


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


def _fake_tables() -> list[_CollectedTable]:
    """兩表帶不同模組代碼、一表字典缺對應(module_code=None)。"""
    return [
        _CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12, "GL"),
        _CollectedTable("DS", "GAT_FILE", "資料檔名檔", 3, 900, "SYS"),
        _CollectedTable("DS", "BBB_FILE", None, 2, 4, None),
    ]


def _patch_collect(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_collect(self: SnapshotService, dataset_value: str) -> list[_CollectedTable]:
        return _fake_tables()

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect)


async def _refresh(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        result = await SnapshotService(session).refresh("source", uuid4())
        await session.commit()
    return result.table_count


# ── A. dictionary.fetch_table_modules 單元測試(fake AsyncConnection)──────
class _FakeResult:
    def __init__(self, rows: Sequence[Any]) -> None:
        self._rows = list(rows)

    def first(self) -> Any | None:
        return self._rows[0] if self._rows else None

    def mappings(self) -> _FakeResult:
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeModuleConn:
    """依 SQL 內容與 bind params 回傳預置列(僅 GAT06 模組查詢 + 表存在性檢查)。"""

    def __init__(
        self,
        *,
        table_exists: bool = True,
        modules: Mapping[str, Mapping[str, str]] | None = None,
    ) -> None:
        self._exists = table_exists
        self._modules = modules or {}

    async def execute(
        self, sql: Any, params: Mapping[str, Any] | None = None
    ) -> _FakeResult:
        s = str(sql)
        bound = dict(params or {})
        if "information_schema.tables" in s:
            return _FakeResult([(1,)] if self._exists else [])
        if "GAT06" in s:
            lang = str(bound["lang"])
            wanted = set(bound["tables"])
            src = self._modules.get(lang, {})
            rows = [{"k": k, "v": v} for k, v in src.items() if k in wanted]
            return _FakeResult(rows)
        raise AssertionError(f"未預期 SQL:{s}")


async def test_fetch_table_modules_prefers_zh_tw() -> None:
    conn = _FakeModuleConn(modules={"0": {"aaa_file": "GL"}, "2": {"aaa_file": "gl-cn"}})
    result = await fetch_table_modules(conn, ["AAA_FILE"])
    assert result == {"aaa_file": "GL"}


async def test_fetch_table_modules_falls_back_zh_cn() -> None:
    conn = _FakeModuleConn(modules={"2": {"aaa_file": "GL"}})
    result = await fetch_table_modules(conn, ["AAA_FILE"])
    assert result == {"aaa_file": "GL"}


async def test_fetch_table_modules_missing_dict_returns_empty_no_raise() -> None:
    conn = _FakeModuleConn(table_exists=False)
    assert await fetch_table_modules(conn, ["AAA_FILE"]) == {}


async def test_fetch_table_modules_empty_tables_returns_empty() -> None:
    conn = _FakeModuleConn()
    assert await fetch_table_modules(conn, []) == {}


async def test_fetch_table_modules_no_match_excluded() -> None:
    conn = _FakeModuleConn(modules={"0": {"bbb_file": "GL"}})
    assert await fetch_table_modules(conn, ["AAA_FILE"]) == {}


# ── B. _collect_from_rds 實際組裝邏輯(不 monkeypatch 整個方法)──────────
class _FakeIntrospectConn:
    async def __aenter__(self) -> _FakeIntrospectConn:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeIntrospectEngine:
    def connect(self) -> _FakeIntrospectConn:
        return _FakeIntrospectConn()


async def test_collect_from_rds_merges_module_code(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """驗證 SnapshotService._collect_from_rds 真正呼叫 fetch_table_modules 並組裝
    module_code(而非僅測試被 monkeypatch 取代的整個方法)。"""
    monkeypatch.setattr(introspect, "get_engine", lambda dataset: _FakeIntrospectEngine())

    async def fake_snapshot_tables(conn: object) -> list[dict[str, int | str]]:
        return [
            {"schema": "DS", "name": "AAA_FILE", "column_count": 5, "row_count": 12},
            {"schema": "DS", "name": "BBB_FILE", "column_count": 2, "row_count": 4},
        ]

    async def fake_comments(conn: object, tables: Sequence[str]) -> dict[str, str]:
        return {"aaa_file": "帳別參數檔"}

    async def fake_modules(conn: object, tables: Sequence[str]) -> dict[str, str]:
        return {"aaa_file": "GL"}  # BBB_FILE 字典缺對應

    monkeypatch.setattr(introspect, "snapshot_tables", fake_snapshot_tables)
    monkeypatch.setattr(
        "app.services.snapshot_service.fetch_table_comments", fake_comments
    )
    monkeypatch.setattr(
        "app.services.snapshot_service.fetch_table_modules", fake_modules
    )

    async with session_factory() as session:
        collected = await SnapshotService(session)._collect_from_rds("source")

    by_name = {c.table_name: c for c in collected}
    assert by_name["AAA_FILE"].module_code == "GL"
    assert by_name["AAA_FILE"].business_name == "帳別參數檔"
    assert by_name["BBB_FILE"].module_code is None  # 字典缺對應 → null


# ── C. refresh 落地 module_code(含字典缺對應為 null)────────────────────
async def test_refresh_persists_module_code(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    assert await _refresh(session_factory) == 3
    async with session_factory() as session:
        rows = (await session.execute(select(RdsTableMeta))).scalars().all()
        by_name = {r.table_name: r.module_code for r in rows}
        assert by_name["AAA_FILE"] == "GL"
        assert by_name["GAT_FILE"] == "SYS"
        assert by_name["BBB_FILE"] is None  # 字典缺對應 → null


async def test_refresh_is_idempotent_updates_module_code(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """重複 refresh 時模組代碼隨最新快照更新(非僅首次寫入)。"""
    _patch_collect(monkeypatch)
    await _refresh(session_factory)

    async def fake_collect_updated(
        self: SnapshotService, dataset_value: str
    ) -> list[_CollectedTable]:
        return [_CollectedTable("DS", "AAA_FILE", "帳別參數檔", 5, 12, "AR")]

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect_updated)
    await _refresh(session_factory)

    async with session_factory() as session:
        aaa = (
            await session.execute(
                select(RdsTableMeta).where(RdsTableMeta.table_name == "AAA_FILE")
            )
        ).scalar_one()
        assert aaa.module_code == "AR"


# ── D. list_tables:module 等值篩選 ──────────────────────────────────────
async def test_list_tables_module_filter(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        svc = SnapshotService(session)
        gl_only = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(rows="all", module="GL"),
        )
        assert {i.name for i in gl_only.items} == {"AAA_FILE"}
        assert gl_only.items[0].module_code == "GL"

        sys_only = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(rows="all", module="SYS"),
        )
        assert {i.name for i in sys_only.items} == {"GAT_FILE"}

        no_match = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(rows="all", module="NOPE"),
        )
        assert no_match.total == 0

        unfiltered = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(rows="all"),
        )
        assert unfiltered.total == 3  # module="" 不篩


# ── D2. list_tables:module=__unclassified__ 篩 module_code IS NULL(AD-117)───
async def test_list_tables_unclassified_sentinel_filters_null_module(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`module=UNCLASSIFIED_MODULE_SENTINEL` 篩 module_code IS NULL,分頁/total 正確反映
    (前端 sentinel `__unclassified__` 與後端此常值對齊)。"""
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        svc = SnapshotService(session)
        unclassified_only = await svc.list_tables(
            "source", "DS", page=1, page_size=50,
            filters=TableFilters(rows="all", module=UNCLASSIFIED_MODULE_SENTINEL),
        )
        assert {i.name for i in unclassified_only.items} == {"BBB_FILE"}
        assert unclassified_only.total == 1
        assert unclassified_only.items[0].module_code is None


# ── E. cache key 依 module 區分 ──────────────────────────────────────────
async def test_list_tables_cache_key_differs_by_module(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_collect(monkeypatch)
    await _refresh(session_factory)

    calls = {"n": 0}
    original = RdsTableMetaRepository.list_by_schema

    async def counting(
        self: RdsTableMetaRepository, *args: object, **kwargs: object
    ) -> tuple[list[RdsTableMeta], int]:
        calls["n"] += 1
        return await original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(RdsTableMetaRepository, "list_by_schema", counting)

    async with session_factory() as session:
        svc = SnapshotService(session)
        gl = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(module="GL")
        )
        sys_ = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(module="SYS")
        )
        # 相同 module 再查一次應命中 cache,不再打 repo
        gl_again = await svc.list_tables(
            "source", "DS", page=1, page_size=50, filters=TableFilters(module="GL")
        )

    assert calls["n"] == 2  # 兩種不同 module 各打一次 repo(cache key 有區分)
    assert {i.name for i in gl.items} == {"AAA_FILE"}
    assert {i.name for i in sys_.items} == {"GAT_FILE"}
    assert gl.total == gl_again.total


# ── F. datasets API:?module= 查詢參數 + 回應 module_code ─────────────────
async def test_api_list_tables_filters_by_module_and_returns_module_code(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    _patch_collect(monkeypatch)
    refresh_resp = await client.post("/api/v1/datasets/source/snapshot/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text

    all_resp = await client.get(
        "/api/v1/datasets/source/tables", params={"schema": "DS", "rows": "all"}
    )
    assert all_resp.status_code == 200, all_resp.text
    all_items = all_resp.json()["data"]["items"]
    by_name = {i["name"]: i["module_code"] for i in all_items}
    assert by_name == {"AAA_FILE": "GL", "GAT_FILE": "SYS", "BBB_FILE": None}

    filtered_resp = await client.get(
        "/api/v1/datasets/source/tables",
        params={"schema": "DS", "rows": "all", "module": "GL"},
    )
    assert filtered_resp.status_code == 200, filtered_resp.text
    filtered_items = filtered_resp.json()["data"]["items"]
    assert [i["name"] for i in filtered_items] == ["AAA_FILE"]


# ── G. repo.list_distinct_modules:整 schema 聚合(AD-115)─────────────────
async def test_repo_list_distinct_modules_aggregates_whole_schema(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    """distinct 模組清單來自整個 schema(非單頁),含未分類旗標。"""
    _patch_collect(monkeypatch)
    await _refresh(session_factory)
    async with session_factory() as session:
        codes, has_unclassified = await RdsTableMetaRepository(session).list_distinct_modules(
            Dataset.SOURCE, "DS"
        )
    assert codes == ["GL", "SYS"]  # 排序;不含 None
    assert has_unclassified is True  # BBB_FILE module_code=None


async def test_repo_list_distinct_modules_no_unclassified_when_all_classified(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_collect(self: SnapshotService, dataset_value: str) -> list[_CollectedTable]:
        return [_CollectedTable("DS", "AAA_FILE", None, 1, 1, "GL")]

    monkeypatch.setattr(SnapshotService, "_collect_from_rds", fake_collect)
    await _refresh(session_factory)
    async with session_factory() as session:
        codes, has_unclassified = await RdsTableMetaRepository(session).list_distinct_modules(
            Dataset.SOURCE, "DS"
        )
    assert codes == ["GL"]
    assert has_unclassified is False


# ── H. datasets API:distinct 模組清單端點(AD-115)──────────────────────
async def test_api_list_schema_modules_returns_distinct_codes_and_unclassified_flag(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    _patch_collect(monkeypatch)
    refresh_resp = await client.post("/api/v1/datasets/source/snapshot/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text

    resp = await client.get("/api/v1/datasets/source/schemas/DS/modules")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data == {"modules": ["GL", "SYS"], "has_unclassified": True}


async def test_api_list_schema_modules_requires_login_and_admin(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    resp = await client.get("/api/v1/datasets/source/schemas/DS/modules")
    assert resp.status_code == 401

    await _login_as(client, session_factory, "member")
    resp = await client.get("/api/v1/datasets/source/schemas/DS/modules")
    assert resp.status_code == 403


# ── I. datasets API:?module=__unclassified__ 端到端(AD-117)──────────────
async def test_api_list_tables_unclassified_sentinel_end_to_end(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await _login_as(client, session_factory, "admin")
    _patch_collect(monkeypatch)
    refresh_resp = await client.post("/api/v1/datasets/source/snapshot/refresh")
    assert refresh_resp.status_code == 200, refresh_resp.text

    resp = await client.get(
        "/api/v1/datasets/source/tables",
        params={"schema": "DS", "rows": "all", "module": UNCLASSIFIED_MODULE_SENTINEL},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert [i["name"] for i in body["items"]] == ["BBB_FILE"]
    assert body["total"] == 1
