"""權限階層管理服務(v1.6.1 task-004 系統別 / 作業 / 作業範圍;task-005 設定檔 / Role)。

權限設定的唯一真身在目標 RDS `client_setting` schema(propose v1.6.1),本層負責維護面:

- **交易邊界**:repo 只 flush 不 commit,故寫入一律包在 `_rds_write()`(內部即
  `async with client_setting_session() as s, s.begin():`)——單交易全成或全不成;
  partial unique 違反(code / name 重複、範圍項重複)由該 helper 統一轉 409。
- **寫入順序(跨庫一致性,propose 風險欄)**:先 RDS 交易 commit 成功 → 才記稽核
  (自有 DB `audit_logs`)→ 才失效快取。順序顛倒會出現「稽核有、資料沒有」的假紀錄。
- **快取**:清單讀取一律走 `permission_cache` 的 cache-aside;失效扇出分兩種:
  - `_invalidate_wide()` — 系統別 / 作業 / 作業範圍異動牽動面廣(任一 Client 的最終權限
    都可能變),直接清空全部 effective,不逐一反查。
  - `_invalidate_narrow(client_uids)` — 設定檔 / Role 異動只影響「綁該設定檔的 Role →
    其 Client」,故於**寫入交易內**先反查受影響 Client uid,commit 後再逐一失效。
    受影響集合須在交易內取:commit 後改綁 / 解除指派會讓反查漏掉本次真正受影響的 Client。
- **semantic 驗證**:範圍項的表 / 欄位須存在於 RDS `erp_metadata.semantic_mappings`
  的 confirmed 映射(propose 對外承諾:無 confirmed 映射的表 / 欄位不可被授權)。
  該查詢為跨 schema 唯讀單表撈取,且本 task 檔案白名單無對應 repo,故比照
  `semantic_admin_service.py` / `api_client_service.py` 前例落在本層(識別字為白名單
  常值、值走 bind params,`04-databases/04-sql-safety.md`)。

task-006 於本檔續加特例權限組 / Client 指派的服務方法,共用下列 helper:
`_rds_read()` / `_rds_write()` / `_invalidate_wide()` / `_invalidate_narrow()` /
`_get_*_or_404()` / `_load_confirmed_semantic()` / `_validate_permission_items()`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.etl.comments import quote_ident
from app.etl.semantic_schema import SEMANTIC_SCHEMA, SEMANTIC_TABLE
from app.models.client_setting import (
    ALL_COLUMNS,
    Operation,
    OperationItem,
    PermissionProfile,
    ProfileItem,
    ProfileOperation,
    Role,
    Service,
)
from app.repositories.client_setting_repo import (
    ClientSettingRepository,
    PermissionItem,
    ScopeItem,
    client_setting_session,
)
from app.schemas.client_setting import (
    OperationCreateRequest,
    OperationItemListResponse,
    OperationItemResponse,
    OperationItemsReplaceRequest,
    OperationListResponse,
    OperationResponse,
    OperationUpdateRequest,
    PermissionAction,
    PermissionItemRequest,
    PermissionProfileCreateRequest,
    PermissionProfileListResponse,
    PermissionProfileResponse,
    PermissionProfileUpdateRequest,
    ProfileItemListResponse,
    ProfileItemResponse,
    ProfileItemsReplaceRequest,
    ProfileOperationListResponse,
    ProfileOperationResponse,
    ProfileOperationsReplaceRequest,
    RoleCreateRequest,
    RoleListResponse,
    RoleResponse,
    RoleUpdateRequest,
    ScopeItemRequest,
    ServiceCreateRequest,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdateRequest,
)
from app.services.audit_service import AuditService
from app.services.permission_cache import (
    get_or_load_model,
    invalidate_all_effective,
    invalidate_clients,
    invalidate_lists,
    list_key,
)

# 稽核 action / target_type(audit_logs 兩欄皆 String(50))
TARGET_TYPE_SERVICE = "client_setting_service"
TARGET_TYPE_OPERATION = "client_setting_operation"
TARGET_TYPE_PROFILE = "client_setting_profile"
TARGET_TYPE_ROLE = "client_setting_role"

_SERVICE_NOT_FOUND = "系統別不存在"
_OPERATION_NOT_FOUND = "作業不存在"
_PROFILE_NOT_FOUND = "權限設定檔不存在"
_ROLE_NOT_FOUND = "角色不存在"
_SERVICE_CODE_CONFLICT = "系統別代碼已存在"
_OPERATION_NAME_CONFLICT = "同一系統別下已有同名作業"
_PROFILE_NAME_CONFLICT = "權限設定檔名稱已存在"
_ROLE_NAME_CONFLICT = "角色名稱已存在"
_SERVICE_HAS_OPERATIONS = "系統別底下仍有作業,請先刪除作業"
_OPERATION_REFERENCED = "作業仍被權限設定檔或特例權限組引用,請先解除引用"
_PROFILE_HAS_ROLES = "權限設定檔仍被角色綁定,請先改綁或刪除角色"
_ROLE_HAS_CLIENTS = "角色仍被 API Client 指派,請先解除指派"
_OPERATION_NOT_GRANTED = "該作業尚未在此設定檔勾選,請先勾選作業再設定授權"
_SCOPE_ITEM_CONFLICT = "作業範圍項重複"
_PROFILE_OPERATION_CONFLICT = "勾選作業重複"
_PROFILE_ITEM_CONFLICT = "授權項重複"
# 作業範圍與授權矩陣共用同一句(兩者的表 / 欄位都須有 confirmed 語意映射)
_UNCONFIRMED_DETAIL = "下列表 / 欄位不存在於 confirmed 語意映射:{labels}"
# 刪除路徑理論上不觸唯一鍵,仍給通用訊息兜底(併發改名 / 復原等罕例)
_WRITE_CONFLICT = "資料異動衝突,請重新整理後再試"

_SEMANTIC_QUALIFIED = f"{quote_ident(SEMANTIC_SCHEMA)}.{quote_ident(SEMANTIC_TABLE)}"
_CONFIRMED_SEMANTIC_SQL = text(
    f"SELECT table_name, column_name, english_name FROM {_SEMANTIC_QUALIFIED}"
    " WHERE status = 'confirmed'"
)


# ── RDS 連線 / 交易 helper(task-005 / 006 共用)─────────────────────────
@asynccontextmanager
async def _rds_read() -> AsyncIterator[AsyncSession]:
    """RDS 唯讀 Session(不開交易);軟刪過濾由 repo 負責。"""
    async with client_setting_session() as session:
        yield session


@asynccontextmanager
async def _rds_write(conflict_detail: str) -> AsyncIterator[AsyncSession]:
    """RDS 寫入交易(單交易全成或全不成);唯一鍵衝突統一轉 409。"""
    try:
        async with client_setting_session() as session, session.begin():
            yield session
    except IntegrityError as exc:
        raise AppError(conflict_detail, response_code=409, status_code=409) from exc


async def _invalidate_wide() -> None:
    """系統別 / 作業 / 作業範圍異動的失效扇出:管理面清單 + 全部 Client 最終權限。

    這三者牽動任一 Client 的可見範圍,逐一反查成本高於直接清空,故整片失效
    (`permission_cache` 失效扇出對照表);本函式永不拋錯,不影響已完成的寫入。
    """
    await invalidate_lists()
    await invalidate_all_effective()


async def _invalidate_narrow(client_uids: Sequence[UUID]) -> None:
    """設定檔 / Role 異動的失效扇出:管理面清單 + 反查到的受影響 Client。

    `client_uids` 須由呼叫端**於寫入交易內**反查(見模組 docstring);空集合時只清清單。
    本函式永不拋錯,不影響已完成的寫入。
    """
    await invalidate_lists()
    await invalidate_clients(*client_uids)


async def _clients_of_roles(
    repo: ClientSettingRepository, role_pids: Sequence[int]
) -> list[UUID]:
    return [
        row.api_client_uid for row in await repo.list_client_roles_by_role_pids(role_pids)
    ]


async def _clients_of_profile(repo: ClientSettingRepository, profile_pid: int) -> list[UUID]:
    """設定檔 → 綁它的 Role → 指派這些 Role 的 Client(失效扇出的兩段反查)。"""
    roles = await repo.list_roles_by_profile(profile_pid)
    return await _clients_of_roles(repo, [role.pid for role in roles])


# ── 取件 / 轉換(task-005 / 006 共用)────────────────────────────────────
async def _get_service_or_404(repo: ClientSettingRepository, uid: UUID) -> Service:
    service = await repo.get_service_by_uid(uid)
    if service is None:
        raise AppError(_SERVICE_NOT_FOUND, response_code=404, status_code=404)
    return service


async def _get_operation_or_404(repo: ClientSettingRepository, uid: UUID) -> Operation:
    operation = await repo.get_operation_by_uid(uid)
    if operation is None:
        raise AppError(_OPERATION_NOT_FOUND, response_code=404, status_code=404)
    return operation


async def _get_permission_profile_or_404(
    repo: ClientSettingRepository, uid: UUID
) -> PermissionProfile:
    profile = await repo.get_permission_profile_by_uid(uid)
    if profile is None:
        raise AppError(_PROFILE_NOT_FOUND, response_code=404, status_code=404)
    return profile


async def _get_role_or_404(repo: ClientSettingRepository, uid: UUID) -> Role:
    role = await repo.get_role_by_uid(uid)
    if role is None:
        raise AppError(_ROLE_NOT_FOUND, response_code=404, status_code=404)
    return role


async def _service_uid_by_pid(repo: ClientSettingRepository) -> dict[int, UUID]:
    """系統別 pid → uid 對照(作業回應需以 uid 表達歸屬;系統別為小表,一次全撈)。"""
    return {service.pid: service.uid for service in await repo.list_services()}


async def _profile_uid_by_pid(repo: ClientSettingRepository) -> dict[int, UUID]:
    """設定檔 pid → uid 對照(Role 回應需以 uid 表達綁定;設定檔為小表,一次全撈)。"""
    return {profile.pid: profile.uid for profile in await repo.list_permission_profiles()}


async def _operation_uid_by_pid(repo: ClientSettingRepository) -> dict[int, UUID]:
    """作業 pid → uid 對照(勾選列回應需以 uid 表達;作業為小表,一次全撈免 N+1)。"""
    return {operation.pid: operation.uid for operation in await repo.list_operations()}


def _to_service(service: Service) -> ServiceResponse:
    return ServiceResponse(
        uid=service.uid,
        code=service.code,
        name=service.name,
        description=service.description,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def _to_operation(operation: Operation, service_uid: UUID) -> OperationResponse:
    return OperationResponse(
        uid=operation.uid,
        service_uid=service_uid,
        name=operation.name,
        description=operation.description,
        created_at=operation.created_at,
        updated_at=operation.updated_at,
    )


def _to_operation_item(item: OperationItem) -> OperationItemResponse:
    return OperationItemResponse(
        uid=item.uid, table_name=item.table_name, column_name=item.column_name
    )


def _to_item_list(items: Sequence[OperationItem]) -> OperationItemListResponse:
    return OperationItemListResponse(
        items=[_to_operation_item(item) for item in items], total=len(items)
    )


def _to_profile(profile: PermissionProfile) -> PermissionProfileResponse:
    return PermissionProfileResponse(
        uid=profile.uid,
        name=profile.name,
        description=profile.description,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _to_role(role: Role, permission_profile_uid: UUID) -> RoleResponse:
    return RoleResponse(
        uid=role.uid,
        permission_profile_uid=permission_profile_uid,
        name=role.name,
        description=role.description,
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


def _to_profile_operation_list(
    rows: Sequence[ProfileOperation], uid_by_pid: Mapping[int, UUID]
) -> ProfileOperationListResponse:
    return ProfileOperationListResponse(
        items=[
            ProfileOperationResponse(uid=row.uid, operation_uid=uid_by_pid[row.operation_pid])
            for row in rows
        ],
        total=len(rows),
    )


def _to_profile_item_list(rows: Sequence[ProfileItem]) -> ProfileItemListResponse:
    return ProfileItemListResponse(
        items=[
            ProfileItemResponse(
                uid=row.uid,
                table_name=row.table_name,
                column_name=row.column_name,
                # DB 端 CHECK 已限定 read / edit,取回時直接窄化為對外 Literal
                action=cast(PermissionAction, row.action),
            )
            for row in rows
        ],
        total=len(rows),
    )


# ── semantic 映射驗證 ───────────────────────────────────────────────────
async def _load_confirmed_semantic(session: AsyncSession) -> dict[str, set[str]]:
    """confirmed 語意映射 → `{表英文名: {欄位英文名}}`(一次全撈,禁逐項查詢 N+1)。

    表層級列(`column_name = ''`)的 `english_name` 即該表的英文名;沒有 confirmed
    表層級列的表視為尚未定稿 → 不可被授權(對齊 view 產生規則:無表層級英文名不產 view)。
    """
    rows = (await session.execute(_CONFIRMED_SEMANTIC_SQL)).all()
    english_table_by_raw: dict[str, str] = {}
    columns_by_raw: dict[str, set[str]] = {}
    for raw_table, raw_column, english_name in rows:
        if str(raw_column) == "":
            english_table_by_raw[str(raw_table)] = str(english_name)
        else:
            columns_by_raw.setdefault(str(raw_table), set()).add(str(english_name))
    confirmed: dict[str, set[str]] = {}
    for raw_table, english_table in english_table_by_raw.items():
        confirmed.setdefault(english_table, set()).update(columns_by_raw.get(raw_table, set()))
    return confirmed


def _validate_scope_items(
    items: Sequence[ScopeItemRequest], confirmed: Mapping[str, set[str]]
) -> list[ScopeItem]:
    """逐項檢核範圍(`*` 只驗表),非法項一次列明回 422(不逐次往返)。

    重複項先擋:唯一鍵雖會擋下,但那是 409 語意;同一次請求內自我重複屬輸入錯誤。
    """
    seen: set[tuple[str, str]] = set()
    duplicated: list[str] = []
    invalid: list[str] = []
    scope: list[ScopeItem] = []
    for item in items:
        key = (item.table_name, item.column_name)
        label = f"{item.table_name}.{item.column_name}"
        if key in seen:
            duplicated.append(label)
            continue
        seen.add(key)
        columns = confirmed.get(item.table_name)
        if columns is None or (
            item.column_name != ALL_COLUMNS and item.column_name not in columns
        ):
            invalid.append(label)
        scope.append(ScopeItem(table_name=item.table_name, column_name=item.column_name))
    if duplicated:
        raise AppError(
            f"範圍項重複:{'、'.join(duplicated)}", response_code=422, status_code=422
        )
    if invalid:
        raise AppError(
            _UNCONFIRMED_DETAIL.format(labels="、".join(invalid)),
            response_code=422,
            status_code=422,
        )
    return scope


def _scope_columns_by_table(scope: Sequence[OperationItem]) -> dict[str, set[str]]:
    """作業範圍 → `{表: {欄位}}`(含 `*`);未列入的表即完全不在範圍內。"""
    columns_by_table: dict[str, set[str]] = {}
    for item in scope:
        columns_by_table.setdefault(item.table_name, set()).add(item.column_name)
    return columns_by_table


def _within_scope(
    table_name: str, column_name: str, columns_by_table: Mapping[str, set[str]]
) -> bool:
    """授權項是否落在作業範圍上限內(default-closed)。

    範圍含該表的 `*` 即全欄位開放,任何授權欄位都通過;否則授權寫 `*` 反而不通過 ——
    `*` 代表全欄位,而作業只開放了列舉的部分欄位,授全欄位即超出上限。
    """
    columns = columns_by_table.get(table_name)
    if columns is None:
        return False
    if ALL_COLUMNS in columns:
        return True
    return column_name != ALL_COLUMNS and column_name in columns


def _validate_permission_items(
    items: Sequence[PermissionItemRequest],
    confirmed: Mapping[str, set[str]],
    scope: Sequence[OperationItem],
) -> list[PermissionItem]:
    """逐項檢核授權矩陣,非法項依類別一次列明回 422(`_validate_scope_items` 的姊妹函式)。

    `action` 合法性由 schema 的 Literal 擋在前面(FastAPI 自動 422),本函式只驗業務規則:
    重複項、confirmed 語意映射、以及**授權 ∩ 作業範圍上限**(propose:設定檔給不出作業
    範圍以外的東西)。
    """
    columns_by_table = _scope_columns_by_table(scope)
    seen: set[tuple[str, str, str]] = set()
    duplicated: list[str] = []
    unconfirmed: list[str] = []
    out_of_scope: list[str] = []
    granted: list[PermissionItem] = []
    for item in items:
        key = (item.table_name, item.column_name, item.action)
        label = f"{item.table_name}.{item.column_name}({item.action})"
        if key in seen:
            duplicated.append(label)
            continue
        seen.add(key)
        columns = confirmed.get(item.table_name)
        if columns is None or (
            item.column_name != ALL_COLUMNS and item.column_name not in columns
        ):
            unconfirmed.append(label)
        elif not _within_scope(item.table_name, item.column_name, columns_by_table):
            out_of_scope.append(label)
        granted.append(
            PermissionItem(
                table_name=item.table_name,
                column_name=item.column_name,
                action=item.action,
            )
        )
    if duplicated:
        raise AppError(
            f"授權項重複:{'、'.join(duplicated)}", response_code=422, status_code=422
        )
    if unconfirmed:
        raise AppError(
            _UNCONFIRMED_DETAIL.format(labels="、".join(unconfirmed)),
            response_code=422,
            status_code=422,
        )
    if out_of_scope:
        raise AppError(
            f"下列授權項超出作業範圍上限:{'、'.join(out_of_scope)}",
            response_code=422,
            status_code=422,
        )
    return granted


async def _resolve_operation_pids(
    repo: ClientSettingRepository, operation_uids: Sequence[UUID]
) -> list[int]:
    """勾選作業 uid → pid(保序);重複與不存在的作業各自一次列明回 422。

    作業為小表,一次全撈建對照(禁逐 uid 查詢 N+1)。
    """
    seen: set[UUID] = set()
    duplicated: list[str] = []
    ordered: list[UUID] = []
    for value in operation_uids:
        if value in seen:
            duplicated.append(str(value))
            continue
        seen.add(value)
        ordered.append(value)
    if duplicated:
        raise AppError(
            f"勾選作業重複:{'、'.join(duplicated)}", response_code=422, status_code=422
        )
    pid_by_uid = {
        operation.uid: operation.pid for operation in await repo.list_operations()
    }
    missing = [str(value) for value in ordered if value not in pid_by_uid]
    if missing:
        raise AppError(
            f"下列作業不存在:{'、'.join(missing)}", response_code=422, status_code=422
        )
    return [pid_by_uid[value] for value in ordered]


class ClientSettingService:
    """權限階層維護服務;`db` 為**自有 DB** session,只用於寫稽核(權限資料一律走 RDS)。"""

    def __init__(self, db: AsyncSession) -> None:
        self._audit = AuditService(db)

    # ── 系統別 ─────────────────────────────────────────────────────────
    async def list_services(self) -> ServiceListResponse:
        async def loader() -> ServiceListResponse:
            async with _rds_read() as session:
                rows = await ClientSettingRepository(session).list_services()
            return ServiceListResponse(
                items=[_to_service(row) for row in rows], total=len(rows)
            )

        return await get_or_load_model(list_key("services"), ServiceListResponse, loader)

    async def create_service(
        self, payload: ServiceCreateRequest, *, actor_uid: UUID
    ) -> ServiceResponse:
        async with _rds_write(_SERVICE_CODE_CONFLICT) as session:
            service = await ClientSettingRepository(session).create_service(
                code=payload.code,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            data = _to_service(service)
        await self._audit.log(
            action="client_setting.service_create",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_SERVICE,
            target_uid=data.uid,
            detail=f"建立系統別 {data.code}({data.name})",
        )
        await _invalidate_wide()
        return data

    async def update_service(
        self, uid: UUID, payload: ServiceUpdateRequest, *, actor_uid: UUID
    ) -> ServiceResponse:
        # 系統別唯一鍵只在 code,而 code 不開放 PATCH → 此路徑不會撞唯一鍵,給通用訊息
        async with _rds_write(_WRITE_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            service = await _get_service_or_404(repo, uid)
            await repo.update_service(
                service,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            data = _to_service(service)
        changed = ", ".join(sorted(payload.model_fields_set)) or "無"
        await self._audit.log(
            action="client_setting.service_update",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_SERVICE,
            target_uid=data.uid,
            detail=f"更新系統別 {data.code}(欄位:{changed})",
        )
        await _invalidate_wide()
        return data

    async def delete_service(self, uid: UUID, *, actor_uid: UUID) -> ServiceResponse:
        """軟刪系統別;底下仍有未刪作業一律擋下(不做連鎖刪除)。"""
        async with _rds_write(_WRITE_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            service = await _get_service_or_404(repo, uid)
            if await repo.count_operations_by_service(service.pid) > 0:
                raise AppError(_SERVICE_HAS_OPERATIONS, response_code=409, status_code=409)
            await repo.soft_delete_service(service, actor_uid=actor_uid)
            data = _to_service(service)
        await self._audit.log(
            action="client_setting.service_delete",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_SERVICE,
            target_uid=data.uid,
            detail=f"刪除系統別 {data.code}({data.name})",
        )
        await _invalidate_wide()
        return data

    # ── 作業 ───────────────────────────────────────────────────────────
    async def list_operations(
        self, *, service_uid: UUID | None = None
    ) -> OperationListResponse:
        async def loader() -> OperationListResponse:
            async with _rds_read() as session:
                repo = ClientSettingRepository(session)
                service_pid: int | None = None
                if service_uid is not None:
                    service_pid = (await _get_service_or_404(repo, service_uid)).pid
                rows = await repo.list_operations(service_pid=service_pid)
                uid_by_pid = await _service_uid_by_pid(repo)
            return OperationListResponse(
                items=[_to_operation(row, uid_by_pid[row.service_pid]) for row in rows],
                total=len(rows),
            )

        cache_key = list_key("operations", service_uid if service_uid is not None else "all")
        return await get_or_load_model(cache_key, OperationListResponse, loader)

    async def create_operation(
        self, payload: OperationCreateRequest, *, actor_uid: UUID
    ) -> OperationResponse:
        async with _rds_write(_OPERATION_NAME_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            service = await _get_service_or_404(repo, payload.service_uid)
            operation = await repo.create_operation(
                service_pid=service.pid,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            data = _to_operation(operation, service.uid)
            service_code = service.code
        await self._audit.log(
            action="client_setting.operation_create",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_OPERATION,
            target_uid=data.uid,
            detail=f"建立作業 {service_code}/{data.name}",
        )
        await _invalidate_wide()
        return data

    async def update_operation(
        self, uid: UUID, payload: OperationUpdateRequest, *, actor_uid: UUID
    ) -> OperationResponse:
        async with _rds_write(_OPERATION_NAME_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            operation = await _get_operation_or_404(repo, uid)
            await repo.update_operation(
                operation,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            uid_by_pid = await _service_uid_by_pid(repo)
            data = _to_operation(operation, uid_by_pid[operation.service_pid])
        changed = ", ".join(sorted(payload.model_fields_set)) or "無"
        await self._audit.log(
            action="client_setting.operation_update",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_OPERATION,
            target_uid=data.uid,
            detail=f"更新作業 {data.name}(欄位:{changed})",
        )
        await _invalidate_wide()
        return data

    async def delete_operation(self, uid: UUID, *, actor_uid: UUID) -> OperationResponse:
        """軟刪作業(連動軟刪其範圍項);被設定檔或特例組引用一律擋下。"""
        async with _rds_write(_WRITE_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            operation = await _get_operation_or_404(repo, uid)
            if await repo.count_profiles_referencing_operation(operation.pid) > 0:
                raise AppError(_OPERATION_REFERENCED, response_code=409, status_code=409)
            uid_by_pid = await _service_uid_by_pid(repo)
            service_uid = uid_by_pid[operation.service_pid]
            await repo.soft_delete_operation(operation, actor_uid=actor_uid)
            data = _to_operation(operation, service_uid)
        await self._audit.log(
            action="client_setting.operation_delete",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_OPERATION,
            target_uid=data.uid,
            detail=f"刪除作業 {data.name}(範圍項一併清除)",
        )
        await _invalidate_wide()
        return data

    # ── 作業範圍 ───────────────────────────────────────────────────────
    async def list_operation_items(self, uid: UUID) -> OperationItemListResponse:
        async def loader() -> OperationItemListResponse:
            async with _rds_read() as session:
                repo = ClientSettingRepository(session)
                operation = await _get_operation_or_404(repo, uid)
                rows = await repo.list_operation_items(operation.pid)
            return _to_item_list(rows)

        return await get_or_load_model(
            list_key("operation-items", uid), OperationItemListResponse, loader
        )

    async def replace_operation_items(
        self, uid: UUID, payload: OperationItemsReplaceRequest, *, actor_uid: UUID
    ) -> OperationItemListResponse:
        """整批置換作業範圍:同交易軟刪舊集合 + 插入新集合(空陣列 = 清空)。"""
        async with _rds_write(_SCOPE_ITEM_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            operation = await _get_operation_or_404(repo, uid)
            scope = _validate_scope_items(
                payload.items, await _load_confirmed_semantic(session)
            )
            rows = await repo.replace_operation_items(
                operation.pid, scope, actor_uid=actor_uid
            )
            data = _to_item_list(rows)
            operation_name = operation.name
        await self._audit.log(
            action="client_setting.operation_items_replace",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_OPERATION,
            target_uid=uid,
            detail=f"置換作業 {operation_name} 範圍(共 {data.total} 項)",
        )
        await _invalidate_wide()
        return data

    # ── 角色權限設定檔 ─────────────────────────────────────────────────
    async def list_permission_profiles(self) -> PermissionProfileListResponse:
        async def loader() -> PermissionProfileListResponse:
            async with _rds_read() as session:
                rows = await ClientSettingRepository(session).list_permission_profiles()
            return PermissionProfileListResponse(
                items=[_to_profile(row) for row in rows], total=len(rows)
            )

        return await get_or_load_model(
            list_key("permission-profiles"), PermissionProfileListResponse, loader
        )

    async def create_permission_profile(
        self, payload: PermissionProfileCreateRequest, *, actor_uid: UUID
    ) -> PermissionProfileResponse:
        async with _rds_write(_PROFILE_NAME_CONFLICT) as session:
            profile = await ClientSettingRepository(session).create_permission_profile(
                name=payload.name, description=payload.description, actor_uid=actor_uid
            )
            data = _to_profile(profile)
        await self._audit.log(
            action="client_setting.profile_create",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_PROFILE,
            target_uid=data.uid,
            detail=f"建立權限設定檔 {data.name}",
        )
        # 新建設定檔尚無 Role 綁定 → 無 Client 受影響,只需清清單
        await _invalidate_narrow([])
        return data

    async def update_permission_profile(
        self, uid: UUID, payload: PermissionProfileUpdateRequest, *, actor_uid: UUID
    ) -> PermissionProfileResponse:
        async with _rds_write(_PROFILE_NAME_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            profile = await _get_permission_profile_or_404(repo, uid)
            await repo.update_permission_profile(
                profile,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            data = _to_profile(profile)
            # 設定檔名進得了 effective 快取內容(task-007 預覽),改名同樣要失效
            affected = await _clients_of_profile(repo, profile.pid)
        changed = ", ".join(sorted(payload.model_fields_set)) or "無"
        await self._audit.log(
            action="client_setting.profile_update",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_PROFILE,
            target_uid=data.uid,
            detail=f"更新權限設定檔 {data.name}(欄位:{changed})",
        )
        await _invalidate_narrow(affected)
        return data

    async def delete_permission_profile(
        self, uid: UUID, *, actor_uid: UUID
    ) -> PermissionProfileResponse:
        """軟刪設定檔(勾選作業與授權項連動);仍被 Role 綁定一律擋下。"""
        async with _rds_write(_WRITE_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            profile = await _get_permission_profile_or_404(repo, uid)
            if await repo.count_roles_by_profile(profile.pid) > 0:
                raise AppError(_PROFILE_HAS_ROLES, response_code=409, status_code=409)
            await repo.soft_delete_permission_profile(profile, actor_uid=actor_uid)
            data = _to_profile(profile)
        await self._audit.log(
            action="client_setting.profile_delete",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_PROFILE,
            target_uid=data.uid,
            detail=f"刪除權限設定檔 {data.name}(勾選作業與授權項一併清除)",
        )
        # 無 Role 綁定才刪得掉(上方 409)→ 無 Client 受影響
        await _invalidate_narrow([])
        return data

    # ── 設定檔勾選作業 ─────────────────────────────────────────────────
    async def list_profile_operations(self, uid: UUID) -> ProfileOperationListResponse:
        async def loader() -> ProfileOperationListResponse:
            async with _rds_read() as session:
                repo = ClientSettingRepository(session)
                profile = await _get_permission_profile_or_404(repo, uid)
                rows = await repo.list_profile_operations(profile.pid)
                uid_by_pid = await _operation_uid_by_pid(repo)
            return _to_profile_operation_list(rows, uid_by_pid)

        return await get_or_load_model(
            list_key("profile-operations", uid), ProfileOperationListResponse, loader
        )

    async def replace_profile_operations(
        self, uid: UUID, payload: ProfileOperationsReplaceRequest, *, actor_uid: UUID
    ) -> ProfileOperationListResponse:
        """整批置換勾選作業;被移除的作業其授權項同交易一併清除(repo 層負責)。"""
        async with _rds_write(_PROFILE_OPERATION_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            profile = await _get_permission_profile_or_404(repo, uid)
            operation_pids = await _resolve_operation_pids(repo, payload.operation_uids)
            rows = await repo.replace_profile_operations(
                profile.pid, operation_pids, actor_uid=actor_uid
            )
            uid_by_pid = await _operation_uid_by_pid(repo)
            data = _to_profile_operation_list(rows, uid_by_pid)
            profile_name = profile.name
            affected = await _clients_of_profile(repo, profile.pid)
        await self._audit.log(
            action="client_setting.profile_operations_replace",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_PROFILE,
            target_uid=uid,
            detail=f"置換設定檔 {profile_name} 勾選作業(共 {data.total} 項)",
        )
        await _invalidate_narrow(affected)
        return data

    # ── 設定檔授權矩陣 ─────────────────────────────────────────────────
    async def list_profile_items(
        self, uid: UUID, operation_uid: UUID
    ) -> ProfileItemListResponse:
        async def loader() -> ProfileItemListResponse:
            async with _rds_read() as session:
                repo = ClientSettingRepository(session)
                profile = await _get_permission_profile_or_404(repo, uid)
                operation = await _get_operation_or_404(repo, operation_uid)
                rows = await repo.list_profile_items(
                    profile.pid, operation_pid=operation.pid
                )
            return _to_profile_item_list(rows)

        return await get_or_load_model(
            list_key("profile-items", uid, operation_uid), ProfileItemListResponse, loader
        )

    async def replace_profile_items(
        self,
        uid: UUID,
        operation_uid: UUID,
        payload: ProfileItemsReplaceRequest,
        *,
        actor_uid: UUID,
    ) -> ProfileItemListResponse:
        """整批置換「設定檔 × 單一作業」授權矩陣;作業須先被勾選(未勾選 409)。"""
        async with _rds_write(_PROFILE_ITEM_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            profile = await _get_permission_profile_or_404(repo, uid)
            operation = await _get_operation_or_404(repo, operation_uid)
            granted_pids = {
                row.operation_pid for row in await repo.list_profile_operations(profile.pid)
            }
            if operation.pid not in granted_pids:
                raise AppError(_OPERATION_NOT_GRANTED, response_code=409, status_code=409)
            items = _validate_permission_items(
                payload.items,
                await _load_confirmed_semantic(session),
                await repo.list_operation_items(operation.pid),
            )
            rows = await repo.replace_profile_items(
                profile.pid, operation.pid, items, actor_uid=actor_uid
            )
            data = _to_profile_item_list(rows)
            profile_name, operation_name = profile.name, operation.name
            affected = await _clients_of_profile(repo, profile.pid)
        await self._audit.log(
            action="client_setting.profile_items_replace",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_PROFILE,
            target_uid=uid,
            detail=(
                f"置換設定檔 {profile_name} / 作業 {operation_name} 授權(共 {data.total} 項)"
            ),
        )
        await _invalidate_narrow(affected)
        return data

    # ── Role ───────────────────────────────────────────────────────────
    async def list_roles(self) -> RoleListResponse:
        async def loader() -> RoleListResponse:
            async with _rds_read() as session:
                repo = ClientSettingRepository(session)
                rows = await repo.list_roles()
                uid_by_pid = await _profile_uid_by_pid(repo)
            return RoleListResponse(
                items=[
                    _to_role(row, uid_by_pid[row.permission_profile_pid]) for row in rows
                ],
                total=len(rows),
            )

        return await get_or_load_model(list_key("roles"), RoleListResponse, loader)

    async def create_role(self, payload: RoleCreateRequest, *, actor_uid: UUID) -> RoleResponse:
        """建立 Role;`permission_profile_uid` 為 schema 必填欄位(缺值即 422,禁空角色)。"""
        async with _rds_write(_ROLE_NAME_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            profile = await _get_permission_profile_or_404(
                repo, payload.permission_profile_uid
            )
            role = await repo.create_role(
                permission_profile_pid=profile.pid,
                name=payload.name,
                description=payload.description,
                actor_uid=actor_uid,
            )
            data = _to_role(role, profile.uid)
            profile_name = profile.name
        await self._audit.log(
            action="client_setting.role_create",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_ROLE,
            target_uid=data.uid,
            detail=f"建立角色 {data.name}(綁定設定檔 {profile_name})",
        )
        # 新建 Role 尚無 Client 指派 → 無 Client 受影響
        await _invalidate_narrow([])
        return data

    async def update_role(
        self, uid: UUID, payload: RoleUpdateRequest, *, actor_uid: UUID
    ) -> RoleResponse:
        """部分更新;可改綁設定檔,但不可清空(schema 擋顯式 null)。"""
        async with _rds_write(_ROLE_NAME_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            role = await _get_role_or_404(repo, uid)
            profile_pid: int | None = None
            profile_uid = payload.permission_profile_uid
            if profile_uid is not None:
                profile_pid = (
                    await _get_permission_profile_or_404(repo, profile_uid)
                ).pid
            await repo.update_role(
                role,
                name=payload.name,
                description=payload.description,
                permission_profile_pid=profile_pid,
                actor_uid=actor_uid,
            )
            uid_by_pid = await _profile_uid_by_pid(repo)
            data = _to_role(role, uid_by_pid[role.permission_profile_pid])
            affected = await _clients_of_roles(repo, [role.pid])
        changed = ", ".join(sorted(payload.model_fields_set)) or "無"
        await self._audit.log(
            action="client_setting.role_update",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_ROLE,
            target_uid=data.uid,
            detail=f"更新角色 {data.name}(欄位:{changed})",
        )
        await _invalidate_narrow(affected)
        return data

    async def delete_role(self, uid: UUID, *, actor_uid: UUID) -> RoleResponse:
        """軟刪 Role;仍被 API Client 指派一律擋下(不做連鎖解除指派)。"""
        async with _rds_write(_WRITE_CONFLICT) as session:
            repo = ClientSettingRepository(session)
            role = await _get_role_or_404(repo, uid)
            if await repo.count_clients_by_role(role.pid) > 0:
                raise AppError(_ROLE_HAS_CLIENTS, response_code=409, status_code=409)
            uid_by_pid = await _profile_uid_by_pid(repo)
            profile_uid = uid_by_pid[role.permission_profile_pid]
            await repo.soft_delete_role(role, actor_uid=actor_uid)
            data = _to_role(role, profile_uid)
        await self._audit.log(
            action="client_setting.role_delete",
            actor_uid=actor_uid,
            target_type=TARGET_TYPE_ROLE,
            target_uid=data.uid,
            detail=f"刪除角色 {data.name}",
        )
        # 無 Client 指派才刪得掉(上方 409)→ 無 Client 受影響
        await _invalidate_narrow([])
        return data
