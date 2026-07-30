"""對外 API Client v1.0:Client Credentials 換發短效 JWT + 語意刷新。

- 兩端點安全等價(不發 refresh token);`/refresh_token` 只是「舊 token 過期後再換一把」的語意入口。
- 失敗一律 `invalid_client`:不存在 / 停用 / 軟刪 / 密錯 / 舊 token 不過的回應體完全同構(防列舉)。
- 對外層無 service(單一唯讀查詢即完成驗證),依 task-004 白名單直呼 repository;
  session 沿用 `api.deps.get_db`(專案唯一 session 生命週期,不含後台認證邏輯)。
"""

import logging
from collections.abc import Callable, Coroutine
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api_client_router.common.auth import is_refreshable_token, sign_client_jwt
from app.api_client_router.common.envelope import (
    ClientEnvelope,
    client_error,
    client_success,
)
from app.api_client_router.common.rate_limit import (
    DEFAULT_LIMIT_PER_10MIN,
    DEFAULT_LIMIT_PER_MINUTE,
    check_auth_lock,
    check_rate_limit,
    clear_auth_failures,
    register_auth_failure,
)
from app.api_client_router.common.schemas import RefreshTokenRequest, TokenRequest
from app.api_client_router.versions.registry import mount_version
from app.core.security import verify_password_async
from app.models.api_client_secret import ApiClientSecret
from app.models.api_client_user import CLIENT_STATUS_ENABLED, ApiClientUser
from app.repositories.api_client_repo import ApiClientRepository

logger = logging.getLogger(__name__)

VERSION = "v1.0"

INVALID_CLIENT_DETAIL = "invalid_client"
INVALID_REQUEST_DETAIL = "invalid_request"
RATE_LIMITED_DETAIL = "rate_limited"
INTERNAL_ERROR_DETAIL = "internal_error"

TOKEN_TYPE_BEARER = "Bearer"

_ClientRecord = tuple[ApiClientUser, list[ApiClientSecret]]


class ClientEnvelopeRoute(APIRoute):
    """對外路由:schema 錯誤與未捕獲例外改走統一封套(全域 handler 回的是後台外殼)。"""

    def get_route_handler(self) -> Callable[[Request], Coroutine[object, object, Response]]:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError:
                return client_error(INVALID_REQUEST_DETAIL, response_code=422)
            except HTTPException:
                raise
            except Exception:
                logger.exception("api-client 端點未預期錯誤 path=%s", request.url.path)
                return client_error(INTERNAL_ERROR_DETAIL, response_code=500)

        return handler


router = APIRouter(route_class=ClientEnvelopeRoute)


def _rate_limited(retry_after_seconds: int) -> JSONResponse:
    return client_error(
        RATE_LIMITED_DETAIL,
        response_code=429,
        headers={"Retry-After": str(max(1, retry_after_seconds))},
    )


async def _throttle(client_id: str, client: ApiClientUser | None) -> JSONResponse | None:
    """限流先行:鎖定中 / 超限回 429,否則回 None。未知 client 用預設上限(防列舉爆破)。"""
    lock = await check_auth_lock(client_id)
    if lock.locked:
        return _rate_limited(lock.retry_after_seconds)
    result = await check_rate_limit(
        client_id,
        client.rate_limit_per_minute if client else DEFAULT_LIMIT_PER_MINUTE,
        client.rate_limit_per_10min if client else DEFAULT_LIMIT_PER_10MIN,
    )
    if not result.allowed:
        return _rate_limited(result.retry_after_seconds)
    return None


async def _authenticated(record: _ClientRecord | None, client_secret: str) -> bool:
    """client 存在且啟用,且明文 secret 命中任一把 active 密鑰(bcrypt 走 thread)。"""
    if record is None:
        return False
    client, secrets = record
    if client.status != CLIENT_STATUS_ENABLED:
        return False
    for secret in secrets:
        if await verify_password_async(client_secret, secret.secret_hash):
            return True
    return False


async def _reject(client_id: str) -> JSONResponse:
    await register_auth_failure(client_id)
    return client_error(INVALID_CLIENT_DETAIL, response_code=401)


async def _issue(client_id: str) -> JSONResponse:
    await clear_auth_failures(client_id)
    access_token, expires_in = sign_client_jwt(client_id)
    return client_success(
        [
            {
                "access_token": access_token,
                "token_type": TOKEN_TYPE_BEARER,
                "expires_in": expires_in,
            }
        ]
    )


@router.post(
    "/token",
    response_model=ClientEnvelope,
    summary="Client Credentials 換發短效 JWT(15 分鐘)",
)
async def issue_token(
    payload: TokenRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> JSONResponse:
    record = await ApiClientRepository(db).get_by_client_id(payload.client_id)
    throttled = await _throttle(payload.client_id, record[0] if record else None)
    if throttled is not None:
        return throttled
    if not await _authenticated(record, payload.client_secret):
        return await _reject(payload.client_id)
    return await _issue(payload.client_id)


@router.post(
    "/refresh_token",
    response_model=ClientEnvelope,
    summary="以過期 token + 憑證換發新 JWT(語意刷新,與 /token 安全等價)",
)
async def refresh_token(
    payload: RefreshTokenRequest, db: Annotated[AsyncSession, Depends(get_db)]
) -> JSONResponse:
    record = await ApiClientRepository(db).get_by_client_id(payload.client_id)
    throttled = await _throttle(payload.client_id, record[0] if record else None)
    if throttled is not None:
        return throttled
    if not is_refreshable_token(payload.access_token, payload.client_id):
        return await _reject(payload.client_id)
    if not await _authenticated(record, payload.client_secret):
        return await _reject(payload.client_id)
    return await _issue(payload.client_id)


def mount(app_or_router: FastAPI | APIRouter) -> None:
    mount_version(app_or_router, VERSION, {"": router})
