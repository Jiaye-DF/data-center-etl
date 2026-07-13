from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_login
from app.core.config import get_settings
from app.core.cookies import JWT_COOKIE_NAME, clear_jwt_cookie, set_jwt_cookie
from app.core.response import success
from app.core.security import create_access_token, decode_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, LogoutResponse, UserResponse
from app.schemas.response import ApiResponse
from app.services.audit_service import AuditService
from app.services.auth_service import AuthService

router = APIRouter()


async def _resolve_logout_actor(request: Request, db: AsyncSession) -> User | None:
    """登出不強制登入(清 cookie 一律成功);cookie 可解析出使用者時才記稽核 actor。"""
    token = request.cookies.get(JWT_COOKIE_NAME)
    if token is None:
        return None
    try:
        payload = decode_access_token(token, get_settings().JWT_SECRET_KEY)
    except jwt.PyJWTError:
        return None
    try:
        uid = UUID(str(payload.get("sub")))
    except ValueError:
        return None
    return await AuthService(db).get_user_by_uid(uid)


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
    role_code = user.role
    token = create_access_token(
        subject=str(user.uid),
        role=role_code,
        secret_key=settings.JWT_SECRET_KEY,
        expires_minutes=settings.JWT_EXPIRE_MINUTES,
    )
    set_jwt_cookie(response, token, max_age=settings.JWT_EXPIRE_MINUTES * 60)
    return success(
        data=UserResponse(
            uid=user.uid,
            username=user.username,
            display_name=user.display_name,
            role=role_code,
        )
    )


@router.post(
    "/logout",
    response_model=ApiResponse[LogoutResponse],
    summary="登出(清除 JWT cookie)",
)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[LogoutResponse]:
    actor = await _resolve_logout_actor(request, db)
    if actor is not None:
        await AuditService(db).log(
            action="logout",
            actor_uid=actor.uid,
            actor_username=actor.username,
            detail="登出(清除 JWT cookie)",
        )
    clear_jwt_cookie(response)
    return success(data=LogoutResponse(message="已登出"))


@router.get(
    "/me",
    response_model=ApiResponse[UserResponse],
    summary="目前登入者",
)
async def me(
    request: Request, user: Annotated[User, Depends(require_login)]
) -> ApiResponse[UserResponse]:
    # provider 由守衛自 JWT payload 判定後掛 request.state(deps.get_current_user)
    provider = str(getattr(request.state, "auth_provider", "local"))
    return success(
        data=UserResponse(
            uid=user.uid,
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            provider=provider,
        )
    )
