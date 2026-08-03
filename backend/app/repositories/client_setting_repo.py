"""RDS `client_setting` schema 權限階層 Repository(v1.6.1 task-002)。

權限設定的唯一真身在目標 RDS(propose v1.6.1 決策),本層直接對 RDS 讀寫,自有 DB
不留副本、不做快照。連線重用 `introspect.get_engine("target")` 的程序內快取 engine
(連線池共用,對齊 `semantic_admin_service.py`),Session 由 `client_setting_session()`
以 `async_sessionmaker` 產出。

- **交易邊界由呼叫端(service)掌握**:本層只 `flush`、**不** `commit`;批次置換的
  「軟刪舊集合 + 插入新集合」因而恆落在同一交易內(全成或全不成)。
- 讀取一律過濾 `is_deleted`;刪除一律軟刪(`04-databases/02-soft-delete.md` 命名強制:
  過濾版無後綴)。父列軟刪時連動軟刪其「內含子集合」(作業→範圍項、角色權限設定檔→勾選/授權項、
  臨時權限組→勾選/授權項);跨實體引用不連鎖刪除,改由 `count_*` 防呆查詢供 service 擋 409。
- 時間欄位為 naive UTC+8(`04-databases/06-timezone.md`,RDS datetime2 等價慣例),
  寫入一律走 `db_now()`;`expires_at` 亦同一時基。
- 全走 ORM / bind params,無字串拼接 SQL(`04-databases/04-sql-safety.md`)。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, Update, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.etl import introspect
from app.models.client_setting import (
    ClientExceptionSet,
    ClientRole,
    ClientSettingBaseModel,
    ExceptionItem,
    ExceptionOperation,
    ExceptionSet,
    Operation,
    OperationItem,
    PermissionProfile,
    ProfileItem,
    ProfileOperation,
    Role,
    Service,
)
from app.utils.datetime import db_now


@asynccontextmanager
async def client_setting_session() -> AsyncIterator[AsyncSession]:
    """取一條指向目標 RDS 的 Session(engine 為程序內快取,禁每請求另建連線)。

    engine 取得失敗(env 缺值 / URL 不合法)時於建立 Session 前即拋出,尚未佔用任何連線;
    Session 建立後一律於 `finally` 關閉,異常路徑不洩漏連線。交易由呼叫端以
    `async with session.begin():` 或顯式 `commit()` / `rollback()` 控制。
    """
    engine = introspect.get_engine("target")
    session = async_sessionmaker(engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        await session.close()


@dataclass(frozen=True)
class ScopeItem:
    """作業範圍一項:表 × 欄位(`column_name='*'` 代表該表全欄位)。"""

    table_name: str
    column_name: str


@dataclass(frozen=True)
class PermissionItem:
    """授權一項:表 × 欄位 × 動作(read / edit)。"""

    table_name: str
    column_name: str
    action: str


class ClientSettingRepository:
    """權限階層 12 表的資料存取層(RDS 直讀寫;交易由呼叫端掌握)。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── 共用小工具 ────────────────────────────────────────────────────────
    async def _touch(self, row: ClientSettingBaseModel, actor_uid: UUID) -> None:
        row.updated_by = actor_uid
        row.updated_at = db_now()
        await self._db.flush()

    async def _soft_delete(self, row: ClientSettingBaseModel, actor_uid: UUID) -> None:
        row.is_deleted = True
        await self._touch(row, actor_uid)

    async def _soft_delete_where(self, stmt: Update, *, actor_uid: UUID) -> None:
        """批次軟刪(審計欄位一併更新);ORM 物件狀態不同步,讀取一律重查。"""
        await self._db.execute(
            stmt.values(
                is_deleted=True, updated_at=db_now(), updated_by=actor_uid
            ).execution_options(synchronize_session=False)
        )

    async def _count(self, stmt: Select[tuple[int]]) -> int:
        return int((await self._db.execute(stmt)).scalar_one())

    @staticmethod
    def _lock[RowT](stmt: Select[tuple[RowT]], *, for_update: bool) -> Select[tuple[RowT]]:
        """`for_update=True` 時對父列加行鎖(`SELECT ... FOR UPDATE`)。

        整批置換系列是 read-then-write:未鎖父列時,READ COMMITTED 下兩管理員併發存檔會
        各刪自己看到的舊列、各插自己的新集合,落地成兩邊聯集(授權被放大)。置換路徑於
        交易開頭以鎖定版取父列,同一父列的置換即序列化為「後者覆蓋」。
        """
        return stmt.with_for_update() if for_update else stmt

    # ── 系統別 services ──────────────────────────────────────────────────
    async def list_services(self) -> list[Service]:
        rows = (
            await self._db.execute(
                select(Service).where(Service.is_deleted.is_(False)).order_by(Service.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_service_by_uid(self, uid: UUID) -> Service | None:
        return (
            await self._db.execute(
                select(Service).where(Service.uid == uid, Service.is_deleted.is_(False))
            )
        ).scalar_one_or_none()

    async def create_service(
        self, *, code: str, name: str, description: str | None = None, actor_uid: UUID
    ) -> Service:
        service = Service(
            uid=uuid4(),
            code=code,
            name=name,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(service)
        await self._db.flush()
        return service

    async def update_service(
        self,
        service: Service,
        *,
        name: str | None = None,
        description: str | None = None,
        actor_uid: UUID,
    ) -> Service:
        """部分更新;None 一律代表「不變更」。`code` 為對外契約不開放改(task-004)。"""
        if name is not None:
            service.name = name
        if description is not None:
            service.description = description
        await self._touch(service, actor_uid)
        return service

    async def soft_delete_service(self, service: Service, *, actor_uid: UUID) -> None:
        await self._soft_delete(service, actor_uid)

    async def count_operations_by_service(self, service_pid: int) -> int:
        """系統別底下未刪作業數(> 0 時 service 層擋刪除)。"""
        return await self._count(
            select(func.count())
            .select_from(Operation)
            .where(Operation.service_pid == service_pid, Operation.is_deleted.is_(False))
        )

    # ── 作業 operations ──────────────────────────────────────────────────
    async def list_operations(self, *, service_pid: int | None = None) -> list[Operation]:
        stmt = select(Operation).where(Operation.is_deleted.is_(False))
        if service_pid is not None:
            stmt = stmt.where(Operation.service_pid == service_pid)
        rows = (await self._db.execute(stmt.order_by(Operation.pid))).scalars()
        return list(rows.all())

    async def list_operations_by_pids(self, operation_pids: Sequence[int]) -> list[Operation]:
        if not operation_pids:
            return []
        rows = (
            await self._db.execute(
                select(Operation)
                .where(Operation.pid.in_(operation_pids), Operation.is_deleted.is_(False))
                .order_by(Operation.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_operation_by_uid(
        self, uid: UUID, *, for_update: bool = False
    ) -> Operation | None:
        return (
            await self._db.execute(
                self._lock(
                    select(Operation).where(
                        Operation.uid == uid, Operation.is_deleted.is_(False)
                    ),
                    for_update=for_update,
                )
            )
        ).scalar_one_or_none()

    async def create_operation(
        self,
        *,
        service_pid: int,
        name: str,
        description: str | None = None,
        actor_uid: UUID,
    ) -> Operation:
        operation = Operation(
            uid=uuid4(),
            service_pid=service_pid,
            name=name,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(operation)
        await self._db.flush()
        return operation

    async def update_operation(
        self,
        operation: Operation,
        *,
        name: str | None = None,
        description: str | None = None,
        actor_uid: UUID,
    ) -> Operation:
        """部分更新;歸屬系統別(`service_pid`)不開放改(task-004 禁改歸屬)。"""
        if name is not None:
            operation.name = name
        if description is not None:
            operation.description = description
        await self._touch(operation, actor_uid)
        return operation

    async def soft_delete_operation(self, operation: Operation, *, actor_uid: UUID) -> None:
        """軟刪作業並連動軟刪其範圍項(範圍項為作業的內含子集合,不獨立存在)。"""
        operation_pid = operation.pid
        await self._soft_delete(operation, actor_uid)
        await self._soft_delete_where(
            update(OperationItem).where(
                OperationItem.operation_pid == operation_pid,
                OperationItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )

    async def count_profiles_referencing_operation(self, operation_pid: int) -> int:
        """作業被角色權限設定檔 / 臨時權限組引用的未刪筆數合計(勾選列與授權項皆計)。

        名稱沿用 task-002 規格;範圍含臨時權限組 — 刪除作業的防呆須同時擋兩側引用(task-004)。
        """
        statements: tuple[Select[tuple[int]], ...] = (
            select(func.count())
            .select_from(ProfileOperation)
            .where(
                ProfileOperation.operation_pid == operation_pid,
                ProfileOperation.is_deleted.is_(False),
            ),
            select(func.count())
            .select_from(ProfileItem)
            .where(
                ProfileItem.operation_pid == operation_pid,
                ProfileItem.is_deleted.is_(False),
            ),
            select(func.count())
            .select_from(ExceptionOperation)
            .where(
                ExceptionOperation.operation_pid == operation_pid,
                ExceptionOperation.is_deleted.is_(False),
            ),
            select(func.count())
            .select_from(ExceptionItem)
            .where(
                ExceptionItem.operation_pid == operation_pid,
                ExceptionItem.is_deleted.is_(False),
            ),
        )
        total = 0
        for stmt in statements:
            total += await self._count(stmt)
        return total

    # ── 作業範圍 operation_items ─────────────────────────────────────────
    async def list_operation_items(self, operation_pid: int) -> list[OperationItem]:
        return await self.list_operation_items_by_operation_pids([operation_pid])

    async def list_operation_items_by_operation_pids(
        self, operation_pids: Sequence[int]
    ) -> list[OperationItem]:
        """一次載入多作業的範圍項(供最終權限展開,避免逐作業 N+1)。"""
        if not operation_pids:
            return []
        rows = (
            await self._db.execute(
                select(OperationItem)
                .where(
                    OperationItem.operation_pid.in_(operation_pids),
                    OperationItem.is_deleted.is_(False),
                )
                .order_by(OperationItem.pid)
            )
        ).scalars()
        return list(rows.all())

    async def replace_operation_items(
        self, operation_pid: int, items: Sequence[ScopeItem], *, actor_uid: UUID
    ) -> list[OperationItem]:
        """整批置換作業範圍:同交易軟刪舊集合 + 插入新集合(重複項由唯一鍵擋下)。"""
        await self._soft_delete_where(
            update(OperationItem).where(
                OperationItem.operation_pid == operation_pid,
                OperationItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        rows = [
            OperationItem(
                uid=uuid4(),
                operation_pid=operation_pid,
                table_name=item.table_name,
                column_name=item.column_name,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            for item in items
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    # ── 角色權限設定檔 permission_profiles ───────────────────────────────
    async def list_permission_profiles(self) -> list[PermissionProfile]:
        rows = (
            await self._db.execute(
                select(PermissionProfile)
                .where(PermissionProfile.is_deleted.is_(False))
                .order_by(PermissionProfile.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_permission_profile_by_uid(
        self, uid: UUID, *, for_update: bool = False
    ) -> PermissionProfile | None:
        return (
            await self._db.execute(
                self._lock(
                    select(PermissionProfile).where(
                        PermissionProfile.uid == uid,
                        PermissionProfile.is_deleted.is_(False),
                    ),
                    for_update=for_update,
                )
            )
        ).scalar_one_or_none()

    async def get_permission_profile_by_pid(self, pid: int) -> PermissionProfile | None:
        return (
            await self._db.execute(
                select(PermissionProfile).where(
                    PermissionProfile.pid == pid, PermissionProfile.is_deleted.is_(False)
                )
            )
        ).scalar_one_or_none()

    async def create_permission_profile(
        self, *, name: str, description: str | None = None, actor_uid: UUID
    ) -> PermissionProfile:
        profile = PermissionProfile(
            uid=uuid4(),
            name=name,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(profile)
        await self._db.flush()
        return profile

    async def update_permission_profile(
        self,
        profile: PermissionProfile,
        *,
        name: str | None = None,
        description: str | None = None,
        actor_uid: UUID,
    ) -> PermissionProfile:
        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description
        await self._touch(profile, actor_uid)
        return profile

    async def soft_delete_permission_profile(
        self, profile: PermissionProfile, *, actor_uid: UUID
    ) -> None:
        """軟刪角色權限設定檔並連動軟刪其勾選作業與授權項(內含子集合)。"""
        profile_pid = profile.pid
        await self._soft_delete(profile, actor_uid)
        await self._soft_delete_where(
            update(ProfileOperation).where(
                ProfileOperation.permission_profile_pid == profile_pid,
                ProfileOperation.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        await self._soft_delete_where(
            update(ProfileItem).where(
                ProfileItem.permission_profile_pid == profile_pid,
                ProfileItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )

    async def count_roles_by_profile(self, permission_profile_pid: int) -> int:
        """綁定該角色權限設定檔的未刪角色數(> 0 時 service 層擋刪除)。"""
        return await self._count(
            select(func.count())
            .select_from(Role)
            .where(
                Role.permission_profile_pid == permission_profile_pid,
                Role.is_deleted.is_(False),
            )
        )

    async def list_roles_by_profile(self, permission_profile_pid: int) -> list[Role]:
        """綁定該角色權限設定檔的未刪角色(角色權限設定檔內容異動時,反查受影響 Client 的第一段)。"""
        rows = (
            await self._db.execute(
                select(Role)
                .where(
                    Role.permission_profile_pid == permission_profile_pid,
                    Role.is_deleted.is_(False),
                )
                .order_by(Role.pid)
            )
        ).scalars()
        return list(rows.all())

    # ── 角色權限設定檔勾選作業 profile_operations ────────────────────────────────
    async def list_profile_operations(
        self, permission_profile_pid: int
    ) -> list[ProfileOperation]:
        rows = (
            await self._db.execute(
                select(ProfileOperation)
                .where(
                    ProfileOperation.permission_profile_pid == permission_profile_pid,
                    ProfileOperation.is_deleted.is_(False),
                )
                .order_by(ProfileOperation.pid)
            )
        ).scalars()
        return list(rows.all())

    async def replace_profile_operations(
        self,
        permission_profile_pid: int,
        operation_pids: Sequence[int],
        *,
        actor_uid: UUID,
    ) -> list[ProfileOperation]:
        """整批置換勾選作業;被移除的作業連動清掉該作業底下的授權項(同交易)。"""
        previous = {row.operation_pid for row in await self.list_profile_operations(
            permission_profile_pid
        )}
        await self._soft_delete_where(
            update(ProfileOperation).where(
                ProfileOperation.permission_profile_pid == permission_profile_pid,
                ProfileOperation.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        removed = previous - set(operation_pids)
        if removed:
            await self._soft_delete_where(
                update(ProfileItem).where(
                    ProfileItem.permission_profile_pid == permission_profile_pid,
                    ProfileItem.operation_pid.in_(removed),
                    ProfileItem.is_deleted.is_(False),
                ),
                actor_uid=actor_uid,
            )
        rows = [
            ProfileOperation(
                uid=uuid4(),
                permission_profile_pid=permission_profile_pid,
                operation_pid=operation_pid,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            for operation_pid in operation_pids
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    # ── 角色權限設定檔授權項 profile_items ───────────────────────────────────────
    async def list_profile_items(
        self, permission_profile_pid: int, *, operation_pid: int | None = None
    ) -> list[ProfileItem]:
        stmt = select(ProfileItem).where(
            ProfileItem.permission_profile_pid == permission_profile_pid,
            ProfileItem.is_deleted.is_(False),
        )
        if operation_pid is not None:
            stmt = stmt.where(ProfileItem.operation_pid == operation_pid)
        rows = (await self._db.execute(stmt.order_by(ProfileItem.pid))).scalars()
        return list(rows.all())

    async def replace_profile_items(
        self,
        permission_profile_pid: int,
        operation_pid: int,
        items: Sequence[PermissionItem],
        *,
        actor_uid: UUID,
    ) -> list[ProfileItem]:
        """整批置換「角色權限設定檔 × 單一作業」的授權矩陣(同交易軟刪舊集合 + 插入新集合)。"""
        await self._soft_delete_where(
            update(ProfileItem).where(
                ProfileItem.permission_profile_pid == permission_profile_pid,
                ProfileItem.operation_pid == operation_pid,
                ProfileItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        rows = [
            ProfileItem(
                uid=uuid4(),
                permission_profile_pid=permission_profile_pid,
                operation_pid=operation_pid,
                table_name=item.table_name,
                column_name=item.column_name,
                action=item.action,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            for item in items
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    # ── Role roles ──────────────────────────────────────────────────────
    async def list_roles(self) -> list[Role]:
        rows = (
            await self._db.execute(
                select(Role).where(Role.is_deleted.is_(False)).order_by(Role.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_role_by_uid(self, uid: UUID) -> Role | None:
        return (
            await self._db.execute(
                select(Role).where(Role.uid == uid, Role.is_deleted.is_(False))
            )
        ).scalar_one_or_none()

    async def get_role_by_pid(self, pid: int) -> Role | None:
        return (
            await self._db.execute(
                select(Role).where(Role.pid == pid, Role.is_deleted.is_(False))
            )
        ).scalar_one_or_none()

    async def create_role(
        self,
        *,
        permission_profile_pid: int,
        name: str,
        description: str | None = None,
        actor_uid: UUID,
    ) -> Role:
        """建立角色;角色權限設定檔為必帶(DB 層 NOT NULL,禁空角色)。"""
        role = Role(
            uid=uuid4(),
            permission_profile_pid=permission_profile_pid,
            name=name,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(role)
        await self._db.flush()
        return role

    async def update_role(
        self,
        role: Role,
        *,
        name: str | None = None,
        description: str | None = None,
        permission_profile_pid: int | None = None,
        actor_uid: UUID,
    ) -> Role:
        """部分更新;可改綁角色權限設定檔,但 None 代表不變更 — 無法清空(必綁)。"""
        if name is not None:
            role.name = name
        if description is not None:
            role.description = description
        if permission_profile_pid is not None:
            role.permission_profile_pid = permission_profile_pid
        await self._touch(role, actor_uid)
        return role

    async def soft_delete_role(self, role: Role, *, actor_uid: UUID) -> None:
        await self._soft_delete(role, actor_uid)

    async def count_clients_by_role(self, role_pid: int) -> int:
        """指派該角色的未刪 Client 數(> 0 時 service 層擋刪除)。"""
        return await self._count(
            select(func.count())
            .select_from(ClientRole)
            .where(ClientRole.role_pid == role_pid, ClientRole.is_deleted.is_(False))
        )

    # ── API Client 的角色指派 client_roles ─────────────────────────────
    async def get_client_role(self, api_client_uid: UUID) -> ClientRole | None:
        """取 Client 目前的角色指派(0..1;partial unique 保證至多一筆有效)。"""
        return (
            await self._db.execute(
                select(ClientRole).where(
                    ClientRole.api_client_uid == api_client_uid,
                    ClientRole.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def list_client_roles_by_role_pids(
        self, role_pids: Sequence[int]
    ) -> list[ClientRole]:
        """指派這些角色的未刪指派列(權限異動時反查受影響 Client 的第二段)。"""
        if not role_pids:
            return []
        rows = (
            await self._db.execute(
                select(ClientRole)
                .where(
                    ClientRole.role_pid.in_(role_pids),
                    ClientRole.is_deleted.is_(False),
                )
                .order_by(ClientRole.pid)
            )
        ).scalars()
        return list(rows.all())

    async def assign_client_role(
        self, api_client_uid: UUID, role_pid: int, *, actor_uid: UUID
    ) -> ClientRole:
        """冪等置換指派:同交易先軟刪既有指派再插新列,恆維持至多 1 筆有效。"""
        await self.remove_client_role(api_client_uid, actor_uid=actor_uid)
        assignment = ClientRole(
            uid=uuid4(),
            api_client_uid=api_client_uid,
            role_pid=role_pid,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(assignment)
        await self._db.flush()
        return assignment

    async def remove_client_role(self, api_client_uid: UUID, *, actor_uid: UUID) -> bool:
        """解除指派;回傳是否確有解除(無指派時回 False,呼叫端可據以回 404)。"""
        assignment = await self.get_client_role(api_client_uid)
        if assignment is None:
            return False
        await self._soft_delete(assignment, actor_uid)
        return True

    async def soft_delete_client_grants(
        self, api_client_uid: UUID, *, actor_uid: UUID
    ) -> None:
        """同交易軟刪該 Client 在 RDS 的全部指派與綁定(API Client 註銷的跨庫連動)。

        自有 DB 的 Client 註銷後,RDS 側的 `client_roles` / `client_exception_sets` 若留著
        就成了解不掉的孤兒(角色 / 臨時權限組因而永久刪不掉),故註銷一併清除。
        """
        await self._soft_delete_where(
            update(ClientRole).where(
                ClientRole.api_client_uid == api_client_uid,
                ClientRole.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        await self._soft_delete_where(
            update(ClientExceptionSet).where(
                ClientExceptionSet.api_client_uid == api_client_uid,
                ClientExceptionSet.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )

    # ── 臨時權限組 exception_sets ────────────────────────────────────────
    async def list_exception_sets(self) -> list[ExceptionSet]:
        rows = (
            await self._db.execute(
                select(ExceptionSet)
                .where(ExceptionSet.is_deleted.is_(False))
                .order_by(ExceptionSet.pid)
            )
        ).scalars()
        return list(rows.all())

    async def list_exception_sets_by_pids(
        self, exception_set_pids: Sequence[int]
    ) -> list[ExceptionSet]:
        if not exception_set_pids:
            return []
        rows = (
            await self._db.execute(
                select(ExceptionSet)
                .where(
                    ExceptionSet.pid.in_(exception_set_pids),
                    ExceptionSet.is_deleted.is_(False),
                )
                .order_by(ExceptionSet.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_exception_set_by_uid(
        self, uid: UUID, *, for_update: bool = False
    ) -> ExceptionSet | None:
        return (
            await self._db.execute(
                self._lock(
                    select(ExceptionSet).where(
                        ExceptionSet.uid == uid, ExceptionSet.is_deleted.is_(False)
                    ),
                    for_update=for_update,
                )
            )
        ).scalar_one_or_none()

    async def create_exception_set(
        self, *, name: str, description: str | None = None, actor_uid: UUID
    ) -> ExceptionSet:
        exception_set = ExceptionSet(
            uid=uuid4(),
            name=name,
            description=description,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(exception_set)
        await self._db.flush()
        return exception_set

    async def update_exception_set(
        self,
        exception_set: ExceptionSet,
        *,
        name: str | None = None,
        description: str | None = None,
        actor_uid: UUID,
    ) -> ExceptionSet:
        if name is not None:
            exception_set.name = name
        if description is not None:
            exception_set.description = description
        await self._touch(exception_set, actor_uid)
        return exception_set

    async def soft_delete_exception_set(
        self, exception_set: ExceptionSet, *, actor_uid: UUID
    ) -> None:
        """軟刪臨時權限組並連動軟刪其勾選作業、授權項與殘留綁定。

        綁定列本非「內含子集合」,但未過期綁定在 service 層已擋刪(409)→ 走到這裡的只會是
        已過期綁定,對權限判斷本就不生效;留著會變成清單看不到、unbind 又 404 的殭屍列。
        """
        exception_set_pid = exception_set.pid
        await self._soft_delete(exception_set, actor_uid)
        await self._soft_delete_where(
            update(ExceptionOperation).where(
                ExceptionOperation.exception_set_pid == exception_set_pid,
                ExceptionOperation.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        await self._soft_delete_where(
            update(ExceptionItem).where(
                ExceptionItem.exception_set_pid == exception_set_pid,
                ExceptionItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        await self._soft_delete_where(
            update(ClientExceptionSet).where(
                ClientExceptionSet.exception_set_pid == exception_set_pid,
                ClientExceptionSet.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )

    async def count_active_bindings_by_exception_set(
        self, exception_set_pid: int, *, now: datetime | None = None
    ) -> int:
        """引用該臨時權限組且**未過期**的綁定數(`expires_at` NULL = 不設限)。"""
        moment = now if now is not None else db_now()
        return await self._count(
            select(func.count())
            .select_from(ClientExceptionSet)
            .where(
                ClientExceptionSet.exception_set_pid == exception_set_pid,
                ClientExceptionSet.is_deleted.is_(False),
                or_(
                    ClientExceptionSet.expires_at.is_(None),
                    ClientExceptionSet.expires_at > moment,
                ),
            )
        )

    # ── 臨時權限組勾選作業 / 授權項 ──────────────────────────────────────────
    async def list_exception_operations(
        self, exception_set_pid: int
    ) -> list[ExceptionOperation]:
        return await self.list_exception_operations_by_set_pids([exception_set_pid])

    async def list_exception_operations_by_set_pids(
        self, exception_set_pids: Sequence[int]
    ) -> list[ExceptionOperation]:
        """一次載入多臨時權限組的勾選作業(Client 可綁多組,避免逐組 N+1)。"""
        if not exception_set_pids:
            return []
        rows = (
            await self._db.execute(
                select(ExceptionOperation)
                .where(
                    ExceptionOperation.exception_set_pid.in_(exception_set_pids),
                    ExceptionOperation.is_deleted.is_(False),
                )
                .order_by(ExceptionOperation.pid)
            )
        ).scalars()
        return list(rows.all())

    async def replace_exception_operations(
        self,
        exception_set_pid: int,
        operation_pids: Sequence[int],
        *,
        actor_uid: UUID,
    ) -> list[ExceptionOperation]:
        """整批置換臨時權限組勾選作業;被移除的作業連動清其授權項(同交易)。"""
        previous = {
            row.operation_pid
            for row in await self.list_exception_operations(exception_set_pid)
        }
        await self._soft_delete_where(
            update(ExceptionOperation).where(
                ExceptionOperation.exception_set_pid == exception_set_pid,
                ExceptionOperation.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        removed = previous - set(operation_pids)
        if removed:
            await self._soft_delete_where(
                update(ExceptionItem).where(
                    ExceptionItem.exception_set_pid == exception_set_pid,
                    ExceptionItem.operation_pid.in_(removed),
                    ExceptionItem.is_deleted.is_(False),
                ),
                actor_uid=actor_uid,
            )
        rows = [
            ExceptionOperation(
                uid=uuid4(),
                exception_set_pid=exception_set_pid,
                operation_pid=operation_pid,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            for operation_pid in operation_pids
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    async def list_exception_items(
        self, exception_set_pid: int, *, operation_pid: int | None = None
    ) -> list[ExceptionItem]:
        stmt = select(ExceptionItem).where(
            ExceptionItem.exception_set_pid == exception_set_pid,
            ExceptionItem.is_deleted.is_(False),
        )
        if operation_pid is not None:
            stmt = stmt.where(ExceptionItem.operation_pid == operation_pid)
        rows = (await self._db.execute(stmt.order_by(ExceptionItem.pid))).scalars()
        return list(rows.all())

    async def list_exception_items_by_set_pids(
        self, exception_set_pids: Sequence[int]
    ) -> list[ExceptionItem]:
        """一次載入多臨時權限組的授權項(供最終權限展開)。"""
        if not exception_set_pids:
            return []
        rows = (
            await self._db.execute(
                select(ExceptionItem)
                .where(
                    ExceptionItem.exception_set_pid.in_(exception_set_pids),
                    ExceptionItem.is_deleted.is_(False),
                )
                .order_by(ExceptionItem.pid)
            )
        ).scalars()
        return list(rows.all())

    async def replace_exception_items(
        self,
        exception_set_pid: int,
        operation_pid: int,
        items: Sequence[PermissionItem],
        *,
        actor_uid: UUID,
    ) -> list[ExceptionItem]:
        """整批置換「臨時權限組 × 單一作業」的授權矩陣(同交易軟刪舊集合 + 插入新集合)。"""
        await self._soft_delete_where(
            update(ExceptionItem).where(
                ExceptionItem.exception_set_pid == exception_set_pid,
                ExceptionItem.operation_pid == operation_pid,
                ExceptionItem.is_deleted.is_(False),
            ),
            actor_uid=actor_uid,
        )
        rows = [
            ExceptionItem(
                uid=uuid4(),
                exception_set_pid=exception_set_pid,
                operation_pid=operation_pid,
                table_name=item.table_name,
                column_name=item.column_name,
                action=item.action,
                created_by=actor_uid,
                updated_by=actor_uid,
            )
            for item in items
        ]
        self._db.add_all(rows)
        await self._db.flush()
        return rows

    # ── API Client 的臨時權限綁定 client_exception_sets ──────────────────────
    async def list_client_exception_sets(
        self, api_client_uid: UUID
    ) -> list[ClientExceptionSet]:
        """該 Client 的全部未刪綁定(含已過期;過期與否由呼叫端依 `expires_at` 標示)。"""
        rows = (
            await self._db.execute(
                select(ClientExceptionSet)
                .where(
                    ClientExceptionSet.api_client_uid == api_client_uid,
                    ClientExceptionSet.is_deleted.is_(False),
                )
                .order_by(ClientExceptionSet.pid)
            )
        ).scalars()
        return list(rows.all())

    async def list_active_client_exception_sets(
        self, api_client_uid: UUID, *, now: datetime | None = None
    ) -> list[ClientExceptionSet]:
        """該 Client **未過期**的綁定(到期即自動失效,無需人工清理)。"""
        moment = now if now is not None else db_now()
        rows = (
            await self._db.execute(
                select(ClientExceptionSet)
                .where(
                    ClientExceptionSet.api_client_uid == api_client_uid,
                    ClientExceptionSet.is_deleted.is_(False),
                    or_(
                        ClientExceptionSet.expires_at.is_(None),
                        ClientExceptionSet.expires_at > moment,
                    ),
                )
                .order_by(ClientExceptionSet.pid)
            )
        ).scalars()
        return list(rows.all())

    async def list_client_exception_sets_by_set_pids(
        self, exception_set_pids: Sequence[int]
    ) -> list[ClientExceptionSet]:
        """綁定這些臨時權限組的未刪綁定列(臨時權限組內容異動時反查受影響 Client)。

        含已過期綁定:失效快取寧可多刪(過期綁定本就讀不到,多失效只是多一次回源)。
        """
        if not exception_set_pids:
            return []
        rows = (
            await self._db.execute(
                select(ClientExceptionSet)
                .where(
                    ClientExceptionSet.exception_set_pid.in_(exception_set_pids),
                    ClientExceptionSet.is_deleted.is_(False),
                )
                .order_by(ClientExceptionSet.pid)
            )
        ).scalars()
        return list(rows.all())

    async def get_client_exception_set_by_uid(self, uid: UUID) -> ClientExceptionSet | None:
        return (
            await self._db.execute(
                select(ClientExceptionSet).where(
                    ClientExceptionSet.uid == uid,
                    ClientExceptionSet.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()

    async def bind_client_exception_set(
        self,
        api_client_uid: UUID,
        exception_set_pid: int,
        *,
        expires_at: datetime | None = None,
        actor_uid: UUID,
    ) -> ClientExceptionSet:
        """綁定臨時權限組(0..N);`expires_at` 為 naive UTC+8,NULL = 不設限。

        同一 Client 重複綁同組由 partial unique 擋下(呼叫端轉 409)。
        """
        binding = ClientExceptionSet(
            uid=uuid4(),
            api_client_uid=api_client_uid,
            exception_set_pid=exception_set_pid,
            expires_at=expires_at,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(binding)
        await self._db.flush()
        return binding

    async def unbind_client_exception_set(
        self, binding: ClientExceptionSet, *, actor_uid: UUID
    ) -> None:
        await self._soft_delete(binding, actor_uid)
