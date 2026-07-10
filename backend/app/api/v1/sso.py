"""DF-SSO 四端點:callback / me / logout / back-channel-logout。

契約:`docs/Design-Base/90-third-party-service/08-df-sso.md`(模式 B:本地帳密 + SSO 雙軌)。
與本地登入(task-002)共用同一 JWT httpOnly cookie;SSO 側 `/me` 每次即時回源中央(契約 #1)。
失敗回應的 detail 為契約錯誤碼(no_token / session_expired / sso_unreachable ...),供前端分流。
"""

from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.clients.df_sso import (
    DfSsoAuthError,
    DfSsoError,
    DfSsoUnreachableError,
    DfSsoUser,
    get_df_sso_client,
)
from app.core.config import get_settings
from app.core.cookies import JWT_COOKIE_NAME, clear_jwt_cookie, set_jwt_cookie
from app.core.response import failure, success
from app.core.security import decode_access_token
from app.repositories.user_repo import resolve_role_code
from app.schemas.response import ApiResponse
from app.services.audit_service import AuditService
from app.services.sso_service import (
    PROVIDER_SSO,
    SSO_SESSION_MAX_AGE_SECONDS,
    SsoService,
    create_sso_access_token,
    is_sso_session_revoked,
    revoke_sso_sessions,
    verify_back_channel_signature,
)

router = APIRouter()


class SsoMeResponse(BaseModel):
    """SSO 側 me 回應:本地使用者(角色以自有 users 表為準)+ 中央 user 原樣。"""

    uid: UUID
    username: str
    role: str
    provider: str
    sso_user: DfSsoUser


class BackChannelLogoutRequest(BaseModel):
    user_id: str
    timestamp: int
    signature: str


class BackChannelLogoutResponse(BaseModel):
    revoked: bool


@router.get(
    "/callback",
    response_class=RedirectResponse,
    summary="DF-SSO callback(code 換 token → 對應/建立本地使用者 → 設 cookie)",
)
async def callback(
    db: Annotated[AsyncSession, Depends(get_db)],
    code: str | None = None,
) -> RedirectResponse:
    settings = get_settings()
    login_url = f"{settings.FRONTEND_URL}/login"
    if not code:
        return RedirectResponse(url=f"{login_url}?error=no_code", status_code=302)
    try:
        user, sso_token = await SsoService(db).login_with_code(code)
    except DfSsoUnreachableError:
        return RedirectResponse(url=f"{login_url}?error=exchange_error", status_code=302)
    except DfSsoError:
        return RedirectResponse(url=f"{login_url}?error=exchange_failed", status_code=302)
    token = create_sso_access_token(
        user=user,
        sso_token=sso_token,
        secret_key=settings.JWT_SECRET_KEY,
        expires_minutes=SSO_SESSION_MAX_AGE_SECONDS // 60,
    )
    resp = RedirectResponse(url=f"{settings.FRONTEND_URL}/", status_code=302)
    # 契約:cookie Max-Age 固定 86400
    set_jwt_cookie(resp, token, max_age=SSO_SESSION_MAX_AGE_SECONDS)
    return resp


