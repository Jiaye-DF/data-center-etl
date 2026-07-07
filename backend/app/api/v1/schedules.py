from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.schedule import (
    ScheduleBatchEnabledRequest,
    ScheduleBatchEnabledResponse,
    ScheduleResponse,
    ScheduleSchemaSummaryListResponse,
    ScheduleTableViewListResponse,
    ScheduleUpdateRequest,
)
from app.services.schedule_service import ScheduleService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[ScheduleTableViewListResponse],
    summary="逐表視角清單(指定 schema;分頁 + 啟停 / 上次結果 / 關鍵字過濾)",
)
async def list_tables_view(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    schema: Annotated[str, Query(min_length=1, description="來源表 schema(必填)")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    enabled: Annotated[str, Query(description="all / enabled / disabled")] = "all",
    last_result: Annotated[
        str, Query(description="all / success / failed / never(其餘 status 亦以字面比對)")
    ] = "all",
    keyword: Annotated[str, Query(description="對表名 / 業務名 ILIKE 子字串過濾")] = "",
) -> ApiResponse[ScheduleTableViewListResponse]:
    data = await ScheduleService(db).list_tables_view(
        schema=schema,
        page=page,
        page_size=page_size,
        enabled=enabled,
        last_result=last_result,
        keyword=keyword,
    )
    return success(data=data)


@router.get(
    "/schemas",
    response_model=ApiResponse[ScheduleSchemaSummaryListResponse],
    summary="各 schema 摘要(表數 / 已啟用排程數)",
)
async def list_schema_summaries(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[ScheduleSchemaSummaryListResponse]:
    return success(data=await ScheduleService(db).list_schema_summaries())


@router.patch(
    "/{uid}",
    response_model=ApiResponse[ScheduleResponse],
    summary="更新排程(cron / 啟停 / 描述;禁改綁定來源表)",
)
async def update_schedule(
    uid: UUID,
    payload: ScheduleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleResponse]:
    data = await ScheduleService(db).update_schedule(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/{uid}/enable",
    response_model=ApiResponse[ScheduleResponse],
    summary="啟用排程",
)
async def enable_schedule(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleResponse]:
    data = await ScheduleService(db).set_enabled(uid, enabled=True, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/{uid}/disable",
    response_model=ApiResponse[ScheduleResponse],
    summary="停用排程(停用排程不派工)",
)
async def disable_schedule(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleResponse]:
    data = await ScheduleService(db).set_enabled(uid, enabled=False, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/batch-enabled",
    response_model=ApiResponse[ScheduleBatchEnabledResponse],
    summary="批次啟停(全部來源表排程,或僅作用於符合篩選者)",
)
async def batch_set_enabled(
    payload: ScheduleBatchEnabledRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleBatchEnabledResponse]:
    data = await ScheduleService(db).batch_set_enabled(
        schema=payload.schema_name,
        enabled=payload.enabled,
        actor_uid=user.uid,
        filter_enabled=payload.filter_enabled,
        filter_last_result=payload.filter_last_result,
        filter_keyword=payload.filter_keyword,
    )
    return success(data=data)
