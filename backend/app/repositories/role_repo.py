from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role


class RoleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_all(self) -> list[Role]:
        stmt = select(Role).where(Role.is_deleted.is_(False)).order_by(Role.pid)
        return list((await self._db.execute(stmt)).scalars().all())

    async def find_by_code(self, code: str) -> Role | None:
        stmt = select(Role).where(Role.code == code, Role.is_deleted.is_(False))
        return (await self._db.execute(stmt)).scalar_one_or_none()
