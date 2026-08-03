from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.api_client import (
    ApiClientCreatedResponse,
    ApiClientCreateRequest,
    ApiClientListResponse,
    ApiClientResponse,
    ApiClientSecretIssuedResponse,
    ApiClientSecretListResponse,
    ApiClientSecretRevealResponse,
    ApiClientUpdateRequest,
)
from app.schemas.client_setting_preview import EffectivePermissionsResponse
from app.schemas.response import ApiResponse
from app.services.api_client_service import ApiClientService
from app.services.effective_permission_service import EffectivePermissionService

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[ApiClientListResponse],
    summary="API Client 清單(admin 專用;分頁,排除軟刪)",
)
async def list_api_clients(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[ApiClientListResponse]:
    data = await ApiClientService(db).list_clients(page=page, page_size=page_size)
    return success(data=data)


@router.post(
    "",
    response_model=ApiResponse[ApiClientCreatedResponse],
    status_code=201,
    summary="建立 API Client(admin 專用;明文 client_secret 僅此一次回傳)",
)
async def create_api_client(
    payload: ApiClientCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientCreatedResponse]:
    data = await ApiClientService(db).create_client(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/{uid}",
    response_model=ApiResponse[ApiClientResponse],
    summary="更新 API Client(名稱 / 說明 / 啟停 / 限流參數;禁改 client_id)",
)
async def update_api_client(
    uid: UUID,
    payload: ApiClientUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientResponse]:
    data = await ApiClientService(db).update_client(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/{uid}",
    response_model=ApiResponse[ApiClientResponse],
    summary="註銷 API Client(軟刪除;active 密鑰同交易全數撤銷,清單不再顯示)",
)
async def delete_api_client(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientResponse]:
    data = await ApiClientService(db).delete_client(uid, actor_uid=user.uid)
    return success(data=data)


@router.get(
    "/{uid}/secrets",
    response_model=ApiResponse[ApiClientSecretListResponse],
    summary="密鑰清單(含 active / retired;排除軟刪,永不含明文與雜湊)",
)
async def list_api_client_secrets(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientSecretListResponse]:
    data = await ApiClientService(db).list_secrets(uid)
    return success(data=data)


@router.get(
    "/{uid}/secrets/{secret_uid}/reveal",
    response_model=ApiResponse[ApiClientSecretRevealResponse],
    summary="檢視密鑰明文(admin 專用;舊密鑰無加密明文 → 409)",
)
async def reveal_api_client_secret(
    uid: UUID,
    secret_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientSecretRevealResponse]:
    data = await ApiClientService(db).reveal_secret(uid, secret_uid, actor_uid=user.uid)
    return success(data=data)


@router.get(
    "/{uid}/effective-permissions",
    response_model=ApiResponse[EffectivePermissionsResponse],
    summary=(
        "最終可見欄位預覽(角色綁定的角色權限設定檔 ∪ 未過期臨時權限,"
        "再 ∩ 作業範圍;default-closed)"
    ),
)
async def get_api_client_effective_permissions(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[EffectivePermissionsResponse]:
    data = await EffectivePermissionService(db).preview(uid)
    return success(data=data)


@router.post(
    "/{uid}/rotate-secret",
    response_model=ApiResponse[ApiClientSecretIssuedResponse],
    summary="輪替密鑰:核發新 active 並自動撤銷舊鑰(單一密鑰制)",
)
async def rotate_api_client_secret(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientSecretIssuedResponse]:
    data = await ApiClientService(db).rotate_secret(uid, actor_uid=user.uid)
    return success(data=data)


@router.post(
    "/{uid}/secrets/{secret_uid}/retire",
    response_model=ApiResponse[ApiClientResponse],
    summary="汰換指定密鑰(改 retired,軟性不刪列;最後一把亦允許)",
)
async def retire_api_client_secret(
    uid: UUID,
    secret_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ApiClientResponse]:
    data = await ApiClientService(db).retire_secret(uid, secret_uid, actor_uid=user.uid)
    return success(data=data)
