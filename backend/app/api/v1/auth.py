from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_login
from app.core.config import get_settings
from app.core.cookies import clear_jwt_cookie, set_jwt_cookie
from app.core.response import success
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutResponse, UserResponse
from app.schemas.response import ApiResponse
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/login",
    response_model=ApiResponse[UserResponse],
    summary="本地帳密登入(JWT httpOnly cookie)",
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[UserResponse]:
    user = await AuthService(db).authenticate(payload.username, payload.password)
    settings = get_settings()
    token = create_access_token(
        subject=str(user.uid),
        role=user.role,
        secret_key=settings.JWT_SECRET_KEY,
        expires_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    set_jwt_cookie(response, token, max_age=settings.JWT_EXPIRE_MINUTES * 60)
    return success(data=UserResponse.model_validate(user))


@router.post(
    "/logout",
    response_model=ApiResponse[LogoutResponse],
    summary="登出(清除 JWT cookie)",
)
async def logout(response: Response) -> ApiResponse[LogoutResponse]:
    clear_jwt_cookie(response)
    return success(data=LogoutResponse(message="已登出"))


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="目前登入者",
)
async def me(user: Annotated[User, Depends(require_login)]) -> ApiResponse[UserResponse]:
    return success(data=UserResponse.model_validate(user))
