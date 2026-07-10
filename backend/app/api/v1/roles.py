from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.role import RoleListResponse
from app.services.user_service import list_roles

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[RoleListResponse],
    summary="角色列表(已登入可讀,供前端下拉與後續權限整合)",
)
async def get_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[RoleListResponse]:
    return success(data=await list_roles(db))