# response_model 僅供 OpenAPI 文件(R-BE-004);實作維持手動 JSONResponse(失敗分支多形)
@router.get(
    "/me",
    response_model=ApiResponse[SsoMeResponse],
    summary="SSO 側 me(每次即時回源中央,禁本地快取)",
)
async def sso_me(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    settings = get_settings()
    token = request.cookies.get(JWT_COOKIE_NAME)
    if token is None:
        return failure(detail="no_token", response_code=401, status_code=401)
    try:
        payload = decode_access_token(token, settings.JWT_SECRET_KEY)
    except jwt.PyJWTError:
        resp = failure(detail="invalid_token", response_code=401, status_code=401)
        clear_jwt_cookie(resp)
        return resp
    if payload.get("provider") != PROVIDER_SSO:
        # 本地登入 token 走 /api/v1/auth/me,不屬 SSO 側
        return failure(detail="not_sso_session", response_code=401, status_code=401)
    sso_token = payload.get("sso_token")
    sso_sub = payload.get("sso_sub")
    iat = payload.get("iat")
    if (
        not isinstance(sso_token, str)
        or not isinstance(sso_sub, str)
        or not isinstance(iat, int | float)
    ):
        resp = failure(detail="invalid_token", response_code=401, status_code=401)
        clear_jwt_cookie(resp)
        return resp
    if is_sso_session_revoked(sso_sub, float(iat)):
        # back-channel logout 已撤銷 → session 失效
        resp = failure(detail="session_expired", response_code=401, status_code=401)
        clear_jwt_cookie(resp)
        return resp
    try:
        sso_user = await get_df_sso_client().get_me(sso_token)
    except DfSsoAuthError:
        # 中央 401 → 刪本地 cookie(契約:JWT 有效 ≠ 中央 session 仍存在)
        resp = failure(detail="session_expired", response_code=401, status_code=401)
        clear_jwt_cookie(resp)
        return resp
    except DfSsoUnreachableError:
        # 中央不可達 → 502 且不刪 cookie(避免網路抖動踢人)
        return failure(detail="sso_unreachable", response_code=502, status_code=502)
    user = await SsoService(db).get_user_by_sso_subject(sso_sub)
    if user is None:
        resp = failure(detail="session_expired", response_code=401, status_code=401)
        clear_jwt_cookie(resp)
        return resp
    data = SsoMeResponse(
        uid=user.uid,
        username=user.username,
        role=resolve_role_code(user),
        provider=PROVIDER_SSO,
        sso_user=sso_user,
    )
    body = success(data=data)
    return JSONResponse(status_code=200, content=body.model_dump(mode="json"))


@router.get(
    "/logout",
    response_class=RedirectResponse,
    summary="SSO 登出(通知中央 → 跟隨 logout_url;不論成敗同一回應刪本地 cookie)",
)
async def sso_logout(request: Request) -> RedirectResponse:
    settings = get_settings()
    fallback = f"{settings.FRONTEND_URL}/login?logged_out=1"
    target = fallback
    token = request.cookies.get(JWT_COOKIE_NAME)
    if token is not None:
        payload: dict[str, object]
        try:
            payload = decode_access_token(token, settings.JWT_SECRET_KEY)
        except jwt.PyJWTError:
            payload = {}
        sso_token = payload.get("sso_token")
        if payload.get("provider") == PROVIDER_SSO and isinstance(sso_token, str):
            # 契約 #2:必先 POST 中央登出;取不到 logout_url 才落 fallback
            url = await get_df_sso_client().logout(sso_token, fallback)
            if url is not None:
                target = url
    resp = RedirectResponse(url=target, status_code=302)
    clear_jwt_cookie(resp)
    return resp


@router.post(
    "/back-channel-logout",
    summary="中央廣播登出(驗 HMAC + timestamp → 撤銷該使用者 SSO session)",
)
async def back_channel_logout(
    payload: BackChannelLogoutRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    settings = get_settings()
    if not settings.SSO_APP_SECRET:
        # 契約 #4:無驗證的裸端點比不註冊更糟 → secret 未設定時一律拒絕
        return failure(detail="sso_not_configured", response_code=503, status_code=503)
    ok, reason = verify_back_channel_signature(
        user_id=payload.user_id,
        timestamp=payload.timestamp,
        signature=payload.signature,
        app_secret=settings.SSO_APP_SECRET,
    )
    if not ok:
        return failure(detail=reason or "invalid_signature", response_code=401, status_code=401)
    # 模式 B:只撤銷 SSO 來源 session(本地登入使用者不受影響)
    revoke_sso_sessions(payload.user_id)
    # 稽核(R-PII-003):中央廣播撤銷,匿名事件;target 為中央 user_id(非 UUID → 記 detail)
    await AuditService(db).log(
        action="sso_revoke",
        target_type="sso_subject",
        detail=f"SSO 中央廣播登出:撤銷 user_id={payload.user_id} 的 SSO session",
    )
    body = success(data=BackChannelLogoutResponse(revoked=True))
    return JSONResponse(status_code=200, content=body.model_dump(mode="json"))
