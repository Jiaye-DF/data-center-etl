"""權限階層管理服務(v1.6.1 task-004:系統別 / 作業 / 作業範圍)。

權限設定的唯一真身在目標 RDS `client_setting` schema(propose v1.6.1),本層負責維護面:

- **交易邊界**:repo 只 flush 不 commit,故寫入一律包在 `_rds_write()`(內部即
  `async with client_setting_session() as s, s.begin():`)——單交易全成或全不成;
  partial unique 違反(code / name 重複、範圍項重複)由該 helper 統一轉 409。
- **寫入順序(跨庫一致性,propose 風險欄)**:先 RDS 交易 commit 成功 → 才記稽核
  (自有 DB `audit_logs`)→ 才失效快取。順序顛倒會出現「稽核有、資料沒有」的假紀錄。
- **快取**:清單讀取一律走 `permission_cache` 的 cache-aside;系統別 / 作業 / 作業範圍
  的異動牽動面廣(任一 Client 的最終權限都可能變),失效扇出固定為
  `invalidate_lists()` + `invalidate_all_effective()`,不逐一反查受影響 Client。
- **semantic 驗證**:範圍項的表 / 欄位須存在於 RDS `erp_metadata.semantic_mappings`
  的 confirmed 映射(propose 對外承諾:無 confirmed 映射的表 / 欄位不可被授權)。
  該查詢為跨 schema 唯讀單表撈取,且本 task 檔案白名單無對應 repo,故比照
  `semantic_admin_service.py` / `api_client_service.py` 前例落在本層(識別字為白名單
  常值、值走 bind params,`04-databases/04-sql-safety.md`)。

task-005 / 006 於本檔續加設定檔 / Role / 特例權限組的服務方法,共用下列 helper:
`_rds_read()` / `_rds_write()` / `_invalidate_wide()` / `_get_*_or_404()`。
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.etl.comments import quote_ident
from app.etl.semantic_schema import SEMANTIC_SCHEMA, SEMANTIC_TABLE
from app.models.client_setting import ALL_COLUMNS, Operation, OperationItem, Service
from app.repositories.client_setting_repo import (
    ClientSettingRepository,
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
    invalidate_lists,
    list_key,
)

# 稽核 action / target_type(audit_logs 兩欄皆 String(50))
TARGET_TYPE_SERVICE = "client_setting_service"
TARGET_TYPE_OPERATION = "client_setting_operation"

_SERVICE_NOT_FOUND = "系統別不存在"
_OPERATION_NOT_FOUND = "作業不存在"
_SERVICE_CODE_CONFLICT = "系統別代碼已存在"
_OPERATION_NAME_CONFLICT = "同一系統別下已有同名作業"
_SERVICE_HAS_OPERATIONS = "系統別底下仍有作業,請先刪除作業"
_OPERATION_REFERENCED = "作業仍被權限設定檔或特例權限組引用,請先解除引用"
_SCOPE_ITEM_CONFLICT = "作業範圍項重複"
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


async def _service_uid_by_pid(repo: ClientSettingRepository) -> dict[int, UUID]:
    """系統別 pid → uid 對照(作業回應需以 uid 表達歸屬;系統別為小表,一次全撈)。"""
    return {service.pid: service.uid for service in await repo.list_services()}


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
            f"下列表 / 欄位不存在於 confirmed 語意映射:{'、'.join(invalid)}",
            response_code=422,
            status_code=422,
        )
    return scope


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
