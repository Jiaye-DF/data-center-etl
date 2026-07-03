from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.schedule import (
    ScheduleCreateRequest,
    ScheduleDeleteResponse,
    ScheduleListResponse,
    ScheduleResponse,
    ScheduleUpdateRequest,
)
from app.services.schedule_service import ScheduleService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[ScheduleListResponse],
    summary="排程清單(分頁)",
)
async def list_schedules(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[ScheduleListResponse]:
    data = await ScheduleService(db).list_schedules(page=page, page_size=page_size)
    return success(data=data)


@router.get(
    "/{uid}",
    response_model=ApiResponse[ScheduleResponse],
    summary="單一排程明細",
)
async def get_schedule(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[ScheduleResponse]:
    return success(data=await ScheduleService(db).get_schedule(uid))


@router.post(
    "",
    response_model=ApiResponse[ScheduleResponse],
    status_code=201,
    summary="建立排程(cron 式定義,時間一律 UTC+8)",
)
async def create_schedule(
    payload: ScheduleCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleResponse]:
    data = await ScheduleService(db).create_schedule(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/{uid}",
    response_model=ApiResponse[ScheduleResponse],
    summary="更新排程(名稱 / cron / 指定表 / 描述)",
)
async def update_schedule(
    uid: UUID,
    payload: ScheduleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleResponse]:
    data = await ScheduleService(db).update_schedule(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/{uid}",
    response_model=ApiResponse[ScheduleDeleteResponse],
    summary="刪除排程(軟刪除;scheduler 即不再派工)",
)
async def delete_schedule(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ScheduleDeleteResponse]:
    await ScheduleService(db).delete_schedule(uid, actor_uid=user.uid)
    return success(data=ScheduleDeleteResponse(message="排程已刪除"))


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
