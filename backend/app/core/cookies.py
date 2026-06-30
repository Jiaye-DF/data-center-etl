from fastapi import Response

JWT_COOKIE_NAME = "access_token"


def set_jwt_cookie(response: Response, token: str, max_age: int = 60 * 60 * 8) -> None:
    response.set_cookie(
        key=JWT_COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


def clear_jwt_cookie(response: Response) -> None:
    response.delete_cookie(key=JWT_COOKIE_NAME, path="/")
