"""最終可見欄位預覽測試(v1.6.1 task-007)。

權限資料連真實本地 PostgreSQL 測試 DB 的 `client_setting` schema(模擬 RDS),
Client 本體連同一測試 DB 的自有表;Redis 以記憶體替身取代(寫法沿用 test_permission_cache.py)。

情境涵蓋 Arch「三情境對照」:聯集 ∩ 作業範圍、default-closed、過期臨時權限排除、
超範圍授權不生效、`*` 展開、快取命中與失效、非 admin 403 / 不存在 client 404。
清理只刪本檔自建資料(以 `ACTOR_UID` 標記),與併行測試共用測試 DB 亦互不干擾;**禁 DROP**。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建 engine;client_setting 連線沿用 AWS_RDS_*(見 reader.py),
# 一律指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"
TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}"
)

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.exceptions import AppError  # noqa: E402
from app.core.security import hash_password_async  # noqa: E402
from app.etl import introspect  # noqa: E402
from app.etl.client_setting_schema import ensure_client_setting_schema  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.client_setting import (  # noqa: E402
    ACTION_EDIT,
    ACTION_READ,
    ALL_COLUMNS,
    CLIENT_SETTING_SCHEMA,
    CLIENT_SETTING_TABLES,
)
from app.models.user import User  # noqa: E402
from app.repositories.api_client_repo import ApiClientRepository  # noqa: E402
from app.repositories.client_setting_repo import (  # noqa: E402
    ClientSettingRepository,
    PermissionItem,
    ScopeItem,
    client_setting_session,
)
from app.repositories.user_repo import UserRepository  # noqa: E402
from app.services import permission_cache  # noqa: E402
from app.services.effective_permission_service import (  # noqa: E402
    EffectivePermissionService,
)
from app.utils.datetime import db_now  # noqa: E402

# 本檔自建資料一律掛此 actor,清理只刪自己的列(與併行測試共用測試 DB 不互相清空)
ACTOR_UID = uuid4()
_CLIENTS_URL = "/api/v1/api-clients"
_FAKE_UID = "00000000-0000-0000-0000-0000000000ff"
_USERNAME_PREFIX = "eff-preview"
_PASSWORD = "preview-password-123"

_schema_ready = False


def _uniq(prefix: str) -> str:
    """唯一名稱(權限表多為全域唯一鍵,避免與併行測試撞鍵)。"""
    return f"{prefix}-{uuid4().hex[:8]}"


class FakeRedis:
    """記憶體 Redis 替身(本層用到的 get / set / delete / scan_iter 子集)。

    `fail_on` 內的指令名會拋 `ConnectionError`,用來模擬 Redis 故障。
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}
        self.fail_on: set[str] = set()

    def _guard(self, command: str) -> None:
        if command in self.fail_on:
            raise ConnectionError(f"redis {command} 連線中斷")

    async def get(self, name: str) -> str | None:
        self._guard("get")
        return self.store.get(name)

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        self._guard("set")
        self.store[name] = value
        if ex is not None:
            self.ttl[name] = ex
        return True

    async def delete(self, *names: str) -> int:
        self._guard("delete")
        removed = 0
        for name in names:
            if self.store.pop(name, None) is not None:
                self.ttl.pop(name, None)
                removed += 1
        return removed

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        self._guard("scan_iter")
        prefix = match.removesuffix("*")
        for name in list(self.store):
            if name.startswith(prefix):
                yield name


