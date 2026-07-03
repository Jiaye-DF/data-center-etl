"""DF-SSO 使用者對應與 session 管理(模式 B:本地帳密 + SSO 雙軌)。

契約:`docs/Design-Base/90-third-party-service/08-df-sso.md`
- SSO 使用者對應自有 `users` 表:首次登入自動建 viewer(升 admin 由管理者調整)
- SSO 側 token 驗證一律即時回源中央(契約 #1);本模組的撤銷註記僅為
  back-channel logout(契約 #4)的本地補強,見 fixed.md
"""

import hashlib
import hmac
import time
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.df_sso import DfSsoUser, get_df_sso_client
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import JWT_ALGORITHM
from app.models.user import User
from app.repositories.user_repo import UserRepository

PROVIDER_SSO = "sso"
# 契約:cookie Max-Age 固定 86400(SSO 側 JWT 效期與之對齊)
SSO_SESSION_MAX_AGE_SECONDS = 86400
MAX_TIMESTAMP_DRIFT_MS = 30_000

# back-channel logout 撤銷註記:sso_subject → 撤銷時間(epoch 秒)。
# process-local(本版尚無共享 session store);主要失效路徑仍是每次回源中央(契約 #1)。
_sso_revoked_at: dict[str, float] = {}


class SsoService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserRepository(db)

    async def login_with_code(self, code: str) -> tuple[User, str]:
        """code 換中央 token → 取中央使用者 → 對應/建立本地使用者。"""
        settings = get_settings()
        if not settings.SSO_URL:
            raise AppError(
                "DF-SSO 未設定", response_code=503, status_code=503,
                error_code="sso_not_configured",
            )
        client = get_df_sso_client()
        sso_token = await client.exchange_code(code)
        sso_user = await client.get_me(sso_token)
        user = await self._get_or_create_user(sso_user)
        return user, sso_token

    async def get_user_by_sso_subject(self, sso_subject: str) -> User | None:
        # user_repo.py 不在 task-003 白名單 → 查詢暫落本 service(見 fixed.md)
        stmt = select(User).where(
            User.sso_subject == sso_subject, User.is_deleted.is_(False)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_or_create_user(self, sso_user: DfSsoUser) -> User:
        existing = await self.get_user_by_sso_subject(sso_user.user_id)
        if existing is not None:
            # 重複登入:不重建、不動角色
            return existing
        by_username = await self._users.get_by_username(sso_user.email)
        if by_username is not None:
            # 同帳號已有本地使用者 → 綁定 sso_subject(避免 username 唯一索引衝突),保留原角色
            by_username.sso_subject = sso_user.user_id
            await self._db.flush()
            return by_username
        # 首次登入:自動建 viewer,無本地密碼(SSO-only)
        user = await self._users.create(
            username=sso_user.email, password_hash=None, role="viewer"
        )
        user.sso_subject = sso_user.user_id
        await self._db.flush()
        return user


def create_sso_access_token(
    *, user: User, sso_token: str, secret_key: str, expires_minutes: int
) -> str:
    """簽發 SSO 側 JWT(與本地登入共用同一 httpOnly cookie 機制)。

    模式 B 契約:payload 必帶 provider;中央 token 併入 payload,
    供 `/sso/me` 每次以 Bearer 回源中央驗證(契約 #1)。
    """
    if user.sso_subject is None:
        raise AppError("使用者缺少 sso_subject", response_code=500, status_code=500)
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(user.uid),
        "role": user.role,
        "provider": PROVIDER_SSO,
        "sso_sub": user.sso_subject,
        "sso_token": sso_token,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def verify_back_channel_signature(
    *, user_id: str, timestamp: int, signature: str, app_secret: str
) -> tuple[bool, str | None]:
    """驗 back-channel logout 簽章(契約 #4)。

    HMAC-SHA256("<user_id>:<timestamp>", app_secret);constant-time 比對(禁 ==),
    並驗 abs(now_ms - timestamp) ≤ 30000。回傳 (是否有效, 失敗原因)。
    """
    now_ms = int(time.time() * 1000)
    if abs(now_ms - timestamp) > MAX_TIMESTAMP_DRIFT_MS:
        return False, "timestamp_expired"
    expected = hmac.new(
        app_secret.encode("utf-8"), f"{user_id}:{timestamp}".encode(), hashlib.sha256
    ).hexdigest()
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        return False, "invalid_signature"
    return True, None


def revoke_sso_sessions(sso_subject: str) -> None:
    """撤銷該中央使用者在本 App 的 SSO session(既發 token 立即失效)。"""
    _sso_revoked_at[sso_subject] = time.time()


def is_sso_session_revoked(sso_subject: str, issued_at: float) -> bool:
    revoked_at = _sso_revoked_at.get(sso_subject)
    return revoked_at is not None and issued_at <= revoked_at


def reset_sso_revocations() -> None:
    """清空撤銷註記(測試用)。"""
    _sso_revoked_at.clear()
