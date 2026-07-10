from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.user import RoleAssignRequest, UserListItemResponse, UserListResponse
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[UserListResponse],
    summary="使用者清單(admin 專用;分頁)",
)
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[UserListResponse]:
    data = await UserService(db).list_users(page=page, page_size=page_size)
    return success(data=data)


@router.patch(
    "/{uid}/role",
    response_model=ApiResponse[UserListItemResponse],
    summary="指派使用者角色(admin 專用;自降防呆 + 稽核 + dual-write)",
)
async def assign_user_role(
    uid: UUID,
    payload: RoleAssignRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[UserListItemResponse]:
    data = await UserService(db).assign_role(uid, payload.role, actor=user)
    return success(data=data)
