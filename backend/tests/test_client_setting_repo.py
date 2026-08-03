"""client_setting 權限階層 Repository 測試(v1.6.1 task-002)。

對齊 test_client_setting_schema.py 模式:連真實本地 PostgreSQL 測試 DB 模擬 RDS
(env 指向共用測試 DB,不觸碰真正 AWS RDS)。驗證 CRUD round-trip、軟刪後不再出現、
批次置換原子性、綁定計數正確、client_roles 置換後恆 ≤ 1 筆有效。
清理一律 DELETE 資料,**不做任何 DROP**。
"""

from __future__ import annotations

import os

# app 模組於 import 時即讀 env 建立 engine;client_setting 連線沿用 AWS_RDS_*(見 reader.py),
# 測試指向共用本地測試 DB(data_center_etl_test),不觸碰真正 AWS RDS
_PG_HOST = os.environ.get("TEST_PG_HOST", "localhost")
_PG_PORT = os.environ.get("TEST_PG_PORT", "5435")
_PG_USER = os.environ.get("TEST_PG_USER", "data_center_etl")
_PG_PASSWORD = os.environ.get("TEST_PG_PASSWORD", "changeme-development")
_TEST_DB_NAME = "data_center_etl_test"

os.environ["AWS_RDS_HOST"] = _PG_HOST
os.environ["AWS_RDS_PORT"] = _PG_PORT
os.environ["AWS_RDS_USER"] = _PG_USER
os.environ["AWS_RDS_PASSWORD"] = _PG_PASSWORD
os.environ["AWS_RDS_TARGET_DB"] = _TEST_DB_NAME
os.environ.setdefault("AWS_RDS_SOURCE_DB", _TEST_DB_NAME)
os.environ.setdefault(
    "DATABASE_URL",
    f"postgresql+asyncpg://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:{_PG_PORT}/{_TEST_DB_NAME}",
)
os.environ.setdefault("INIT_ADMIN_USERNAME", "init-admin")
os.environ.setdefault("INIT_ADMIN_PASSWORD", "init-admin-password-for-test")

from collections.abc import AsyncIterator  # noqa: E402
from datetime import timedelta  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import func, select, text  # noqa: E402
from sqlalchemy.exc import DBAPIError, IntegrityError  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession  # noqa: E402

from app.etl import introspect  # noqa: E402
from app.etl.client_setting_schema import ensure_client_setting_schema  # noqa: E402
from app.models.client_setting import (  # noqa: E402
    ACTION_EDIT,
    ACTION_READ,
    ALL_COLUMNS,
    CLIENT_SETTING_SCHEMA,
    CLIENT_SETTING_TABLES,
    ClientRole,
)
from app.repositories.client_setting_repo import (  # noqa: E402
    ClientSettingRepository,
    PermissionItem,
    ScopeItem,
    client_setting_session,
)
from app.utils.datetime import db_now  # noqa: E402

ACTOR_UID = uuid4()

_schema_ready = False


async def _ensure_schema_once(engine: AsyncEngine) -> None:
    """整個測試模組只建置一次 schema(DDL 冪等,重跑僅為浪費時間)。"""
    global _schema_ready
    if not _schema_ready:
        async with engine.begin() as conn:
            await ensure_client_setting_schema(conn)
        _schema_ready = True


async def _clear_all(engine: AsyncEngine) -> None:
    """清空 12 張表資料(反向 FK 順序,子表在先)。禁 DROP。"""
    async with engine.begin() as conn:
        for table in reversed(CLIENT_SETTING_TABLES):
            await conn.execute(text(f"DELETE FROM {CLIENT_SETTING_SCHEMA}.{table}"))


@pytest_asyncio.fixture(autouse=True)
async def _reset_introspect_engines() -> AsyncIterator[None]:
    """introspect 以 module-level 連線池快取 RDS engine;pytest 每測試獨立 event loop,
    跨 loop 重用池內連線會失效。每測試後 dispose + 清快取(對齊 test_data_query_api.py)。"""
    yield
    for engine in list(introspect._ENGINES.values()):
        await engine.dispose()
    introspect._ENGINES.clear()


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """指向測試 DB 的 client_setting Session(即受測的連線管理入口)。"""
    engine = introspect.get_engine("target")
    await _ensure_schema_once(engine)
    try:
        async with client_setting_session() as db:
            yield db
    finally:
        await _clear_all(engine)


