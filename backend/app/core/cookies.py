from fastapi import Response

from app.core.config import get_settings

JWT_COOKIE_NAME = "access_token"


def _cookie_domain() -> str | None:
    # 空字串 → host-only(本機開發);設 .zerozero.tw → 所有 *.zerozero.tw 子網域共用
    domain = get_settings().COOKIE_DOMAIN
    return domain or None


def set_jwt_cookie(response: Response, token: str, max_age: int = 60 * 60 * 8) -> None:
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
        domain=_cookie_domain(),
    )


def clear_jwt_cookie(response: Response) -> None:
    # domain 必須與 set 時一致,否則刪不到跨子網域那顆 cookie(登出清不掉)
    response.delete_cookie(key=JWT_COOKIE_NAME, path="/", domain=_cookie_domain())
