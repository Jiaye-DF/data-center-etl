"""語意映射管理 API(v1.5.1 task-004):讀寫目標 RDS `erp_metadata.semantic_mappings`。

- `GET /semantic-mappings`:分頁列表(表名精準 / 狀態 / 關鍵字篩選)。
- `GET /semantic-mappings/tables`:distinct 表名 + 各狀態計數(前端下拉)。
- `PATCH /semantic-mappings`:單列更新(english_name / zh_name / status;複合鍵定位)。
- `POST /semantic-mappings/confirm-table`:整表轉 confirmed。
- `POST /semantic-mappings/sync-views`:手動觸發副本重灌 + view 重生(即時生效)。

全端點 admin-only(member 403)。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.rawdata import SnapshotRefreshProgress
from app.schemas.response import ApiResponse
from app.schemas.semantic_mapping import (
    SemanticAffectedResponse,
    SemanticConfirmTableRequest,
    SemanticMappingItem,
    SemanticMappingListResponse,
    SemanticMappingUpdateRequest,
    SemanticSyncViewsResponse,
    SemanticTableListResponse,
)
from app.services.semantic_admin_service import SemanticAdminService

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
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticMappingItem]:
    data = await SemanticAdminService().update_mapping(payload, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/confirm-table",
    response_model=ApiResponse[SemanticAffectedResponse],
    summary="整表轉 confirmed(對齊 seed 腳本 --confirm-table 語意)",
)
async def confirm_table(
    payload: SemanticConfirmTableRequest,
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticAffectedResponse]:
    data = await SemanticAdminService().confirm_table(
        payload.table_name, actor_uid=user.uid
    )
    return success(data=data)


@router.post(
    "/sync-views",
    response_model=ApiResponse[SemanticSyncViewsResponse],
    summary="手動同步:RDS 真身 → 本地副本重灌 + confirmed 異動則重生 view(即時生效)",
)
async def sync_views(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SemanticSyncViewsResponse]:
    data = await SemanticAdminService().sync_views(db)
    return success(data=data)


@router.get(
    "/sync-views/progress",
    response_model=ApiResponse[SnapshotRefreshProgress],
    summary="查套用變更執行進度(讀 Redis;無進行中套用回 active=false)",
)
async def sync_views_progress(
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SnapshotRefreshProgress]:
    data = await SemanticAdminService().get_apply_progress()
    return success(data=data)
