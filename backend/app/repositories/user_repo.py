from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.role import Role
from app.models.user import User
from app.utils.datetime import db_now

_ROLE_REF_MISSING_DETAIL = "使用者角色關聯缺失,請確認 roles migration 已執行"


def resolve_role_code(user: User) -> str:
    """角色取值單一入口:授權判斷 / me 回應 / 簽發 token 一律經此取 roles.code。

    來源 = role_ref 關聯(model 端 lazy="joined" 隨主查詢載入,無額外 IO / N+1);
    deprecated 的 users.role 字串不再作為授權判斷來源。
    關聯缺失(migration 未跑 / role_pid 未寫入)→ fail-fast,禁默默 fallback。
    """
    role = user.role_ref
    if role is None or role.is_deleted:
        raise AppError(_ROLE_REF_MISSING_DETAIL, response_code=500, status_code=500)
    return role.code


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
        """分頁清單(role_ref 由 model 端 lazy="joined" 隨主查詢載入,禁 N+1)。"""
        conditions = (User.is_deleted.is_(False),)
        total = (
            await self._db.execute(
                select(func.count()).select_from(User).where(*conditions)
            )
        ).scalar_one()
        stmt = (
            select(User)
            .where(*conditions)
            .order_by(User.pid)
            .offset(offset)
            .limit(limit)
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        return list(rows), total

    async def get_role_by_code(self, code: str) -> Role:
        """依 code 取角色;找不到 → fail-fast(migration 未跑的環境要炸得明確)。"""
        stmt = select(Role).where(Role.code == code, Role.is_deleted.is_(False))
        role = (await self._db.execute(stmt)).scalar_one_or_none()
        if role is None:
            raise AppError(
                f"角色 {code} 不存在,請確認 roles migration 已執行",
                response_code=500,
                status_code=500,
            )
        return role

    async def create(
        self,
        *,
        username: str,
        password_hash: str | None,
        role: str,
        display_name: str | None = None,
        actor_uid: UUID | None = None,
    ) -> User:
        role_row = await self.get_role_by_code(role)
        uid = uuid4()
        # 無操作者(如系統初始化)時,以新使用者自身 uid 作為 created_by / updated_by
        actor = actor_uid if actor_uid is not None else uid
        user = User(
            uid=uid,
            username=username,
            password_hash=password_hash,
            # dual-write:deprecated 字串欄位同步寫同值(與 ck_users_role 一致,直到人工移除)
            role=role_row.code,
            role_ref=role_row,
            display_name=display_name,
            created_by=actor,
            updated_by=actor,
        )
        self._db.add(user)
        await self._db.flush()
        return user

    async def assign_role(self, user: User, role: Role, *, actor_uid: UUID) -> None:
        """指派角色:寫 role_pid 關聯,dual-write deprecated 字串欄位同值。"""
        user.role_pid = role.pid
        user.role_ref = role
        user.role = role.code
        user.updated_by = actor_uid
        user.updated_at = db_now()
        await self._db.flush()
