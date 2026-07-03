from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.run import (
    RunListResponse,
    RunLogListResponse,
    RunSummaryResponse,
    RunTriggerRequest,
    RunTriggerResponse,
)
from app.services.schedule_service import RunService

router = APIRouter()

# 狀態過濾值對齊 etl_runs / etl_run_logs 的 CHECK 約束;非法值由 FastAPI 回 422
RunStatus = Literal["pending", "running", "success", "partial", "failed"]
RunLogStatus = Literal["pending", "running", "success", "failed", "skipped"]
TriggerType = Literal["schedule", "manual"]


@router.get(
    "",
    response_model=ApiResponse[RunListResponse],
    summary="執行紀錄清單(狀態 / 觸發方式過濾,分頁,最新在前)",
)
async def list_runs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    status: Annotated[RunStatus | None, Query()] = None,
    trigger_type: Annotated[TriggerType | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[RunListResponse]:
    data = await RunService(db).list_runs(
        page=page, page_size=page_size, status=status, trigger_type=trigger_type
    )
    return success(data=data)


@router.post(
    "/trigger",
    response_model=ApiResponse[RunTriggerResponse],
    summary="手動觸發一次 ETL 執行(enqueue 至 taskiq)",
)
async def trigger_run(
    payload: RunTriggerRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[RunTriggerResponse]:
    return success(data=await RunService(db).trigger_manual(payload))


@router.get(
    "/{uid}",
    response_model=ApiResponse[RunSummaryResponse],
    summary="單次執行明細(狀態 / 起訖 / 逐表統計)",
)
async def get_run(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[RunSummaryResponse]:
    return success(data=await RunService(db).get_run(uid))


@router.get(
    "/{uid}/logs",
    response_model=ApiResponse[RunLogListResponse],
    summary="單次執行逐表詳細 log(表名 / 筆數 / 耗時 / 狀態 / 錯誤明細,支援依狀態過濾)",
)
async def list_run_logs(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    status: Annotated[RunLogStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[RunLogListResponse]:
    data = await RunService(db).list_run_logs(
        uid, page=page, page_size=page_size, status=status
    )
    return success(data=data)
