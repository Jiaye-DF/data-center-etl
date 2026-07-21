"""語意映射管理 API(v1.5.1 task-004):讀寫目標 RDS `erp_metadata.semantic_mappings`。

- `GET /semantic-mappings`:分頁列表(表名精準 / 狀態 / 關鍵字篩選)。
- `GET /semantic-mappings/tables`:distinct 表名 + 各狀態計數(前端下拉)。
- `PATCH /semantic-mappings`:單列更新(english_name / zh_name / status;複合鍵定位)。
- `POST /semantic-mappings/confirm-table`:整表轉 confirmed。
- `POST /semantic-mappings/sync-views`:派工 worker 執行副本重灌 + view 重生
  (202 受理;進度輪詢 `GET /progress` 聚合端點,AD-122)。

全端點 admin-only(member 403);寫入類端點寫 audit_logs(AD-123)。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.exceptions import AppError
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.semantic_mapping import (
    SemanticAffectedResponse,
    SemanticConfirmTableRequest,
    SemanticMappingItem,
    SemanticMappingListResponse,
    SemanticMappingUpdateRequest,
    SemanticSyncViewsQueuedResponse,
    SemanticTableListResponse,
)
from app.services.audit_service import AuditService
from app.services.semantic_admin_service import SemanticAdminService
from app.worker.tasks import is_apply_in_progress, semantic_apply

router = APIRouter()

StatusFilter = Literal["all", "draft", "confirmed"]


@router.get(
    "",
    response_model=ApiResponse[SemanticMappingListResponse],
    summary="分頁列出語意映射(RDS 真身;表名精準 / 狀態 / 關鍵字篩選)",
)
async def list_mappings(
    _user: Annotated[User, Depends(require_admin)],
    table: Annotated[str, Query(max_length=128, description="表名精準篩選;空字串不篩")] = "",
    status: Annotated[StatusFilter, Query()] = "all",
    keyword: Annotated[
        str, Query(max_length=128, description="欄名 / 英文名 / 中文名子字串;空字串不篩")
    ] = "",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApiResponse[SemanticMappingListResponse]:
    data = await SemanticAdminService().list_mappings(
        table=table, status=status, keyword=keyword, page=page, page_size=page_size
    )
    return success(data=data)


@router.get(
    "/tables",
    response_model=ApiResponse[SemanticTableListResponse],
    summary="列出映射涵蓋的表名與 draft / confirmed 計數(下拉用)",
)
async def list_tables(
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticTableListResponse]:
    data = await SemanticAdminService().list_tables()
    return success(data=data)


@router.patch(
    "",
    response_model=ApiResponse[SemanticMappingItem],
    summary="更新單筆映射(english_name / zh_name / status;複合鍵定位)",
)
async def update_mapping(
    payload: SemanticMappingUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticMappingItem]:
    data = await SemanticAdminService().update_mapping(payload, actor_uid=user.uid)
    changed = sorted(payload.model_fields_set - {"table_name", "column_name"})
    await AuditService(db).log(
        action="semantic_mapping.update",
        actor_uid=user.uid,
        target_type="semantic_mapping",
        detail=(
            f"更新映射 {payload.table_name}.{payload.column_name or '(表層級)'}"
            f"(欄位:{', '.join(changed)})"
        ),
    )
    return success(data=data)


@router.post(
    "/confirm-table",
    response_model=ApiResponse[SemanticAffectedResponse],
    summary="整表轉 confirmed(對齊 seed 腳本 --confirm-table 語意)",
)
async def confirm_table(
    payload: SemanticConfirmTableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticAffectedResponse]:
    data = await SemanticAdminService().confirm_table(
        payload.table_name, actor_uid=user.uid
    )
    await AuditService(db).log(
        action="semantic_mapping.confirm_table",
        actor_uid=user.uid,
        target_type="semantic_mapping",
        detail=f"整表轉 confirmed:{payload.table_name}(affected={data.affected})",
    )
    return success(data=data)


@router.post(
    "/sync-views",
    response_model=ApiResponse[SemanticSyncViewsQueuedResponse],
    status_code=202,
    summary="手動套用變更:派工 worker 執行副本重灌 + view 重生(202 受理;進行中 409)",
)
async def sync_views(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticSyncViewsQueuedResponse]:
    # 派工前預檢(仍有微小 race 無妨,真互斥為 task 內 SET NX 鎖;AD-120)
    if await is_apply_in_progress():
        raise AppError("套用進行中,請稍後再試", response_code=409, status_code=409)
    await semantic_apply.kiq()
    await AuditService(db).log(
        action="semantic_mapping.sync_views",
        actor_uid=user.uid,
        target_type="semantic_mapping",
        detail="觸發套用變更(queued=true;副本重灌 + view 重生派工 worker)",
    )
    return success(data=SemanticSyncViewsQueuedResponse(queued=True), response_code=202)
