from datetime import UTC, datetime

import jwt

from app.core.config import get_settings

CLIENT_JWT_ALGORITHM = "HS256"
CLIENT_JWT_ISSUER = "datahub-api-gateway"
CLIENT_JWT_EXPIRE_SECONDS = 900


def sign_client_jwt(client_id: str) -> tuple[str, int]:
    """簽發對外 API Client 的短效 JWT;回 (token, expires_in 秒數)。"""
    issued_at = int(datetime.now(UTC).timestamp())
    payload: dict[str, object] = {
        "sub": client_id,
        "iat": issued_at,
        "exp": issued_at + CLIENT_JWT_EXPIRE_SECONDS,
        "iss": CLIENT_JWT_ISSUER,
    }
    token = jwt.encode(
        payload,
        get_settings().CLIENT_JWT_SECRET,
        algorithm=CLIENT_JWT_ALGORITHM,
    )
    return token, CLIENT_JWT_EXPIRE_SECONDS


def verify_client_jwt(token: str, *, verify_exp: bool = True) -> dict[str, object]:
    """本地驗簽(不查 DB、不回源);無效 / 過期拋 jwt.PyJWTError,由呼叫端轉 401。

    `verify_exp=False` 供 /refresh_token 驗過期舊 token 的簽章與 sub(忽略 exp)。
    """
    payload: dict[str, object] = jwt.decode(
        token,
        get_settings().CLIENT_JWT_SECRET,
        algorithms=[CLIENT_JWT_ALGORITHM],
        issuer=CLIENT_JWT_ISSUER,
        options={"verify_exp": verify_exp, "require": ["sub", "iat", "exp", "iss"]},
    )
    return payload


def is_refreshable_token(token: str, client_id: str) -> bool:
    """`/refresh_token` 前置:舊 token 簽章有效(忽略 exp)且 `sub` 與請求 client_id 相符。"""
    try:
        payload = verify_client_jwt(token, verify_exp=False)
    except jwt.PyJWTError:
        return False
    return payload.get("sub") == client_id
