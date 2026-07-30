"""API Client 機器身分 Repository(api_client_users / api_client_secrets)。

- 讀取一律過濾 `is_deleted`(軟刪除規範 `04-databases/02-soft-delete.md`);
- client_id 唯一性由 partial unique index 保證(軟刪除後可重建同名);
- 「同一 Client active 密鑰 ≤ 2」為應用層檢核(DB 無此約束),於 `add_secret` 擋下。
"""

from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.models.api_client_secret import (
    SECRET_STATUS_ACTIVE,
    SECRET_STATUS_RETIRED,
    ApiClientSecret,
)
from app.models.api_client_user import (
    CLIENT_STATUS_ENABLED,
    DEFAULT_RATE_LIMIT_PER_10MIN,
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    ApiClientUser,
)
from app.utils.datetime import db_now

MAX_ACTIVE_SECRETS = 2


class ApiClientRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_client_id(
        self, client_id: str
    ) -> tuple[ApiClientUser, list[ApiClientSecret]] | None:
        """取未刪除 Client 與其 active 密鑰(驗證 client_secret 所需的最小資料)。"""
        client = (
            await self._db.execute(
                select(ApiClientUser).where(
                    ApiClientUser.client_id == client_id,
                    ApiClientUser.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if client is None:
            return None
        return client, await self.list_active_secrets(client)

    async def list_active_secrets(self, client: ApiClientUser) -> list[ApiClientSecret]:
        rows = (
            await self._db.execute(
                select(ApiClientSecret)
                .where(
                    ApiClientSecret.api_client_user_pid == client.pid,
                    ApiClientSecret.status == SECRET_STATUS_ACTIVE,
                    ApiClientSecret.is_deleted.is_(False),
                )
                .order_by(ApiClientSecret.pid)
            )
        ).scalars()
        return list(rows.all())

    async def list_(self, *, offset: int, limit: int) -> tuple[list[ApiClientUser], int]:
        conditions = (ApiClientUser.is_deleted.is_(False),)
        total = (
            await self._db.execute(
                select(func.count()).select_from(ApiClientUser).where(*conditions)
            )
        ).scalar_one()
        rows = (
            await self._db.execute(
                select(ApiClientUser)
                .where(*conditions)
                .order_by(ApiClientUser.pid)
                .offset(offset)
                .limit(limit)
            )
        ).scalars()
        return list(rows.all()), total

    async def create(
        self,
        *,
        client_id: str,
        name: str,
        description: str | None = None,
        status: str = CLIENT_STATUS_ENABLED,
        rate_limit_per_minute: int = DEFAULT_RATE_LIMIT_PER_MINUTE,
        rate_limit_per_10min: int = DEFAULT_RATE_LIMIT_PER_10MIN,
        actor_uid: UUID,
    ) -> ApiClientUser:
        client = ApiClientUser(
            uid=uuid4(),
            client_id=client_id,
            name=name,
            description=description,
            status=status,
            rate_limit_per_minute=rate_limit_per_minute,
            rate_limit_per_10min=rate_limit_per_10min,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(client)
        await self._db.flush()
        return client

    async def update(
        self,
        client: ApiClientUser,
        *,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        rate_limit_per_minute: int | None = None,
        rate_limit_per_10min: int | None = None,
        actor_uid: UUID,
    ) -> ApiClientUser:
        """部分更新;None 一律代表「不變更」(含 description,故本層無法清空該欄)。"""
        if name is not None:
            client.name = name
        if description is not None:
            client.description = description
        if status is not None:
            client.status = status
        if rate_limit_per_minute is not None:
            client.rate_limit_per_minute = rate_limit_per_minute
        if rate_limit_per_10min is not None:
            client.rate_limit_per_10min = rate_limit_per_10min
        await self._touch(client, actor_uid)
        return client

    async def soft_delete(self, client: ApiClientUser, *, actor_uid: UUID) -> None:
        client.is_deleted = True
        await self._touch(client, actor_uid)

    async def add_secret(
        self, client: ApiClientUser, *, secret_hash: str, actor_uid: UUID
    ) -> ApiClientSecret:
        active_count = len(await self.list_active_secrets(client))
        if active_count >= MAX_ACTIVE_SECRETS:
            raise AppError(
                f"同一 API Client 最多 {MAX_ACTIVE_SECRETS} 把有效密鑰,請先停用舊密鑰",
                response_code=409,
                status_code=409,
            )
        secret = ApiClientSecret(
            uid=uuid4(),
            api_client_user_pid=client.pid,
            secret_hash=secret_hash,
            status=SECRET_STATUS_ACTIVE,
            created_by=actor_uid,
            updated_by=actor_uid,
        )
        self._db.add(secret)
        await self._db.flush()
        return secret

    async def retire_secret(self, secret: ApiClientSecret, *, actor_uid: UUID) -> None:
        secret.status = SECRET_STATUS_RETIRED
        await self._touch(secret, actor_uid)

    async def _touch(self, row: ApiClientUser | ApiClientSecret, actor_uid: UUID) -> None:
        row.updated_by = actor_uid
        row.updated_at = db_now()
        await self._db.flush()