# ── fixtures ────────────────────────────────────────────────────────────
@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效,故每測試後 dispose + 清快取。"""
    yield
    for engine in list(introspect._ENGINES.values()):
        await engine.dispose()
    introspect._ENGINES.clear()


@pytest.fixture(autouse=True)
def redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """記憶體 Redis 替身(每測試一份,狀態天然隔離)。"""
    fake = FakeRedis()
    monkeypatch.setattr(permission_cache, "get_redis", lambda: fake)
    return fake


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture(autouse=True)
async def _clean_own_db(db_engine: AsyncEngine) -> AsyncIterator[None]:
    yield
    async with db_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM api_client_users WHERE created_by = :actor"),
            {"actor": str(ACTOR_UID)},
        )
        await conn.execute(
            text("DELETE FROM users WHERE username LIKE :pattern"),
            {"pattern": f"{_USERNAME_PREFIX}-%"},
        )


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """指向測試 DB `client_setting` schema 的 Session;離開時只刪本檔建立的列。"""
    engine = introspect.get_engine("target")
    global _schema_ready
    if not _schema_ready:
        async with engine.begin() as conn:
            await ensure_client_setting_schema(conn)
        _schema_ready = True
    try:
        async with client_setting_session() as db:
            yield db
    finally:
        async with engine.begin() as conn:
            for table in reversed(CLIENT_SETTING_TABLES):
                await conn.execute(
                    text(
                        f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table} "
                        "WHERE created_by = :actor"
                    ),
                    {"actor": str(ACTOR_UID)},
                )


@pytest_asyncio.fixture
async def repo(session: AsyncSession) -> ClientSettingRepository:
    return ClientSettingRepository(session)


@pytest_asyncio.fixture
async def app(session_factory: async_sessionmaker[AsyncSession]) -> FastAPI:
    fastapi_app = create_app()

    async def _override_get_db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    return fastapi_app


@pytest_asyncio.fixture
async def http_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    # base_url 用 https:cookie 為 secure=True,走 http 不會被 client 回送
    async with AsyncClient(transport=transport, base_url="https://testserver") as ac:
        yield ac


# ── 資料建構小工具 ───────────────────────────────────────────────────────
async def _create_user(
    session_factory: async_sessionmaker[AsyncSession], username: str, role: str
) -> User:
    async with session_factory() as db:
        user = await UserRepository(db).create(
            username=username,
            password_hash=await hash_password_async(_PASSWORD),
            role=role,
        )
        await db.commit()
        return user


async def _login(http_client: AsyncClient, username: str) -> None:
    resp = await http_client.post(
        "/api/v1/auth/login", json={"username": username, "password": _PASSWORD}
    )
    assert resp.status_code == 200, resp.text


async def _create_client_row(session_factory: async_sessionmaker[AsyncSession]) -> UUID:
    async with session_factory() as db:
        row = await ApiClientRepository(db).create(
            client_id=f"dc_{uuid4().hex[:24]}",
            name=_uniq("預覽測試 Client"),
            actor_uid=ACTOR_UID,
        )
        await db.commit()
        return row.uid


async def _preview(
    session_factory: async_sessionmaker[AsyncSession], client_uid: UUID
) -> dict[str, dict[str, dict[str, str]]]:
    """呼叫預覽並轉成 `{作業名: {表: {欄位: 動作}}}`(等價 Arch 範例形狀)。"""
    async with session_factory() as db:
        result = await EffectivePermissionService(db).preview(client_uid)
    return {row.operation_name: row.tables for row in result.operations}


async def _make_arch_operation(
    repo: ClientSettingRepository, *, name: str = "O1"
) -> tuple[int, int]:
    """Arch 範例作業:範圍 T1(C11·C12)、T2(C21·C22)、T3(C31·C32)。"""
    service = await repo.create_service(code=_uniq("erp"), name="ERP", actor_uid=ACTOR_UID)
    operation = await repo.create_operation(
        service_pid=service.pid, name=name, actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        operation.pid,
        [
            ScopeItem("T1", "C11"),
            ScopeItem("T1", "C12"),
            ScopeItem("T2", "C21"),
            ScopeItem("T2", "C22"),
            ScopeItem("T3", "C31"),
            ScopeItem("T3", "C32"),
        ],
        actor_uid=ACTOR_UID,
    )
    return service.pid, operation.pid


async def _assign_profile(
    repo: ClientSettingRepository,
    client_uid: UUID,
    *,
    operation_pids: list[int],
    items: dict[int, list[PermissionItem]],
) -> int:
    """建角色權限設定檔 → Role → 指派給 Client;回傳角色權限設定檔 pid。"""
    profile = await repo.create_permission_profile(name=_uniq("P1"), actor_uid=ACTOR_UID)
    await repo.replace_profile_operations(profile.pid, operation_pids, actor_uid=ACTOR_UID)
    for operation_pid, permission_items in items.items():
        await repo.replace_profile_items(
            profile.pid, operation_pid, permission_items, actor_uid=ACTOR_UID
        )
    role = await repo.create_role(
        permission_profile_pid=profile.pid, name=_uniq("R1"), actor_uid=ACTOR_UID
    )
    await repo.assign_client_role(client_uid, role.pid, actor_uid=ACTOR_UID)
    return profile.pid


async def _bind_exception_set(
    repo: ClientSettingRepository,
    client_uid: UUID,
    *,
    operation_pid: int,
    items: list[PermissionItem],
    expires_at: datetime | None = None,
) -> int:
    """建臨時權限組(勾作業 + 授權項)並綁給 Client;回傳臨時權限組 pid。"""
    exception_set = await repo.create_exception_set(name=_uniq("X"), actor_uid=ACTOR_UID)
    await repo.replace_exception_operations(
        exception_set.pid, [operation_pid], actor_uid=ACTOR_UID
    )
    if items:
        await repo.replace_exception_items(
            exception_set.pid, operation_pid, items, actor_uid=ACTOR_UID
        )
    await repo.bind_client_exception_set(
        client_uid, exception_set.pid, expires_at=expires_at, actor_uid=ACTOR_UID
    )
    return exception_set.pid


# ── 情境一:聯集 ∩ 作業範圍(Arch 範例)──────────────────────────────────
async def test_arch_example_intersects_scope_and_merges_actions(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """P1 於 O1 授 C11:read、C21:read+edit、C31:read → 只回三欄且 C21 取較高動作 edit。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={
            operation_pid: [
                PermissionItem("T1", "C11", ACTION_READ),
                PermissionItem("T2", "C21", ACTION_READ),
                PermissionItem("T2", "C21", ACTION_EDIT),
                PermissionItem("T3", "C31", ACTION_READ),
            ]
        },
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {
            "T1": {"C11": ACTION_READ},
            "T2": {"C21": ACTION_EDIT},
            "T3": {"C31": ACTION_READ},
        }
    }


