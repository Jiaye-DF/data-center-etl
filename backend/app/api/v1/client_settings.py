"""權限階層管理 API(v1.6.1 task-004):`/api/v1/client-settings` 前綴,admin 專用。

真身在目標 RDS `client_setting` schema(propose v1.6.1),本路由只做參數驗證與封套;
交易 / 稽核 / 快取失效全在 `client_setting_service.py`。

- 服務:`GET|POST /services`、`PATCH|DELETE /services/{uid}`(code 建立後不可改;
  底下仍有作業不得刪)。
- 作業:`GET|POST /operations`、`PATCH|DELETE /operations/{uid}`(歸屬服務不可改;
  被角色權限設定檔 / 臨時權限組引用不得刪)。
- 作業範圍:`GET|PUT /operations/{uid}/items`(整批置換;表 / 欄位須為 confirmed 語意映射)。
- 角色權限設定檔:`GET|POST /profiles`、`PATCH|DELETE /profiles/{uid}`(被角色綁不得刪);
  `GET|PUT /profiles/{uid}/operations`(勾選可讀作業整批置換);
  `GET|PUT /profiles/{uid}/operations/{operation_uid}/items`(授權矩陣整批置換)。
- 角色:`GET|POST /roles`、`PATCH|DELETE /roles/{uid}`(必綁 1 角色權限設定檔;被 Client 指派
  不得刪)。與既有 `/api/v1/roles`(後台人員角色)分屬不同資源,勿混用。
- 臨時權限組(task-006):`GET|POST /exception-sets`、`PATCH|DELETE /exception-sets/{uid}`
  (可重用,同一組可綁多個 Client;仍被未過期綁定引用不得刪);內容維護端點與角色權限設定檔對稱
  ——`GET|PUT /exception-sets/{uid}/operations`、
  `GET|PUT /exception-sets/{uid}/operations/{operation_uid}/items`。
- API Client 指派(task-006):以 client uid 定位於本前綴下,不動既有 `/api/v1/api-clients`
  資源(預覽端點 `GET /api-clients/{uid}/effective-permissions` 屬 task-007)。
  `PUT|DELETE /clients/{client_uid}/role`(0..1,PUT 冪等置換);
  `GET|POST /clients/{client_uid}/exception-sets`、
  `DELETE /clients/{client_uid}/exception-sets/{binding_uid}`(0..N,綁定帶效期)。

router 已於 `api/v1/__init__.py` 註冊(task-004 一次完成,後續 task 不再動該檔)。
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.client_setting import (
    ClientExceptionSetBindRequest,
    ClientExceptionSetListResponse,
    ClientExceptionSetResponse,
    ClientRoleAssignRequest,
    ClientRoleResponse,
    ExceptionItemListResponse,
    ExceptionItemsReplaceRequest,
    ExceptionOperationListResponse,
    ExceptionOperationsReplaceRequest,
    ExceptionSetCreateRequest,
    ExceptionSetListResponse,
    ExceptionSetResponse,
    ExceptionSetUpdateRequest,
    OperationCreateRequest,
    OperationItemListResponse,
    OperationItemsReplaceRequest,
    OperationListResponse,
    OperationResponse,
    OperationUpdateRequest,
    PermissionProfileCreateRequest,
    PermissionProfileListResponse,
    PermissionProfileResponse,
    PermissionProfileUpdateRequest,
    ProfileItemListResponse,
    ProfileItemsReplaceRequest,
    ProfileOperationListResponse,
    ProfileOperationsReplaceRequest,
    RoleCreateRequest,
    RoleListResponse,
    RoleResponse,
    RoleUpdateRequest,
    ServiceCreateRequest,
    ServiceListResponse,
    ServiceResponse,
    ServiceUpdateRequest,
)
from app.schemas.response import ApiResponse
from app.services.client_setting_service import ClientSettingService

router = APIRouter()


# ── 服務 ──────────────────────────────────────────────────────────────
@router.get(
    "/services",
    response_model=ApiResponse[ServiceListResponse],
    summary="服務清單(admin 專用;讀取走 Redis 快取,排除軟刪)",
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
    summary="建立服務(code 未刪列唯一,重複 409)",
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
    summary="更新服務(名稱 / 說明;code 為路由分段契約不可改)",
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
    summary="刪除服務(軟刪;底下仍有作業 409,不做連鎖刪除)",
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
    summary="作業清單(可依服務過濾;讀取走 Redis 快取)",
)
async def list_operations(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    service_uid: Annotated[UUID | None, Query(description="歸屬服務;省略即全部")] = None,
) -> ApiResponse[OperationListResponse]:
    data = await ClientSettingService(db).list_operations(service_uid=service_uid)
    return success(data=data)


@router.post(
    "/operations",
    response_model=ApiResponse[OperationResponse],
    status_code=201,
    summary="建立作業(name 於同一服務內唯一,重複 409)",
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
    summary="更新作業(名稱 / 說明;歸屬服務不可改)",
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
    summary="刪除作業(軟刪,範圍項連動;被角色權限設定檔 / 臨時權限組引用 409)",
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


# ── 角色權限設定檔 ──────────────────────────────────────────────────────────
@router.get(
    "/profiles",
    response_model=ApiResponse[PermissionProfileListResponse],
    summary="角色權限設定檔清單(讀取走 Redis 快取,排除軟刪)",
)
async def list_permission_profiles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[PermissionProfileListResponse]:
    data = await ClientSettingService(db).list_permission_profiles()
    return success(data=data)


@router.post(
    "/profiles",
    response_model=ApiResponse[PermissionProfileResponse],
    status_code=201,
    summary="建立角色權限設定檔(name 未刪列唯一,重複 409)",
)
async def create_permission_profile(
    payload: PermissionProfileCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[PermissionProfileResponse]:
    data = await ClientSettingService(db).create_permission_profile(
        payload, actor_uid=user.uid
    )
    return success(data=data, response_code=201)


@router.patch(
    "/profiles/{uid}",
    response_model=ApiResponse[PermissionProfileResponse],
    summary="更新角色權限設定檔(名稱 / 說明)",
)
async def update_permission_profile(
    uid: UUID,
    payload: PermissionProfileUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[PermissionProfileResponse]:
    data = await ClientSettingService(db).update_permission_profile(
        uid, payload, actor_uid=user.uid
    )
    return success(data=data)


@router.delete(
    "/profiles/{uid}",
    response_model=ApiResponse[PermissionProfileResponse],
    summary="刪除角色權限設定檔(軟刪,勾選 / 授權連動;仍被角色綁定 409)",
)
async def delete_permission_profile(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[PermissionProfileResponse]:
    data = await ClientSettingService(db).delete_permission_profile(uid, actor_uid=user.uid)
    return success(data=data)


# ── 角色權限設定檔勾選作業 ──────────────────────────────────────────────────────
@router.get(
    "/profiles/{uid}/operations",
    response_model=ApiResponse[ProfileOperationListResponse],
    summary="角色權限設定檔已勾選的可讀作業",
)
async def list_profile_operations(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ProfileOperationListResponse]:
    data = await ClientSettingService(db).list_profile_operations(uid)
    return success(data=data)


@router.put(
    "/profiles/{uid}/operations",
    response_model=ApiResponse[ProfileOperationListResponse],
    summary="整批置換勾選作業(取消勾選的作業其授權項同交易清除;不存在的作業 422)",
)
async def replace_profile_operations(
    uid: UUID,
    payload: ProfileOperationsReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ProfileOperationListResponse]:
    data = await ClientSettingService(db).replace_profile_operations(
        uid, payload, actor_uid=user.uid
    )
    return success(data=data)


# ── 角色權限設定檔授權矩陣(作業 × 表 × 欄位 × read/edit)──────────────────────
@router.get(
    "/profiles/{uid}/operations/{operation_uid}/items",
    response_model=ApiResponse[ProfileItemListResponse],
    summary="角色權限設定檔在單一作業下的授權項",
)
async def list_profile_items(
    uid: UUID,
    operation_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ProfileItemListResponse]:
    data = await ClientSettingService(db).list_profile_items(uid, operation_uid)
    return success(data=data)


@router.put(
    "/profiles/{uid}/operations/{operation_uid}/items",
    response_model=ApiResponse[ProfileItemListResponse],
    summary="整批置換授權矩陣(作業未勾選 409;超出作業範圍上限 / 非 confirmed 逐筆 422)",
)
async def replace_profile_items(
    uid: UUID,
    operation_uid: UUID,
    payload: ProfileItemsReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ProfileItemListResponse]:
    data = await ClientSettingService(db).replace_profile_items(
        uid, operation_uid, payload, actor_uid=user.uid
    )
    return success(data=data)


# ── 角色(API Client 角色;與後台人員角色 /api/v1/roles 不同資源)───────
@router.get(
    "/roles",
    response_model=ApiResponse[RoleListResponse],
    summary="角色清單(讀取走 Redis 快取,排除軟刪)",
)
async def list_client_roles(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[RoleListResponse]:
    data = await ClientSettingService(db).list_roles()
    return success(data=data)


@router.post(
    "/roles",
    response_model=ApiResponse[RoleResponse],
    status_code=201,
    summary="建立角色(必帶 permission_profile_uid,缺值 422;name 未刪列唯一 409)",
)
async def create_client_role(
    payload: RoleCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[RoleResponse]:
    data = await ClientSettingService(db).create_role(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/roles/{uid}",
    response_model=ApiResponse[RoleResponse],
    summary="更新角色(可改綁角色權限設定檔;顯式清空 permission_profile_uid 422)",
)
async def update_client_role(
    uid: UUID,
    payload: RoleUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[RoleResponse]:
    data = await ClientSettingService(db).update_role(uid, payload, actor_uid=user.uid)
    return success(data=data)


@router.delete(
    "/roles/{uid}",
    response_model=ApiResponse[RoleResponse],
    summary="刪除角色(軟刪;仍被 API Client 指派 409)",
)
async def delete_client_role(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[RoleResponse]:
    data = await ClientSettingService(db).delete_role(uid, actor_uid=user.uid)
    return success(data=data)


# ── 臨時權限組(可重用;結構同角色權限設定檔)──────────────────────────────────
@router.get(
    "/exception-sets",
    response_model=ApiResponse[ExceptionSetListResponse],
    summary="臨時權限組清單(讀取走 Redis 快取,排除軟刪)",
)
async def list_exception_sets(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionSetListResponse]:
    data = await ClientSettingService(db).list_exception_sets()
    return success(data=data)


@router.post(
    "/exception-sets",
    response_model=ApiResponse[ExceptionSetResponse],
    status_code=201,
    summary="建立臨時權限組(name 未刪列唯一,重複 409)",
)
async def create_exception_set(
    payload: ExceptionSetCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionSetResponse]:
    data = await ClientSettingService(db).create_exception_set(payload, actor_uid=user.uid)
    return success(data=data, response_code=201)


@router.patch(
    "/exception-sets/{uid}",
    response_model=ApiResponse[ExceptionSetResponse],
    summary="更新臨時權限組(名稱 / 說明)",
)
async def update_exception_set(
    uid: UUID,
    payload: ExceptionSetUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionSetResponse]:
    data = await ClientSettingService(db).update_exception_set(
        uid, payload, actor_uid=user.uid
    )
    return success(data=data)


@router.delete(
    "/exception-sets/{uid}",
    response_model=ApiResponse[ExceptionSetResponse],
    summary="刪除臨時權限組(軟刪,勾選 / 授權連動;仍被未過期綁定引用 409)",
)
async def delete_exception_set(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionSetResponse]:
    data = await ClientSettingService(db).delete_exception_set(uid, actor_uid=user.uid)
    return success(data=data)


# ── 臨時權限組勾選作業 / 授權矩陣(語意同角色權限設定檔)──────────────────────────
@router.get(
    "/exception-sets/{uid}/operations",
    response_model=ApiResponse[ExceptionOperationListResponse],
    summary="臨時權限組已勾選的可讀作業",
)
async def list_exception_operations(
    uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionOperationListResponse]:
    data = await ClientSettingService(db).list_exception_operations(uid)
    return success(data=data)


@router.put(
    "/exception-sets/{uid}/operations",
    response_model=ApiResponse[ExceptionOperationListResponse],
    summary="整批置換勾選作業(取消勾選的作業其授權項同交易清除;不存在的作業 422)",
)
async def replace_exception_operations(
    uid: UUID,
    payload: ExceptionOperationsReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionOperationListResponse]:
    data = await ClientSettingService(db).replace_exception_operations(
        uid, payload, actor_uid=user.uid
    )
    return success(data=data)


@router.get(
    "/exception-sets/{uid}/operations/{operation_uid}/items",
    response_model=ApiResponse[ExceptionItemListResponse],
    summary="臨時權限組在單一作業下的授權項",
)
async def list_exception_items(
    uid: UUID,
    operation_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionItemListResponse]:
    data = await ClientSettingService(db).list_exception_items(uid, operation_uid)
    return success(data=data)


@router.put(
    "/exception-sets/{uid}/operations/{operation_uid}/items",
    response_model=ApiResponse[ExceptionItemListResponse],
    summary="整批置換授權矩陣(作業未勾選 409;超出作業範圍上限 / 非 confirmed 逐筆 422)",
)
async def replace_exception_items(
    uid: UUID,
    operation_uid: UUID,
    payload: ExceptionItemsReplaceRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ExceptionItemListResponse]:
    data = await ClientSettingService(db).replace_exception_items(
        uid, operation_uid, payload, actor_uid=user.uid
    )
    return success(data=data)


# ── API Client 的角色指派(0..1)─────────────────────────────────────
@router.put(
    "/clients/{client_uid}/role",
    response_model=ApiResponse[ClientRoleResponse],
    summary="指派 / 改指派角色(冪等置換;Client 或角色不存在 404)",
)
async def assign_client_role(
    client_uid: UUID,
    payload: ClientRoleAssignRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ClientRoleResponse]:
    data = await ClientSettingService(db).assign_client_role(
        client_uid, payload, actor_uid=user.uid
    )
    return success(data=data)


@router.delete(
    "/clients/{client_uid}/role",
    response_model=ApiResponse[ClientRoleResponse],
    summary="解除角色指派(本來就沒指派 404)",
)
async def remove_client_role(
    client_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ClientRoleResponse]:
    data = await ClientSettingService(db).remove_client_role(
        client_uid, actor_uid=user.uid
    )
    return success(data=data)


# ── API Client 的臨時權限組綁定(0..N,各自效期)──────────────────────────
@router.get(
    "/clients/{client_uid}/exception-sets",
    response_model=ApiResponse[ClientExceptionSetListResponse],
    summary="臨時權限綁定清單(含已過期,以 is_expired 標示)",
)
async def list_client_exception_sets(
    client_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ClientExceptionSetListResponse]:
    data = await ClientSettingService(db).list_client_exception_sets(client_uid)
    return success(data=data)


@router.post(
    "/clients/{client_uid}/exception-sets",
    response_model=ApiResponse[ClientExceptionSetResponse],
    status_code=201,
    summary="綁定臨時權限組(expires_at 省略 = 不設限;重複綁同組 409)",
)
async def bind_client_exception_set(
    client_uid: UUID,
    payload: ClientExceptionSetBindRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ClientExceptionSetResponse]:
    data = await ClientSettingService(db).bind_client_exception_set(
        client_uid, payload, actor_uid=user.uid
    )
    return success(data=data, response_code=201)


@router.delete(
    "/clients/{client_uid}/exception-sets/{binding_uid}",
    response_model=ApiResponse[ClientExceptionSetResponse],
    summary="解除單筆臨時權限綁定(以綁定列 uid 定位;不屬於該 Client 404)",
)
async def unbind_client_exception_set(
    client_uid: UUID,
    binding_uid: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[ClientExceptionSetResponse]:
    data = await ClientSettingService(db).unbind_client_exception_set(
        client_uid, binding_uid, actor_uid=user.uid
    )
    return success(data=data)
