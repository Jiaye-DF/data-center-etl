from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


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
            role=role,
            display_name=display_name,
            created_by=actor,
            updated_by=actor,
        )
        self._db.add(user)
        await self._db.flush()
        return user
