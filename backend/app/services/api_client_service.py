"""API Client 後台管理服務(建立 / 發證 / 輪替 / 汰換 / 啟停 / 限流參數)。

- 明文 client_secret 只在核發當次回傳,入庫僅存 bcrypt 雜湊;稽核 detail 一律不含明文。
- api_client_repo 無「依 uid 取件」、「active 密鑰計數」與「含 retired 的密鑰清單」方法,
  且該檔不在本 task 檔案白名單 → 這些查詢暫落本 service
  (同 sso_service / data_query_service 前例)。
"""

import secrets
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError
from app.core.security import hash_password_async
from app.models.api_client_secret import SECRET_STATUS_ACTIVE, ApiClientSecret
from app.models.api_client_user import ApiClientUser
from app.repositories.api_client_repo import ApiClientRepository
from app.schemas.api_client import (
    ApiClientCreatedResponse,
    ApiClientCreateRequest,
    ApiClientListResponse,
    ApiClientResponse,
    ApiClientSecretIssuedResponse,
    ApiClientSecretListResponse,
    ApiClientSecretResponse,
    ApiClientUpdateRequest,
)
from app.services.audit_service import AuditService

CLIENT_ID_PREFIX = "dc_"
_CLIENT_ID_RANDOM_BYTES = 12  # token_hex 產出 24 字元 hex
_SECRET_TOKEN_BYTES = 32

_TARGET_TYPE = "api_client"
_CLIENT_NOT_FOUND_DETAIL = "API Client 不存在"
_SECRET_NOT_FOUND_DETAIL = "密鑰不存在"


def generate_client_id() -> str:
    return f"{CLIENT_ID_PREFIX}{secrets.token_hex(_CLIENT_ID_RANDOM_BYTES)}"


def generate_client_secret() -> str:
    return secrets.token_urlsafe(_SECRET_TOKEN_BYTES)


def _to_response(client: ApiClientUser, active_secret_count: int) -> ApiClientResponse:
    return ApiClientResponse(
        uid=client.uid,
        client_id=client.client_id,
        name=client.name,
        description=client.description,
        status=client.status,
        rate_limit_per_minute=client.rate_limit_per_minute,
        rate_limit_per_10min=client.rate_limit_per_10min,
        active_secret_count=active_secret_count,
        created_at=client.created_at,
    )


