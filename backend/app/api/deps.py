from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.df_sso import DfSsoAuthError, DfSsoUnreachableError, get_df_sso_client
from app.core.config import get_settings
from app.core.cookies import JWT_COOKIE_NAME
from app.core.db import AsyncSessionLocal
from app.core.exceptions import AppError
from app.core.security import decode_access_token
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.sso_service import PROVIDER_SSO, is_sso_session_revoked

_INVALID_TOKEN_DETAIL = "登入憑證無效或已過期"
_SSO_SESSION_EXPIRED_DETAIL = "SSO session 已失效,請重新登入"

PROVIDER_LOCAL = "local"


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _verify_sso_session(payload: dict[str, object]) -> None:
    """SSO 來源 token 一律即時回源中央驗證(08-df-sso.md 契約 #1,模式 B 守衛分流)。

    - back-channel logout 已撤銷 → 401
    - 中央 401(session 已清)→ 401;JWT 簽名有效 ≠ 中央 session 仍存在
    - 中央不可達 → 502(不視為登出,避免網路抖動踢人)
    """
    sso_token = payload.get("sso_token")
    sso_sub = payload.get("sso_sub")
    iat = payload.get("iat")
    if (
        not isinstance(sso_token, str)
        or not isinstance(sso_sub, str)
        or not isinstance(iat, int | float)
    ):
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401)
    if is_sso_session_revoked(sso_sub, float(iat)):
        raise AppError(_SSO_SESSION_EXPIRED_DETAIL, response_code=401, status_code=401)
    try:
        await get_df_sso_client().get_me(sso_token)
    except DfSsoAuthError as exc:
        raise AppError(
            _SSO_SESSION_EXPIRED_DETAIL, response_code=401, status_code=401
        ) from exc
    except DfSsoUnreachableError as exc:
        raise AppError(
            "SSO 中央不可達,請稍後再試", response_code=502, status_code=502
        ) from exc


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
    # 模式 B 守衛分流(fixed.md §8 收口):sso → 回源中央;local → 本地驗證
    provider = str(payload.get("provider", PROVIDER_LOCAL))
    if provider == PROVIDER_SSO:
        await _verify_sso_session(payload)
    try:
        uid = UUID(str(payload.get("sub")))
    except ValueError as exc:
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401) from exc
    user = await AuthService(db).get_user_by_uid(uid)
    if user is None:
        raise AppError(_INVALID_TOKEN_DETAIL, response_code=401, status_code=401)
    # 供 /auth/me 等端點回報登入來源(UserResponse.provider;fixed.md §13)
    request.state.auth_provider = provider
    return user


# 已登入即可(admin / member 皆可讀)
require_login = get_current_user


def require_role(*roles: str) -> Callable[[User], Coroutine[object, object, User]]:
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        # 授權判斷改自 roles 關聯(單一入口;get_current_user 已隨主查詢 eager load)
        if user.role not in roles:
            raise AppError("權限不足", response_code=403, status_code=403)
        return user

    return _dep


# admin 可寫;member 呼叫寫入類 API 一律 403
require_admin = require_role("admin")
