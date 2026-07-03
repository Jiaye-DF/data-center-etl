from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.cookies import JWT_COOKIE_NAME
from app.core.db import AsyncSessionLocal
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth_service import AuthService

_INVALID_TOKEN_DETAIL = "登入憑證無效或已過期"


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    request: Request, db: Annotated[AsyncSession, Depends(get_db)]
) -> User:
    token = request.cookies.get(JWT_COOKIE_NAME)
    if token is None:
        raise AppError("未登入", response_code=401, status_code=401)
    settings = get_settings()
    try:
        payload = decode_access_token(token, settings.JWT_SECRET_KEY)
    except jwt.PyJWTError as exc:
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401) from exc
    try:
        uid = UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401) from exc
    user = await AuthService(db).get_user_by_uid(uid)
    if user is None:
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401)
    return user


# 已登入即可(admin / viewer 皆可讀)
require_login = get_current_user


def require_role(*roles: str) -> Callable[[User], Coroutine[object, object, User]]:
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise AppError("權限不足", response_code=403, status_code=403)
        return user

    return _dep


# admin 可寫;viewer 呼叫寫入類 API 一律 403
require_admin = require_role("admin")