async def test_preview_carries_role_and_exception_context(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """預覽同時交代權限來源:Role / 角色權限設定檔名稱、納入計算的臨時權限組與效期(naive UTC+8)。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={operation_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    expires_at = db_now() + timedelta(days=1)
    await _bind_exception_set(
        repo, client_uid, operation_pid=operation_pid, items=[], expires_at=expires_at
    )
    await session.commit()

    async with session_factory() as db:
        result = await EffectivePermissionService(db).preview(client_uid)

    assert result.client_uid == client_uid
    assert result.role is not None
    assert result.role.permission_profile_name is not None
    assert len(result.exception_sets) == 1
    assert result.exception_sets[0].expires_at == expires_at
    assert expires_at.tzinfo is None
    assert result.operations[0].service_code.startswith("erp-")


# ── 情境二:default-closed ───────────────────────────────────────────────
async def test_operation_without_items_is_empty_not_absent(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """勾了作業但沒給任何表欄位授權 → 該作業出現但為空(作業開門 ≠ 欄位授權)。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(repo, client_uid, operation_pids=[operation_pid], items={})
    await session.commit()

    assert await _preview(session_factory, client_uid) == {"O1": {}}


async def test_no_role_and_no_exception_returns_empty(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """無 Role 且無臨時權限 → 空結構(default-closed 的極端情形)。"""
    client_uid = await _create_client_row(session_factory)
    await _make_arch_operation(repo)
    await session.commit()

    async with session_factory() as db:
        result = await EffectivePermissionService(db).preview(client_uid)

    assert result.role is None
    assert result.exception_sets == []
    assert result.operations == []


async def test_items_of_unopened_operation_do_not_grant(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """授權項所屬作業未被同一來源勾選 → 不生效(開門與授權須同一來源配對)。"""
    client_uid = await _create_client_row(session_factory)
    service_pid, opened_pid = await _make_arch_operation(repo)
    other = await repo.create_operation(
        service_pid=service_pid, name="O2", actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        other.pid, [ScopeItem("T9", "C91")], actor_uid=ACTOR_UID
    )
    # 角色權限設定檔只勾 O1,卻在 O2 底下留有授權項(異常資料);臨時權限組只開 O2 的門、不給授權
    profile_pid = await _assign_profile(
        repo,
        client_uid,
        operation_pids=[opened_pid],
        items={opened_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    await repo.replace_profile_items(
        profile_pid,
        other.pid,
        [PermissionItem("T9", "C91", ACTION_EDIT)],
        actor_uid=ACTOR_UID,
    )
    await _bind_exception_set(repo, client_uid, operation_pid=other.pid, items=[])
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {"T1": {"C11": ACTION_READ}},
        "O2": {},
    }


# ── 情境三:超範圍 / 萬用欄位 ───────────────────────────────────────────
async def test_grants_outside_operation_scope_are_dropped(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """超出作業範圍的表與欄位一律不生效(∩ 上限);交集為空的表整張省略。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={
            operation_pid: [
                PermissionItem("T1", "C11", ACTION_READ),
                PermissionItem("T1", "C19", ACTION_EDIT),  # 範圍外欄位
                PermissionItem("T9", "C91", ACTION_EDIT),  # 範圍外的表
            ]
        },
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {"T1": {"C11": ACTION_READ}}
    }


async def test_wildcard_column_expands_within_scope(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`*` 展開為作業範圍內該表全欄位;範圍本身為 `*` 時原樣保留 `*`。"""
    client_uid = await _create_client_row(session_factory)
    service = await repo.create_service(code=_uniq("erp"), name="ERP", actor_uid=ACTOR_UID)
    operation = await repo.create_operation(
        service_pid=service.pid, name="O1", actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        operation.pid,
        [ScopeItem("T1", "C11"), ScopeItem("T1", "C12"), ScopeItem("T2", ALL_COLUMNS)],
        actor_uid=ACTOR_UID,
    )
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation.pid],
        items={
            operation.pid: [
                PermissionItem("T1", ALL_COLUMNS, ACTION_READ),
                PermissionItem("T1", "C12", ACTION_EDIT),
                PermissionItem("T2", ALL_COLUMNS, ACTION_EDIT),
            ]
        },
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {
            "T1": {"C11": ACTION_READ, "C12": ACTION_EDIT},
            "T2": {ALL_COLUMNS: ACTION_EDIT},
        }
    }


async def test_concrete_grant_passes_wildcard_scope(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """作業範圍為 `*`(全欄位)時,具體欄位授權視為在範圍內。"""
    client_uid = await _create_client_row(session_factory)
    service = await repo.create_service(code=_uniq("erp"), name="ERP", actor_uid=ACTOR_UID)
    operation = await repo.create_operation(
        service_pid=service.pid, name="O1", actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        operation.pid, [ScopeItem("T1", ALL_COLUMNS)], actor_uid=ACTOR_UID
    )
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation.pid],
        items={operation.pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {"T1": {"C11": ACTION_READ}}
    }


async def test_wildcard_and_named_columns_converge_to_higher_action(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """AD-155:同表 `*` 與具名欄位並存時,只保留動作**高於** `*` 的具名欄位。

    `*` read + C11 edit → C11 是更高權限的覆寫,保留;`*` read + C12 read 無額外資訊,
    收斂進 `*`;`*` edit 之下任何具名欄位都不可能更高,一律省略。
    """
    client_uid = await _create_client_row(session_factory)
    service = await repo.create_service(code=_uniq("erp"), name="ERP", actor_uid=ACTOR_UID)
    operation = await repo.create_operation(
        service_pid=service.pid, name="O1", actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        operation.pid,
        [ScopeItem("T1", ALL_COLUMNS), ScopeItem("T2", ALL_COLUMNS)],
        actor_uid=ACTOR_UID,
    )
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation.pid],
        items={
            operation.pid: [
                PermissionItem("T1", ALL_COLUMNS, ACTION_READ),
                PermissionItem("T1", "C11", ACTION_EDIT),
                PermissionItem("T1", "C12", ACTION_READ),
                PermissionItem("T2", ALL_COLUMNS, ACTION_EDIT),
                PermissionItem("T2", "C21", ACTION_READ),
            ]
        },
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == {
        "O1": {
            "T1": {ALL_COLUMNS: ACTION_READ, "C11": ACTION_EDIT},
            "T2": {ALL_COLUMNS: ACTION_EDIT},
        }
    }


# ── 臨時權限:效期與聯集 ────────────────────────────────────────────────
async def test_expired_exception_excluded_and_active_included(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """過期臨時權限(expires_at < now)排除;未過期臨時權限納入聯集,並可提高既有欄位動作。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={operation_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    now = db_now()
    await _bind_exception_set(
        repo,
        client_uid,
        operation_pid=operation_pid,
        items=[PermissionItem("T3", "C31", ACTION_EDIT)],
        expires_at=now - timedelta(minutes=1),
    )
    await _bind_exception_set(
        repo,
        client_uid,
        operation_pid=operation_pid,
        items=[
            PermissionItem("T1", "C11", ACTION_EDIT),
            PermissionItem("T2", "C22", ACTION_READ),
        ],
        expires_at=now + timedelta(days=1),
    )
    await session.commit()

    async with session_factory() as db:
        result = await EffectivePermissionService(db).preview(client_uid)

    assert len(result.exception_sets) == 1  # 過期綁定不出現
    assert {row.operation_name: row.tables for row in result.operations} == {
        "O1": {"T1": {"C11": ACTION_EDIT}, "T2": {"C22": ACTION_READ}}
    }


async def test_exception_alone_grants_without_role(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """無 Role 也能只靠臨時權限組取得權限(加法模型;仍受作業範圍限制)。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _bind_exception_set(
        repo,
        client_uid,
        operation_pid=operation_pid,
        items=[
            PermissionItem("T2", "C21", ACTION_EDIT),
            PermissionItem("T2", "C29", ACTION_EDIT),  # 範圍外欄位
        ],
    )
    await session.commit()

    async with session_factory() as db:
        result = await EffectivePermissionService(db).preview(client_uid)

    assert result.role is None
    assert {row.operation_name: row.tables for row in result.operations} == {
        "O1": {"T2": {"C21": ACTION_EDIT}}
    }


# ── 快取行為 ────────────────────────────────────────────────────────────
async def test_second_read_hits_cache_and_invalidation_refreshes(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    redis: FakeRedis,
) -> None:
    """第二次讀取命中快取(不反映期間的 RDS 異動);失效後重讀即為新值。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    profile_pid = await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={operation_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    await session.commit()

    first = await _preview(session_factory, client_uid)
    assert first == {"O1": {"T1": {"C11": ACTION_READ}}}
    cache_key = permission_cache.effective_key(client_uid)
    assert cache_key in redis.store
    assert redis.ttl[cache_key] == permission_cache.DEFAULT_TTL_SECONDS

    await repo.replace_profile_items(
        profile_pid,
        operation_pid,
        [
            PermissionItem("T1", "C11", ACTION_EDIT),
            PermissionItem("T3", "C31", ACTION_READ),
        ],
        actor_uid=ACTOR_UID,
    )
    await session.commit()

    assert await _preview(session_factory, client_uid) == first  # 命中快取,未回源

    await permission_cache.invalidate_clients(client_uid)
    assert await _preview(session_factory, client_uid) == {
        "O1": {"T1": {"C11": ACTION_EDIT}, "T3": {"C31": ACTION_READ}}
    }


async def test_redis_outage_degrades_to_direct_read(
    repo: ClientSettingRepository,
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    redis: FakeRedis,
) -> None:
    """Redis 全掛:預覽照常直讀 RDS(降級不失能)。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={operation_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    await session.commit()
    redis.fail_on = {"get", "set", "delete", "scan_iter"}

    assert await _preview(session_factory, client_uid) == {
        "O1": {"T1": {"C11": ACTION_READ}}
    }
    assert redis.store == {}


# ── 端點:權限與錯誤碼 ──────────────────────────────────────────────────
async def test_unknown_client_raises_404(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with pytest.raises(AppError) as exc_info:
        async with session_factory() as db:
            await EffectivePermissionService(db).preview(uuid4())

    assert exc_info.value.status_code == 404


async def test_endpoint_requires_admin_and_returns_envelope(
    repo: ClientSettingRepository,
    session: AsyncSession,
    http_client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """未登入 401、非 admin 403、不存在 client 404、admin 200 統一封套。"""
    client_uid = await _create_client_row(session_factory)
    _, operation_pid = await _make_arch_operation(repo)
    await _assign_profile(
        repo,
        client_uid,
        operation_pids=[operation_pid],
        items={operation_pid: [PermissionItem("T1", "C11", ACTION_READ)]},
    )
    await session.commit()
    url = f"{_CLIENTS_URL}/{client_uid}/effective-permissions"

    assert (await http_client.get(url)).status_code == 401

    member_username = _uniq(f"{_USERNAME_PREFIX}-vera")
    await _create_user(session_factory, member_username, "member")
    await _login(http_client, member_username)
    assert (await http_client.get(url)).status_code == 403

    admin_username = _uniq(f"{_USERNAME_PREFIX}-adam")
    await _create_user(session_factory, admin_username, "admin")
    await _login(http_client, admin_username)

    missing = await http_client.get(f"{_CLIENTS_URL}/{_FAKE_UID}/effective-permissions")
    assert missing.status_code == 404
    assert missing.json()["success"] is False

    resp = await http_client.get(url)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["response_code"] == 200
    data = body["data"]
    assert data["client_uid"] == str(client_uid)
    assert data["operations"][0]["operation_name"] == "O1"
    assert data["operations"][0]["tables"] == {"T1": {"C11": ACTION_READ}}
