from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_login
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.role import RoleListResponse
from app.services.user_service import list_roles

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[RoleListResponse],
    summary="角色列表(已登入可讀;固定 admin / member,供前端下拉)",
)
async def get_roles(
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[RoleListResponse]:
    return success(data=list_roles())
