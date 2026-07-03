from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.etl_config import (
    EtlMappingsUpdateRequest,
    EtlTableCreateRequest,
    EtlTableDeleteResponse,
    EtlTableDetailResponse,
    EtlTableListResponse,
    EtlTableUpdateRequest,
)
from app.schemas.response import ApiResponse
from app.services.etl_config_service import EtlConfigService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[EtlTableListResponse],
    summary="ETL 納管表清單(分頁,含啟用狀態與最近執行狀態)",
)
async def list_etl_tables(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[EtlTableListResponse]:
    data = await EtlConfigService(db).list_tables(page=page, page_size=page_size)
    return success(data=data)


@router.get(
    "/{uid}",
    response_model=ApiResponse[EtlTableDetailResponse],
    summary="單表明細(含 mapping 與欄位 Comment)",
)
async def get_etl_table(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[EtlTableDetailResponse]:
    return success(data=await EtlConfigService(db).get_table_detail(uid))


@router.post(
    "",
    response_model=ApiResponse[EtlTableDetailResponse],
    status_code=201,
    summary="納管新表(可一併帶 mapping,每欄位必帶 Comment)",
)
async def create_etl_table(
    payload: EtlTableCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDetailResponse]:
    data = await EtlConfigService(db).create_table(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/{uid}",
    response_model=ApiResponse[EtlTableDetailResponse],
    summary="更新表設定(目標 schema / 表名 / 描述)",
)
async def update_etl_table(
    uid: UUID,
    payload: EtlTableUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDetailResponse]:
    data = await EtlConfigService(db).update_table(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/{uid}",
    response_model=ApiResponse[EtlTableDeleteResponse],
    summary="移除納管(軟刪除,連同 mapping)",
)
async def delete_etl_table(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDeleteResponse]:
    await EtlConfigService(db).delete_table(uid, actor_uid=user.uid)
    return success(data=EtlTableDeleteResponse(message="已移除納管"))


@router.post(
    "/{uid}/enable",
    response_model=ApiResponse[EtlTableDetailResponse],
    summary="啟用表(恢復排程處理)",
)
async def enable_etl_table(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDetailResponse]:
    data = await EtlConfigService(db).set_enabled(uid, enabled=True, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/{uid}/disable",
    response_model=ApiResponse[EtlTableDetailResponse],
    summary="停用表(停用表不處理)",
)
async def disable_etl_table(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDetailResponse]:
    data = await EtlConfigService(db).set_enabled(uid, enabled=False, actor_uid=user.uid)
    return success(data=data)


@router.put(
    "/{uid}/mappings",
    response_model=ApiResponse[EtlTableDetailResponse],
    summary="全量更新 mapping(欄位對照 + Comment;缺 Comment 回 400)",
)
async def replace_etl_table_mappings(
    uid: UUID,
    payload: EtlMappingsUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EtlTableDetailResponse]:
    data = await EtlConfigService(db).replace_mappings(
        uid, payload.mappings, actor_uid=user.uid
    )
    return success(data=data)
