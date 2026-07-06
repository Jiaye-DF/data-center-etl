from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.audit import AuditLogListResponse
from app.schemas.response import ApiResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[AuditLogListResponse],
    summary="稽核紀錄清單(admin 專用;分頁,最新在前,可依事件類型過濾)",
)
async def list_audit_logs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    action: Annotated[str | None, Query(max_length=50)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[AuditLogListResponse]:
    data = await AuditService(db).list_logs(page=page, page_size=page_size, action=action)
    return success(data=data)
