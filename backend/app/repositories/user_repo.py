from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.roles import ROLE_CODES
from app.models.user import User
from app.utils.datetime import db_now


def ensure_valid_role(code: str) -> str:
    """角色驗證單一入口:非 admin / member → fail-fast,禁默默寫入未知角色。"""
    if code not in ROLE_CODES:
        raise AppError(f"角色 {code} 不存在", response_code=404, status_code=404)
    return code


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_username(self, username: str) -> User | None:
        stmt = select(User).where(User.username == username, User.is_deleted.is_(False))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_uid(self, uid: UUID) -> User | None:
        stmt = select(User).where(User.uid == uid, User.is_deleted.is_(False))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_users(self, *, offset: int, limit: int) -> tuple[list[User], int]:
        conditions = (User.is_deleted.is_(False),)
        total = (
            await self._db.execute(select(func.count()).select_from(User).where(*conditions))
        ).scalar_one()
        stmt = select(User).where(*conditions).order_by(User.pid).offset(offset).limit(limit)
        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows), total

    async def create(
        self,
        *,
        username: str,
        password_hash: str | None,
        role: str,
        display_name: str | None = None,
        actor_uid: UUID | None = None,
    ) -> User:
        uid = uuid4()
        # 無操作者(如系統初始化)時,以新使用者自身 uid 作為 created_by / updated_by
        actor = actor_uid if actor_uid is not None else uid
        user = User(
            uid=uid,
            username=username,
            password_hash=password_hash,
            role=ensure_valid_role(role),
            display_name=display_name,
            created_by=actor,
            updated_by=actor,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def assign_role(self, user: User, role: str, *, actor_uid: UUID) -> None:
        user.role = ensure_valid_role(role)
        user.updated_by = actor_uid
        user.updated_at = db_now()
        await self._db.flush()
