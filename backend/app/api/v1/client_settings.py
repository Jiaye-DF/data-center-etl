"""權限階層管理 API(v1.6.1 task-004):`/api/v1/client-settings` 前綴,admin 專用。

真身在目標 RDS `client_setting` schema(propose v1.6.1),本路由只做參數驗證與封套;
交易 / 稽核 / 快取失效全在 `client_setting_service.py`。

- 系統別:`GET|POST /services`、`PATCH|DELETE /services/{uid}`(code 建立後不可改;
  底下仍有作業不得刪)。
- 作業:`GET|POST /operations`、`PATCH|DELETE /operations/{uid}`(歸屬系統別不可改;
  被設定檔 / 特例組引用不得刪)。
- 作業範圍:`GET|PUT /operations/{uid}/items`(整批置換;表 / 欄位須為 confirmed 語意映射)。

task-005 / 006 於本檔續加設定檔 / Role / 特例權限組的路由(router 已於
`api/v1/__init__.py` 註冊,後續 task 不再動該檔)。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.client_setting import (
    OperationCreateRequest,
    OperationItemListResponse,
    OperationItemsReplaceRequest,
    OperationListResponse,
    OperationResponse,
    OperationUpdateRequest,
    ServiceCreateRequest,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdateRequest,
)
from app.schemas.response import ApiResponse
from app.services.client_setting_service import ClientSettingService

router = APIRouter()


# ── 系統別 ──────────────────────────────────────────────────────────────
@router.get(
    "/services",
    response_model=ApiResponse[ServiceListResponse],
    summary="系統別清單(admin 專用;讀取走 Redis 快取,排除軟刪)",
)
async def list_services(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ServiceListResponse]:
    data = await ClientSettingService(db).list_services()
    return success(data=data)


@router.post(
    "/services",
    response_model=ApiResponse[ServiceResponse],
    status_code=201,
    summary="建立系統別(code 未刪列唯一,重複 409)",
)
async def create_service(
    payload: ServiceCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ServiceResponse]:
    data = await ClientSettingService(db).create_service(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/services/{uid}",
    response_model=ApiResponse[ServiceResponse],
    summary="更新系統別(名稱 / 說明;code 為路由分段契約不可改)",
)
async def update_service(
    uid: UUID,
    payload: ServiceUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ServiceResponse]:
    data = await ClientSettingService(db).update_service(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/services/{uid}",
    response_model=ApiResponse[ServiceResponse],
    summary="刪除系統別(軟刪;底下仍有作業 409,不做連鎖刪除)",
)
async def delete_service(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ServiceResponse]:
    data = await ClientSettingService(db).delete_service(uid, actor_uid=user.uid)
    return success(data=data)


# ── 作業 ────────────────────────────────────────────────────────────────
@router.get(
    "/operations",
    response_model=ApiResponse[OperationListResponse],
    summary="作業清單(可依系統別過濾;讀取走 Redis 快取)",
)
async def list_operations(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    service_uid: Annotated[UUID | None, Query(description="歸屬系統別;省略即全部")] = None,
) -> ApiResponse[OperationListResponse]:
    data = await ClientSettingService(db).list_operations(service_uid=service_uid)
    return success(data=data)


@router.post(
    "/operations",
    response_model=ApiResponse[OperationResponse],
    status_code=201,
    summary="建立作業(name 於同一系統別內唯一,重複 409)",
)
async def create_operation(
    payload: OperationCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[OperationResponse]:
    data = await ClientSettingService(db).create_operation(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/operations/{uid}",
    response_model=ApiResponse[OperationResponse],
    summary="更新作業(名稱 / 說明;歸屬系統別不可改)",
)
async def update_operation(
    uid: UUID,
    payload: OperationUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[OperationResponse]:
    data = await ClientSettingService(db).update_operation(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/operations/{uid}",
    response_model=ApiResponse[OperationResponse],
    summary="刪除作業(軟刪,範圍項連動;被設定檔 / 特例組引用 409)",
)
async def delete_operation(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[OperationResponse]:
    data = await ClientSettingService(db).delete_operation(uid, actor_uid=user.uid)
    return success(data=data)


# ── 作業範圍(表 × 欄位)────────────────────────────────────────────────
@router.get(
    "/operations/{uid}/items",
    response_model=ApiResponse[OperationItemListResponse],
    summary="作業範圍清單(表 × 欄位;`*` = 全欄位)",
)
async def list_operation_items(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[OperationItemListResponse]:
    data = await ClientSettingService(db).list_operation_items(uid)
    return success(data=data)


@router.put(
    "/operations/{uid}/items",
    response_model=ApiResponse[OperationItemListResponse],
    summary="整批置換作業範圍(非 confirmed 語意映射的表 / 欄位逐筆列明 422)",
)
async def replace_operation_items(
    uid: UUID,
    payload: OperationItemsReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[OperationItemListResponse]:
    data = await ClientSettingService(db).replace_operation_items(
        uid, payload, actor_uid=user.uid
    )
    return success(data=data)