@pytest_asyncio.fixture
async def repo(session: AsyncSession) -> ClientSettingRepository:
    return ClientSettingRepository(session)


async def _make_operation(
    repo: ClientSettingRepository, *, code: str, name: str
) -> tuple[int, int]:
    """建 system 別 + 作業,回傳 (service_pid, operation_pid)。"""
    service = await repo.create_service(code=code, name=code.upper(), actor_uid=ACTOR_UID)
    operation = await repo.create_operation(
        service_pid=service.pid, name=name, actor_uid=ACTOR_UID
    )
    return service.pid, operation.pid


# ── 系統別 / 作業 CRUD ──────────────────────────────────────────────────
async def test_service_crud_round_trip(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """建立 → 讀取 → 更新 → 列表:欄位如實往返,時間為 naive UTC+8。"""
    service = await repo.create_service(
        code="erp", name="ERP 系統", description="測試", actor_uid=ACTOR_UID
    )
    await session.commit()

    found = await repo.get_service_by_uid(service.uid)
    assert found is not None
    assert (found.code, found.name, found.description) == ("erp", "ERP 系統", "測試")
    assert found.created_at.tzinfo is None
    assert found.created_by == ACTOR_UID
    assert found.is_deleted is False

    await repo.update_service(found, name="ERP 主系統", actor_uid=ACTOR_UID)
    await session.commit()
    assert [s.name for s in await repo.list_services()] == ["ERP 主系統"]


async def test_soft_deleted_service_disappears_from_reads(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """軟刪後預設讀取(get / list)一律讀不到,且列仍實體存在(禁物理刪除)。"""
    service = await repo.create_service(code="crm", name="CRM", actor_uid=ACTOR_UID)
    service_uid = service.uid
    await session.commit()

    await repo.soft_delete_service(service, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.get_service_by_uid(service_uid) is None
    assert await repo.list_services() == []
    remaining = (
        await session.execute(
            text(f"SELECT count(*) FROM {CLIENT_SETTING_SCHEMA}.services")
        )
    ).scalar_one()
    assert remaining == 1


async def test_soft_delete_operation_cascades_scope_items(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """軟刪作業連動軟刪其範圍項(範圍項為作業的內含子集合)。"""
    _, operation_pid = await _make_operation(repo, code="erp", name="O1")
    await repo.replace_operation_items(
        operation_pid, [ScopeItem("T1", ALL_COLUMNS)], actor_uid=ACTOR_UID
    )
    await session.commit()

    operation = (await repo.list_operations())[0]
    await repo.soft_delete_operation(operation, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.list_operations() == []
    assert await repo.list_operation_items(operation_pid) == []


# ── 批次置換 ───────────────────────────────────────────────────────────
async def test_replace_operation_items_replaces_whole_set(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """整批置換:舊集合軟刪、新集合生效(重複置換不殘留舊項)。"""
    _, operation_pid = await _make_operation(repo, code="erp", name="O1")
    await repo.replace_operation_items(
        operation_pid,
        [ScopeItem("T1", "C11"), ScopeItem("T2", ALL_COLUMNS)],
        actor_uid=ACTOR_UID,
    )
    await session.commit()
    assert len(await repo.list_operation_items(operation_pid)) == 2

    await repo.replace_operation_items(
        operation_pid, [ScopeItem("T3", "C31")], actor_uid=ACTOR_UID
    )
    await session.commit()
    items = await repo.list_operation_items(operation_pid)
    assert [(i.table_name, i.column_name) for i in items] == [("T3", "C31")]


async def test_replace_operation_items_is_atomic(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """置換中途違反唯一鍵 → 整筆交易回滾,舊集合原封不動(軟刪也一併復原)。"""
    _, operation_pid = await _make_operation(repo, code="erp", name="O1")
    await repo.replace_operation_items(
        operation_pid, [ScopeItem("T1", "C11")], actor_uid=ACTOR_UID
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repo.replace_operation_items(
            operation_pid,
            [ScopeItem("T9", "C91"), ScopeItem("T9", "C91")],
            actor_uid=ACTOR_UID,
        )
    await session.rollback()

    items = await repo.list_operation_items(operation_pid)
    assert [(i.table_name, i.column_name) for i in items] == [("T1", "C11")]


async def test_replace_profile_operations_clears_items_of_removed_operation(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """移除勾選作業時,連動清掉該作業底下的授權項;保留作業的授權項不受影響。"""
    service_pid, op1_pid = await _make_operation(repo, code="erp", name="O1")
    op2 = await repo.create_operation(service_pid=service_pid, name="O2", actor_uid=ACTOR_UID)
    op2_pid = op2.pid
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    profile_pid = profile.pid

    await repo.replace_profile_operations(
        profile_pid, [op1_pid, op2_pid], actor_uid=ACTOR_UID
    )
    await repo.replace_profile_items(
        profile_pid, op1_pid, [PermissionItem("T1", "C11", ACTION_READ)], actor_uid=ACTOR_UID
    )
    await repo.replace_profile_items(
        profile_pid, op2_pid, [PermissionItem("T2", "C21", ACTION_EDIT)], actor_uid=ACTOR_UID
    )
    await session.commit()
    assert len(await repo.list_profile_items(profile_pid)) == 2

    await repo.replace_profile_operations(profile_pid, [op1_pid], actor_uid=ACTOR_UID)
    await session.commit()

    assert [row.operation_pid for row in await repo.list_profile_operations(profile_pid)] == [
        op1_pid
    ]
    remaining = await repo.list_profile_items(profile_pid)
    assert [(i.operation_pid, i.table_name, i.action) for i in remaining] == [
        (op1_pid, "T1", ACTION_READ)
    ]


async def test_replace_exception_operations_clears_items_of_removed_operation(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """臨時權限組勾選作業置換語意與角色權限設定檔一致(移除作業連動清授權項)。"""
    service_pid, op1_pid = await _make_operation(repo, code="erp", name="O1")
    op2 = await repo.create_operation(service_pid=service_pid, name="O2", actor_uid=ACTOR_UID)
    op2_pid = op2.pid
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    set_pid = exception_set.pid

    await repo.replace_exception_operations(set_pid, [op1_pid, op2_pid], actor_uid=ACTOR_UID)
    await repo.replace_exception_items(
        set_pid, op2_pid, [PermissionItem("T2", ALL_COLUMNS, ACTION_READ)], actor_uid=ACTOR_UID
    )
    await session.commit()
    assert len(await repo.list_exception_items(set_pid)) == 1

    await repo.replace_exception_operations(set_pid, [op1_pid], actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.list_exception_items(set_pid) == []
    assert await repo.list_exception_items_by_set_pids([set_pid]) == []


# ── 刪除防呆計數 ────────────────────────────────────────────────────────
async def test_count_operations_by_service(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    service_pid, _ = await _make_operation(repo, code="erp", name="O1")
    await session.commit()
    assert await repo.count_operations_by_service(service_pid) == 1

    operation = (await repo.list_operations())[0]
    await repo.soft_delete_operation(operation, actor_uid=ACTOR_UID)
    await session.commit()
    assert await repo.count_operations_by_service(service_pid) == 0


async def test_count_profiles_referencing_operation(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """作業引用計數涵蓋角色權限設定檔勾選 / 授權項與臨時權限組兩側(刪作業防呆用)。"""
    _, operation_pid = await _make_operation(repo, code="erp", name="O1")
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    await session.commit()
    assert await repo.count_profiles_referencing_operation(operation_pid) == 0

    await repo.replace_profile_operations(profile.pid, [operation_pid], actor_uid=ACTOR_UID)
    await repo.replace_profile_items(
        profile.pid,
        operation_pid,
        [PermissionItem("T1", "C11", ACTION_READ)],
        actor_uid=ACTOR_UID,
    )
    await repo.replace_exception_operations(
        exception_set.pid, [operation_pid], actor_uid=ACTOR_UID
    )
    await session.commit()
    assert await repo.count_profiles_referencing_operation(operation_pid) == 3

    await repo.replace_profile_operations(profile.pid, [], actor_uid=ACTOR_UID)
    await repo.replace_exception_operations(exception_set.pid, [], actor_uid=ACTOR_UID)
    await session.commit()
    assert await repo.count_profiles_referencing_operation(operation_pid) == 0


async def test_count_roles_by_profile_and_clients_by_role(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """角色權限設定檔被 Role 綁、Role 被 Client 指派的計數(供 409 防呆)。"""
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    role = await repo.create_role(
        permission_profile_pid=profile.pid, name="R1", actor_uid=ACTOR_UID
    )
    profile_pid, role_pid = profile.pid, role.pid
    await session.commit()

    assert await repo.count_roles_by_profile(profile_pid) == 1
    assert await repo.count_clients_by_role(role_pid) == 0

    api_client_uid = uuid4()
    await repo.assign_client_role(api_client_uid, role_pid, actor_uid=ACTOR_UID)
    await session.commit()
    assert await repo.count_clients_by_role(role_pid) == 1

    await repo.remove_client_role(api_client_uid, actor_uid=ACTOR_UID)
    await repo.soft_delete_role(role, actor_uid=ACTOR_UID)
    await session.commit()
    assert await repo.count_clients_by_role(role_pid) == 0
    assert await repo.count_roles_by_profile(profile_pid) == 0


async def test_count_active_bindings_by_exception_set_ignores_expired(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """臨時權限組刪除防呆只算未過期綁定;已過期綁定自動不計。"""
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    set_pid = exception_set.pid
    now = db_now()
    await repo.bind_client_exception_set(uuid4(), set_pid, actor_uid=ACTOR_UID)
    await repo.bind_client_exception_set(
        uuid4(), set_pid, expires_at=now + timedelta(days=1), actor_uid=ACTOR_UID
    )
    await repo.bind_client_exception_set(
        uuid4(), set_pid, expires_at=now - timedelta(days=1), actor_uid=ACTOR_UID
    )
    await session.commit()

    assert await repo.count_active_bindings_by_exception_set(set_pid) == 2


# ── Client 指派 ────────────────────────────────────────────────────────
async def test_assign_client_role_is_idempotent_replacement(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """重複指派恆為置換:未刪列永遠 ≤ 1 筆,且指向最後一次指派的 Role。"""
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    role1 = await repo.create_role(
        permission_profile_pid=profile.pid, name="R1", actor_uid=ACTOR_UID
    )
    role2 = await repo.create_role(
        permission_profile_pid=profile.pid, name="R2", actor_uid=ACTOR_UID
    )
    role1_pid, role2_pid = role1.pid, role2.pid
    api_client_uid = uuid4()

    for role_pid in (role1_pid, role2_pid, role2_pid):
        await repo.assign_client_role(api_client_uid, role_pid, actor_uid=ACTOR_UID)
        await session.commit()

    assignment = await repo.get_client_role(api_client_uid)
    assert assignment is not None
    assert assignment.role_pid == role2_pid

    active = (
        await session.execute(
            select(func.count())
            .select_from(ClientRole)
            .where(
                ClientRole.api_client_uid == api_client_uid,
                ClientRole.is_deleted.is_(False),
            )
        )
    ).scalar_one()
    assert active == 1


async def test_remove_client_role_reports_whether_anything_removed(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    role = await repo.create_role(
        permission_profile_pid=profile.pid, name="R1", actor_uid=ACTOR_UID
    )
    api_client_uid = uuid4()
    await repo.assign_client_role(api_client_uid, role.pid, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.remove_client_role(api_client_uid, actor_uid=ACTOR_UID) is True
    await session.commit()
    assert await repo.get_client_role(api_client_uid) is None
    assert await repo.remove_client_role(api_client_uid, actor_uid=ACTOR_UID) is False


async def test_client_exception_set_binding_expiry_and_unbind(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """綁定清單含已過期列(供前端標示),未過期清單自動排除到期者;解除為軟刪。"""
    set_a = await repo.create_exception_set(name="XA", actor_uid=ACTOR_UID)
    set_b = await repo.create_exception_set(name="XB", actor_uid=ACTOR_UID)
    api_client_uid = uuid4()
    now = db_now()
    await repo.bind_client_exception_set(api_client_uid, set_a.pid, actor_uid=ACTOR_UID)
    expired = await repo.bind_client_exception_set(
        api_client_uid, set_b.pid, expires_at=now - timedelta(minutes=1), actor_uid=ACTOR_UID
    )
    expired_uid = expired.uid
    await session.commit()

    assert len(await repo.list_client_exception_sets(api_client_uid)) == 2
    active = await repo.list_active_client_exception_sets(api_client_uid)
    assert [row.exception_set_pid for row in active] == [set_a.pid]

    binding = await repo.get_client_exception_set_by_uid(expired_uid)
    assert binding is not None
    await repo.unbind_client_exception_set(binding, actor_uid=ACTOR_UID)
    await session.commit()
    assert len(await repo.list_client_exception_sets(api_client_uid)) == 1
    assert await repo.get_client_exception_set_by_uid(expired_uid) is None


async def test_duplicate_binding_is_rejected(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """同一 Client 重複綁同一臨時權限組由 partial unique 擋下(呼叫端轉 409)。"""
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    api_client_uid = uuid4()
    await repo.bind_client_exception_set(
        api_client_uid, exception_set.pid, actor_uid=ACTOR_UID
    )
    await session.commit()

    with pytest.raises(IntegrityError):
        await repo.bind_client_exception_set(
            api_client_uid, exception_set.pid, actor_uid=ACTOR_UID
        )
    await session.rollback()


# ── 角色權限設定檔軟刪連動 + 批次載入 ───────────────────────────────────────────
async def test_soft_delete_profile_cascades_children(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    _, operation_pid = await _make_operation(repo, code="erp", name="O1")
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    profile_pid = profile.pid
    await repo.replace_profile_operations(profile_pid, [operation_pid], actor_uid=ACTOR_UID)
    await repo.replace_profile_items(
        profile_pid,
        operation_pid,
        [PermissionItem("T1", "C11", ACTION_READ)],
        actor_uid=ACTOR_UID,
    )
    await session.commit()

    await repo.soft_delete_permission_profile(profile, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.list_permission_profiles() == []
    assert await repo.list_profile_operations(profile_pid) == []
    assert await repo.list_profile_items(profile_pid) == []


async def test_bulk_loaders_cover_multiple_parents(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """供最終權限展開的批次載入:多作業 / 多臨時權限組一次取回,空輸入回空集合。"""
    service_pid, op1_pid = await _make_operation(repo, code="erp", name="O1")
    op2 = await repo.create_operation(service_pid=service_pid, name="O2", actor_uid=ACTOR_UID)
    op2_pid = op2.pid
    await repo.replace_operation_items(
        op1_pid, [ScopeItem("T1", "C11")], actor_uid=ACTOR_UID
    )
    await repo.replace_operation_items(
        op2_pid, [ScopeItem("T2", "C21")], actor_uid=ACTOR_UID
    )
    set_a = await repo.create_exception_set(name="XA", actor_uid=ACTOR_UID)
    set_b = await repo.create_exception_set(name="XB", actor_uid=ACTOR_UID)
    await repo.replace_exception_operations(set_a.pid, [op1_pid], actor_uid=ACTOR_UID)
    await repo.replace_exception_operations(set_b.pid, [op2_pid], actor_uid=ACTOR_UID)
    set_pids = [set_a.pid, set_b.pid]
    await session.commit()

    scope = await repo.list_operation_items_by_operation_pids([op1_pid, op2_pid])
    assert {(i.operation_pid, i.table_name) for i in scope} == {
        (op1_pid, "T1"),
        (op2_pid, "T2"),
    }
    granted = await repo.list_exception_operations_by_set_pids(set_pids)
    assert {row.operation_pid for row in granted} == {op1_pid, op2_pid}
    assert len(await repo.list_exception_sets_by_pids(set_pids)) == 2
    assert len(await repo.list_operations_by_pids([op1_pid, op2_pid])) == 2

    assert await repo.list_operation_items_by_operation_pids([]) == []
    assert await repo.list_exception_operations_by_set_pids([]) == []
    assert await repo.list_exception_items_by_set_pids([]) == []
    assert await repo.list_exception_sets_by_pids([]) == []
    assert await repo.list_operations_by_pids([]) == []


async def test_role_rebinding_profile_round_trip(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """Role 必綁角色權限設定檔,可改綁但不可清空;uid / pid 兩種讀法一致。"""
    profile1 = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    profile2 = await repo.create_permission_profile(name="P2", actor_uid=ACTOR_UID)
    role = await repo.create_role(
        permission_profile_pid=profile1.pid, name="R1", actor_uid=ACTOR_UID
    )
    role_uid, role_pid = role.uid, role.pid
    await session.commit()

    await repo.update_role(role, permission_profile_pid=profile2.pid, actor_uid=ACTOR_UID)
    await session.commit()

    by_uid = await repo.get_role_by_uid(role_uid)
    by_pid = await repo.get_role_by_pid(role_pid)
    assert by_uid is not None and by_pid is not None
    assert by_uid.pid == by_pid.pid == role_pid
    assert by_uid.permission_profile_pid == profile2.pid

    bound = await repo.get_permission_profile_by_pid(by_uid.permission_profile_pid)
    assert bound is not None and bound.name == "P2"


# ── 快取失效扇出反查(task-003)──────────────────────────────────────────
async def test_invalidation_fanout_lookups(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """角色權限設定檔 / 臨時權限組異動時,反查受影響 Client 的兩段查詢(供快取失效)。"""
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    role1 = await repo.create_role(
        permission_profile_pid=profile.pid, name="R1", actor_uid=ACTOR_UID
    )
    role2 = await repo.create_role(
        permission_profile_pid=profile.pid, name="R2", actor_uid=ACTOR_UID
    )
    profile_pid, role1_pid, role2_pid = profile.pid, role1.pid, role2.pid
    client1, client2, client3 = uuid4(), uuid4(), uuid4()
    for client_uid, role_pid in (
        (client1, role1_pid),
        (client2, role1_pid),
        (client3, role2_pid),
    ):
        await repo.assign_client_role(client_uid, role_pid, actor_uid=ACTOR_UID)

    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    set_pid = exception_set.pid
    bound_active, bound_expired = uuid4(), uuid4()
    await repo.bind_client_exception_set(bound_active, set_pid, actor_uid=ACTOR_UID)
    await repo.bind_client_exception_set(
        bound_expired,
        set_pid,
        expires_at=db_now() - timedelta(days=1),
        actor_uid=ACTOR_UID,
    )
    await session.commit()

    roles = await repo.list_roles_by_profile(profile_pid)
    assert {role.pid for role in roles} == {role1_pid, role2_pid}

    assignments = await repo.list_client_roles_by_role_pids([r.pid for r in roles])
    assert {row.api_client_uid for row in assignments} == {client1, client2, client3}

    # 失效扇出寧可多刪:已過期綁定同樣列入
    bindings = await repo.list_client_exception_sets_by_set_pids([set_pid])
    assert {row.api_client_uid for row in bindings} == {bound_active, bound_expired}

    assert await repo.list_client_roles_by_role_pids([]) == []
    assert await repo.list_client_exception_sets_by_set_pids([]) == []

    await repo.soft_delete_role(role2, actor_uid=ACTOR_UID)
    await session.commit()
    assert [role.pid for role in await repo.list_roles_by_profile(profile_pid)] == [role1_pid]


# ── v1.6.1 fixed:跨庫連動 / 併發鎖 / 殭屍綁定 ──────────────────────────
async def test_soft_delete_client_grants_clears_both_tables(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """AD-152:註銷 API Client 時,RDS 側指派與綁定同交易軟刪,其他 Client 不受影響。"""
    profile = await repo.create_permission_profile(name="P1", actor_uid=ACTOR_UID)
    role = await repo.create_role(
        permission_profile_pid=profile.pid, name="R1", actor_uid=ACTOR_UID
    )
    role_pid = role.pid
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    set_pid = exception_set.pid
    doomed, survivor = uuid4(), uuid4()
    for client_uid in (doomed, survivor):
        await repo.assign_client_role(client_uid, role_pid, actor_uid=ACTOR_UID)
        await repo.bind_client_exception_set(client_uid, set_pid, actor_uid=ACTOR_UID)
    await session.commit()

    await repo.soft_delete_client_grants(doomed, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.get_client_role(doomed) is None
    assert await repo.list_client_exception_sets(doomed) == []
    # 孤兒清乾淨 → Role 與臨時權限組的刪除防呆不再被已註銷 Client 卡住
    assert await repo.count_clients_by_role(role_pid) == 1
    assert await repo.count_active_bindings_by_exception_set(set_pid) == 1
    assert await repo.get_client_role(survivor) is not None


async def test_soft_delete_exception_set_clears_leftover_bindings(
    repo: ClientSettingRepository, session: AsyncSession
) -> None:
    """AD-156:臨時權限組軟刪連動軟刪其殘留(已過期)綁定,不留看不到又解不掉的殭屍列。"""
    exception_set = await repo.create_exception_set(name="X1", actor_uid=ACTOR_UID)
    set_pid = exception_set.pid
    api_client_uid = uuid4()
    binding = await repo.bind_client_exception_set(
        api_client_uid,
        set_pid,
        expires_at=db_now() - timedelta(days=1),
        actor_uid=ACTOR_UID,
    )
    binding_uid = binding.uid
    await session.commit()

    await repo.soft_delete_exception_set(exception_set, actor_uid=ACTOR_UID)
    await session.commit()

    assert await repo.list_client_exception_sets(api_client_uid) == []
    assert await repo.get_client_exception_set_by_uid(binding_uid) is None
    assert await repo.list_client_exception_sets_by_set_pids([set_pid]) == []


@pytest.mark.parametrize(
    ("table", "getter"),
    [
        ("permission_profiles", "get_permission_profile_by_uid"),
        ("exception_sets", "get_exception_set_by_uid"),
        ("operations", "get_operation_by_uid"),
    ],
)
async def test_parent_getters_take_row_lock_when_for_update(
    repo: ClientSettingRepository, session: AsyncSession, table: str, getter: str
) -> None:
    """AD-153:置換路徑取父列時加行鎖,另一條連線再取同列即取不到(併發置換序列化)。"""
    if table == "permission_profiles":
        parent = await repo.create_permission_profile(name="P-lock", actor_uid=ACTOR_UID)
    elif table == "exception_sets":
        parent = await repo.create_exception_set(name="X-lock", actor_uid=ACTOR_UID)
    else:
        service = await repo.create_service(code="lock", name="LOCK", actor_uid=ACTOR_UID)
        parent = await repo.create_operation(
            service_pid=service.pid, name="O-lock", actor_uid=ACTOR_UID
        )
    parent_uid, parent_pid = parent.uid, parent.pid
    await session.commit()

    # 無鎖版不佔鎖 → 他人可正常取件
    assert await getattr(repo, getter)(parent_uid) is not None
    await session.rollback()

    nowait_sql = text(
        f"SELECT pid FROM {CLIENT_SETTING_SCHEMA}.{table} WHERE pid = :pid FOR UPDATE NOWAIT"
    )
    try:
        locked = await getattr(repo, getter)(parent_uid, for_update=True)
        assert locked is not None
        async with client_setting_session() as other:
            with pytest.raises(DBAPIError):
                await other.execute(nowait_sql, {"pid": parent_pid})
            await other.rollback()
    finally:
        # 務必釋放鎖,否則 fixture 的清理 DELETE 會卡住
        await session.rollback()