class ApiClientService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = ApiClientRepository(db)
        self._audit = AuditService(db)

    async def list_clients(self, *, page: int, page_size: int) -> ApiClientListResponse:
        rows, total = await self._repo.list_(
            offset=(page - 1) * page_size, limit=page_size
        )
        counts = await self._active_secret_counts([row.pid for row in rows])
        return ApiClientListResponse(
            items=[_to_response(row, counts.get(row.pid, 0)) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def list_secrets(self, uid: UUID) -> ApiClientSecretListResponse:
        client = await self._get_or_404(uid)
        rows = (
            (
                await self._db.execute(
                    select(ApiClientSecret)
                    .where(
                        ApiClientSecret.api_client_user_pid == client.pid,
                        ApiClientSecret.is_deleted.is_(False),
                    )
                    .order_by(ApiClientSecret.created_at, ApiClientSecret.pid)
                )
            )
            .scalars()
            .all()
        )
        items = [
            ApiClientSecretResponse(
                uid=row.uid, status=row.status, created_at=row.created_at
            )
            for row in rows
        ]
        return ApiClientSecretListResponse(items=items, total=len(items))

    async def create_client(
        self, payload: ApiClientCreateRequest, *, actor_uid: UUID
    ) -> ApiClientCreatedResponse:
        plain_secret = generate_client_secret()
        client = await self._repo.create(
            client_id=generate_client_id(),
            name=payload.name,
            description=payload.description,
            actor_uid=actor_uid,
        )
        secret = await self._repo.add_secret(
            client,
            secret_hash=await hash_password_async(plain_secret),
            actor_uid=actor_uid,
        )
        await self._db.refresh(client)
        await self._audit.log(
            action="api_client_create",
            actor_uid=actor_uid,
            target_type=_TARGET_TYPE,
            target_uid=client.uid,
            detail=f"建立 API Client {client.name}(client_id={client.client_id})",
        )
        return ApiClientCreatedResponse(
            client=_to_response(client, 1),
            secret_uid=secret.uid,
            client_secret=plain_secret,
        )

    async def update_client(
        self, uid: UUID, payload: ApiClientUpdateRequest, *, actor_uid: UUID
    ) -> ApiClientResponse:
        client = await self._get_or_404(uid)
        await self._repo.update(
            client,
            name=payload.name,
            description=payload.description,
            status=payload.status,
            rate_limit_per_minute=payload.rate_limit_per_minute,
            rate_limit_per_10min=payload.rate_limit_per_10min,
            actor_uid=actor_uid,
        )
        changed = ", ".join(sorted(payload.model_fields_set)) or "無"
        await self._audit.log(
            action="api_client_update",
            actor_uid=actor_uid,
            target_type=_TARGET_TYPE,
            target_uid=client.uid,
            detail=f"更新 API Client {client.client_id}(欄位:{changed})",
        )
        return await self._with_active_count(client)

    async def rotate_secret(
        self, uid: UUID, *, actor_uid: UUID
    ) -> ApiClientSecretIssuedResponse:
        client = await self._get_or_404(uid)
        plain_secret = generate_client_secret()
        # active ≥ 2 由 repo 檢核擋下(AppError 409:先汰舊才能再發)
        secret = await self._repo.add_secret(
            client,
            secret_hash=await hash_password_async(plain_secret),
            actor_uid=actor_uid,
        )
        active_count = len(await self._repo.list_active_secrets(client))
        await self._audit.log(
            action="api_client_secret_rotate",
            actor_uid=actor_uid,
            target_type=_TARGET_TYPE,
            target_uid=client.uid,
            detail=(
                f"核發新密鑰(client_id={client.client_id};"
                f"有效密鑰把數={active_count})"
            ),
        )
        return ApiClientSecretIssuedResponse(
            secret_uid=secret.uid,
            client_secret=plain_secret,
            active_secret_count=active_count,
        )

    async def retire_secret(
        self, uid: UUID, secret_uid: UUID, *, actor_uid: UUID
    ) -> ApiClientResponse:
        client = await self._get_or_404(uid)
        secret = await self._get_secret_or_404(client, secret_uid)
        await self._repo.retire_secret(secret, actor_uid=actor_uid)
        await self._audit.log(
            action="api_client_secret_retire",
            actor_uid=actor_uid,
            target_type=_TARGET_TYPE,
            target_uid=client.uid,
            detail=f"汰換密鑰(client_id={client.client_id};secret_uid={secret.uid})",
        )
        return await self._with_active_count(client)

    async def _with_active_count(self, client: ApiClientUser) -> ApiClientResponse:
        return _to_response(client, len(await self._repo.list_active_secrets(client)))

    async def _get_or_404(self, uid: UUID) -> ApiClientUser:
        client = (
            await self._db.execute(
                select(ApiClientUser).where(
                    ApiClientUser.uid == uid, ApiClientUser.is_deleted.is_(False)
                )
            )
        ).scalar_one_or_none()
        if client is None:
            raise AppError(_CLIENT_NOT_FOUND_DETAIL, response_code=404, status_code=404)
        return client

    async def _get_secret_or_404(
        self, client: ApiClientUser, secret_uid: UUID
    ) -> ApiClientSecret:
        secret = (
            await self._db.execute(
                select(ApiClientSecret).where(
                    ApiClientSecret.uid == secret_uid,
                    ApiClientSecret.api_client_user_pid == client.pid,
                    ApiClientSecret.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if secret is None:
            raise AppError(_SECRET_NOT_FOUND_DETAIL, response_code=404, status_code=404)
        return secret

    async def _active_secret_counts(self, pids: list[int]) -> dict[int, int]:
        if not pids:
            return {}
        rows = await self._db.execute(
            select(ApiClientSecret.api_client_user_pid, func.count())
            .where(
                ApiClientSecret.api_client_user_pid.in_(pids),
                ApiClientSecret.status == SECRET_STATUS_ACTIVE,
                ApiClientSecret.is_deleted.is_(False),
            )
            .group_by(ApiClientSecret.api_client_user_pid)
        )
        return {pid: count for pid, count in rows.all()}
