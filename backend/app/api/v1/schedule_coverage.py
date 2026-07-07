from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.schedule_coverage import (
    CoverageListResponse,
    CoverageSchemaListResponse,
    ExclusionToggleRequest,
    TableCoverageItem,
)
from app.services.schedule_coverage_service import ScheduleCoverageService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[CoverageListResponse],
    summary="依表檢視:指定 schema 的來源表涵蓋清單(分頁)",
)
async def list_table_coverage(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
    schema: Annotated[str, Query(min_length=1, description="來源 schema 名稱")],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    inclusion: Annotated[
        str, Query(description="納入篩選:all / included / excluded")
    ] = "all",
    last_result: Annotated[
        str, Query(description="上次結果篩選:all / success / failed / never")
    ] = "all",
    keyword: Annotated[
        str, Query(description="表名 / 業務名關鍵字(子字串比對)")
    ] = "",
) -> ApiResponse[CoverageListResponse]:
    data = await ScheduleCoverageService(db).list_tables(
        schema,
        page=page,
        page_size=page_size,
        inclusion=inclusion,
        last_result=last_result,
        keyword=keyword,
    )
    return success(data=data)


@router.get(
    "/schemas",
    response_model=ApiResponse[CoverageSchemaListResponse],
    summary="依表檢視:各 schema 涵蓋概況 + 目前套用排程",
)
async def list_schema_coverage(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[CoverageSchemaListResponse]:
    data = await ScheduleCoverageService(db).list_schemas()
    return success(data=data)


@router.patch(
    "/tables/{uid}/exclusion",
    response_model=ApiResponse[TableCoverageItem],
    summary="逐表切換增量同步排除(true=排除 / false=納入)",
)
async def set_table_exclusion(
    uid: UUID,
    payload: ExclusionToggleRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[TableCoverageItem]:
    data = await ScheduleCoverageService(db).set_exclusion(
        uid, excluded=payload.excluded, actor_uid=user.uid
    )
    return success(data=data)
