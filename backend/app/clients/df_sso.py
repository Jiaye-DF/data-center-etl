"""DF-SSO 中央登入器 client(server-to-server)。

契約:`docs/Design-Base/90-third-party-service/08-df-sso.md`
- 所有呼叫等價 `cache: no-store` + timeout ≤ 8s
- 第三方錯誤一律轉 AppError 子類(禁 httpx 原生 exception 外流)

註:依 task-003 affected_files 白名單,本 client 為單一模組(非 `clients/df_sso/` 子目錄),
schema 與錯誤類併於本檔,見 fixed.md。
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.exceptions import AppError


class DfSsoError(AppError):
    """DF-SSO 中央回應異常(對外預設 502)。"""

    def __init__(
        self, detail: str, *, status_code: int = 502, error_code: str | None = None
    ) -> None:
        super().__init__(
            detail, response_code=status_code, status_code=status_code, error_code=error_code
        )


class DfSsoAuthError(DfSsoError):
    """中央判定認證失敗(code 無效 / session 已失效)。"""

    def __init__(self, detail: str, *, error_code: str | None = None) -> None:
        super().__init__(detail, status_code=401, error_code=error_code)


class DfSsoUnreachableError(DfSsoError):
    """中央不可達(逾時 / 網路錯誤)。"""


class DfSsoUser(BaseModel):
    """中央 `/api/auth/me` 回應的 user 物件(erpData 可能為 null)。"""

    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(alias="userId")
    email: str
    name: str
    erp_data: dict[str, str] | None = Field(default=None, alias="erpData")
    login_at: str | None = Field(default=None, alias="loginAt")


class DfSsoClient:
    """DF-SSO client:code 交換 / 回源 me / 通知登出。"""

    def __init__(
        self, *, base_url: str, app_id: str, app_secret: str, timeout_read: float = 8.0
    ) -> None:
        self._app_id = app_id
        self._app_secret = app_secret
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(connect=5.0, read=timeout_read, write=5.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=5),
            headers={"Cache-Control": "no-store"},
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def exchange_code(self, code: str) -> str:
        """以 auth code 換中央 token(帶 client_secret,僅 server-to-server)。"""
        try:
            res = await self._http.post(
                "/api/auth/sso/exchange",
                json={
                    "code": code,
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                },
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise DfSsoUnreachableError(
                "DF-SSO 中央不可達", error_code="exchange_error"
            ) from exc
        if res.status_code != 200:
            raise DfSsoAuthError("DF-SSO code 交換失敗", error_code="exchange_failed")
        body: object = res.json()
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not token:
            raise DfSsoError("DF-SSO 交換回應缺少 token", error_code="exchange_failed")
        return token

    async def get_me(self, token: str) -> DfSsoUser:
        """以 Bearer token 即時回源中央 `/api/auth/me`(契約 #1:禁本地快取)。"""
        try:
            res = await self._http.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise DfSsoUnreachableError(
                "DF-SSO 中央不可達", error_code="sso_unreachable"
            ) from exc
        if res.status_code == 401:
            raise DfSsoAuthError("DF-SSO session 已失效", error_code="session_expired")
        if res.status_code != 200:
            raise DfSsoError(f"DF-SSO 回應異常:{res.status_code}", error_code="sso_error")
        body: object = res.json()
        user_data = body.get("user") if isinstance(body, dict) else None
        if not isinstance(user_data, dict):
            raise DfSsoError("DF-SSO /me 回應格式異常", error_code="sso_error")
        return DfSsoUser.model_validate(user_data)

    async def logout(self, token: str, redirect_after: str) -> str | None:
        """通知中央登出(契約 #2)。失敗不 raise(登出不因中央異常中斷),回 logout_url 或 None。"""
        try:
            res = await self._http.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {token}"},
                json={"redirect": redirect_after},
            )
            if res.status_code != 200:
                return None
            body: object = res.json()
        except (httpx.HTTPError, ValueError):
            return None
        if not isinstance(body, dict):
            return None
        url = body.get("logout_url") or body.get("redirect")
        return url if isinstance(url, str) else None


_client: DfSsoClient | None = None


def get_df_sso_client() -> DfSsoClient:
    """惰性單例(共用連線池)。

    main.py 不在 task-003 白名單,無法依 01-client-design 於 lifespan 建立/釋放,
    改為首次使用時建立(見 fixed.md)。
    """
    global _client
    if _client is None:
        settings = get_settings()
        _client = DfSsoClient(
            base_url=settings.SSO_URL,
            app_id=settings.SSO_APP_ID,
            app_secret=settings.SSO_APP_SECRET,
        )
    return _client
