"""使用者管理服務:使用者清單 / 角色指派(自降防呆 + 稽核)、角色列表(供 /roles 端點)。

角色為固定兩種(admin / member,見 app/core/roles.py),無 roles 表 / 外鍵關聯。
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.roles import ROLE_ADMIN, ROLES
from app.models.user import User
from app.repositories.user_repo import UserRepository, ensure_valid_role
from app.schemas.role import RoleListResponse, RoleResponse
from app.schemas.user import UserListItemResponse, UserListResponse
from app.services.audit_service import AuditService
from app.services.sso_service import PROVIDER_SSO

_PROVIDER_LOCAL = "local"

_USER_NOT_FOUND_DETAIL = "使用者不存在"
_SELF_DEMOTE_DETAIL = "不可將自己降級"


def _provider_of(user: User) -> str:
    return PROVIDER_SSO if user.sso_subject is not None else _PROVIDER_LOCAL


def _to_list_item(user: User) -> UserListItemResponse:
    return UserListItemResponse(
        uid=user.uid,
        username=user.username,
        display_name=user.display_name,
        provider=_provider_of(user),
        role=user.role,
    )


def list_roles() -> RoleListResponse:
    return RoleListResponse(
        items=[
            RoleResponse(code=code, name=name, description=description)
            for code, name, description in ROLES
        ]
    )


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._users = UserRepository(db)

    async def list_users(self, *, page: int, page_size: int) -> UserListResponse:
        rows, total = await self._users.list_users(
            offset=(page - 1) * page_size, limit=page_size
        )
        return UserListResponse(
            items=[_to_list_item(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def assign_role(
        self, target_uid: UUID, role_code: str, *, actor: User
    ) -> UserListItemResponse:
        target = await self._users.get_by_uid(target_uid)
        if target is None:
            raise AppError(_USER_NOT_FOUND_DETAIL, response_code=404, status_code=404)
        role = ensure_valid_role(role_code)
        # 自降防呆:admin 對自己指派非 admin 角色 → 403(避免系統鎖死無 admin)
        if target.uid == actor.uid and role != ROLE_ADMIN:
            raise AppError(_SELF_DEMOTE_DETAIL, response_code=403, status_code=403)
        old_code = target.role
        await self._users.assign_role(target, role, actor_uid=actor.uid)
        await AuditService(self._db).log(
            action="role_assigned",
            actor_uid=actor.uid,
            actor_username=actor.username,
            target_type="user",
            target_uid=target.uid,
            detail=f"{old_code} → {role}",
        )
        return _to_list_item(target)
