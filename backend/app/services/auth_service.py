import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import hash_password_async, verify_password_async
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.services.audit_service import AuditService, log_detached

logger = logging.getLogger(__name__)

_LOGIN_FAILED_DETAIL = "帳號或密碼錯誤"


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User:
        """驗證帳密;失敗一律回同一 401 訊息,避免帳號列舉。

        稽核(R-PII-003):成功寫 login_success(request session);
        失敗寫 login_failed — 隨後 raise 會使 get_db rollback,
        必須走 log_detached 獨立 session 立即 commit。
        """
        user = await self._users.get_by_username(username)
        if user is None or user.password_hash is None:
            await self._audit_login_failed(username)
            raise AppError(_LOGIN_FAILED_DETAIL, response_code=401, status_code=401)
        if not await verify_password_async(password, user.password_hash):
            await self._audit_login_failed(username)
            raise AppError(_LOGIN_FAILED_DETAIL, response_code=401, status_code=401)
        await AuditService(self._db).log(
            action="login_success",
            actor_uid=user.uid,
            actor_username=user.username,
            detail="本地帳密登入成功",
        )
        return user

    async def _audit_login_failed(self, username: str) -> None:
        # 只記嘗試帳號,禁記密碼;失敗原因不區分(避免帳號列舉線索落 DB 之外的差異)
        await log_detached(
            action="login_failed",
            actor_username=username,
            detail="本地帳密登入失敗(帳號或密碼錯誤)",
        )

    async def get_user_by_uid(self, uid: UUID) -> User | None:
        return await self._users.get_by_uid(uid)


async def ensure_init_admin(db: AsyncSession) -> bool:
    """冪等建立初始管理員(帳密來自 env):已存在即不重建、不覆寫密碼。回傳是否新建。"""
    settings = get_settings()
    repo = UserRepository(db)
    existing = await repo.get_by_username(settings.INIT_ADMIN_USERNAME)
    if existing is not None:
        return False
    password_hash = await hash_password_async(settings.INIT_ADMIN_PASSWORD)
    await repo.create(
        username=settings.INIT_ADMIN_USERNAME,
        password_hash=password_hash,
        role="admin",
    )
    # 只記帳號,禁 log 密碼(00-overview/02-secrets.md)
    logger.info("init_admin:已建立初始管理員 %s", settings.INIT_ADMIN_USERNAME)
    return True
