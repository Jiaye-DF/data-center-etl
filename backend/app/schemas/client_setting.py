"""權限階層管理 API 的 Pydantic schema(v1.6.1 task-004;真身在 RDS `client_setting`)。

- 對外一律 `uid`,**禁**曝內部主鍵 `pid`;父子歸屬同樣以 uid 表達(如 `service_uid`)。
- 時間欄位為 naive UTC+8(RDS datetime2 等價慣例,`04-databases/06-timezone.md`)。
- 表 / 欄位名採**語意層英文名**(與資料 API 回傳 JSON key 同一套);`column_name = '*'`
  代表該表全欄位。合法性(須為 confirmed 語意映射)由 service 層驗證,非 schema 層。
- task-005 / 006 於本檔續加設定檔 / Role / 特例權限組的 schema,命名沿用
  `<實體><用途>Request` / `<實體>Response` / `<實體>ListResponse` 慣例。
"""

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# 系統別代碼對應資料 API 路由 `{service}` 分段 → 限小寫英數起頭的 URL 安全字元
SERVICE_CODE_PATTERN = r"^[a-z0-9][a-z0-9_-]*$"


# ── 系統別 services ────────────────────────────────────────────────────
class ServiceResponse(BaseModel):
    uid: UUID = Field(description="系統別對外識別碼")
    code: str = Field(description="系統別代碼(erp / crm / hrm…;建立後不可改)")
    name: str = Field(description="系統別名稱")
    description: str | None = Field(default=None, description="說明")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間(Asia/Taipei wall-clock)")


class ServiceListResponse(BaseModel):
    items: list[ServiceResponse] = Field(description="系統別清單(排除軟刪)")
    total: int = Field(description="總筆數")


class ServiceCreateRequest(BaseModel):
    code: str = Field(
        min_length=1,
        max_length=50,
        pattern=SERVICE_CODE_PATTERN,
        description="系統別代碼(小寫英數 / `-` / `_`;未刪列唯一)",
    )
    name: str = Field(min_length=1, max_length=100, description="系統別名稱")
    description: str | None = Field(default=None, description="說明")


class ServiceUpdateRequest(BaseModel):
    """部分更新;省略即不變更。`code` 為對外契約(路由分段)故不開放改。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="系統別名稱"
    )
    description: str | None = Field(default=None, description="說明")


# ── 作業 operations ────────────────────────────────────────────────────
class OperationResponse(BaseModel):
    uid: UUID = Field(description="作業對外識別碼")
    service_uid: UUID = Field(description="歸屬系統別對外識別碼")
    name: str = Field(description="作業名(同一系統別內唯一)")
    description: str | None = Field(default=None, description="業務動作說明")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間(Asia/Taipei wall-clock)")


class OperationListResponse(BaseModel):
    items: list[OperationResponse] = Field(description="作業清單(排除軟刪)")
    total: int = Field(description="總筆數")


class OperationCreateRequest(BaseModel):
    service_uid: UUID = Field(description="歸屬系統別(建立後不可改)")
    name: str = Field(min_length=1, max_length=100, description="作業名(系統別內唯一)")
    description: str | None = Field(default=None, description="業務動作說明")


class OperationUpdateRequest(BaseModel):
    """部分更新;省略即不變更。歸屬系統別(`service_uid`)不開放改。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="作業名(系統別內唯一)"
    )
    description: str | None = Field(default=None, description="業務動作說明")


# ── 作業範圍 operation_items ───────────────────────────────────────────
class ScopeItemRequest(BaseModel):
    table_name: str = Field(min_length=1, max_length=200, description="資料表(語意層英文名)")
    column_name: str = Field(
        min_length=1, max_length=200, description="欄位(語意層英文名;`*` = 全欄位)"
    )


class OperationItemResponse(BaseModel):
    uid: UUID = Field(description="範圍項對外識別碼")
    table_name: str = Field(description="資料表(語意層英文名)")
    column_name: str = Field(description="欄位(`*` = 全欄位)")


class OperationItemListResponse(BaseModel):
    items: list[OperationItemResponse] = Field(description="作業範圍項(排除軟刪)")
    total: int = Field(description="總筆數")


class OperationItemsReplaceRequest(BaseModel):
    """整批置換作業範圍:空陣列 = 清空範圍(非「不變更」)。"""

    items: list[ScopeItemRequest] = Field(description="置換後的完整範圍集合")


# ── 角色權限設定檔 permission_profiles(task-005)───────────────────────
class PermissionProfileResponse(BaseModel):
    uid: UUID = Field(description="設定檔對外識別碼")
    name: str = Field(description="設定檔名(唯一)")
    description: str | None = Field(default=None, description="說明")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間(Asia/Taipei wall-clock)")


class PermissionProfileListResponse(BaseModel):
    items: list[PermissionProfileResponse] = Field(description="設定檔清單(排除軟刪)")
    total: int = Field(description="總筆數")


class PermissionProfileCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="設定檔名(未刪列唯一)")
    description: str | None = Field(default=None, description="說明")


class PermissionProfileUpdateRequest(BaseModel):
    """部分更新;省略即不變更。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="設定檔名(未刪列唯一)"
    )
    description: str | None = Field(default=None, description="說明")


# ── 設定檔勾選作業 profile_operations ──────────────────────────────────
class ProfileOperationResponse(BaseModel):
    uid: UUID = Field(description="勾選列對外識別碼")
    operation_uid: UUID = Field(description="勾選的作業")


class ProfileOperationListResponse(BaseModel):
    items: list[ProfileOperationResponse] = Field(description="已勾選作業(排除軟刪)")
    total: int = Field(description="總筆數")


class ProfileOperationsReplaceRequest(BaseModel):
    """整批置換勾選作業:空陣列 = 全部取消勾選(移除的作業其授權項同交易清除)。"""

    operation_uids: list[UUID] = Field(description="置換後的完整勾選作業集合")


# ── 設定檔授權矩陣 profile_items ───────────────────────────────────────
# 與 `models.client_setting.ACTION_READ / ACTION_EDIT` 同一組值;動作為固定列舉,
# 合法性於 schema 層擋下(FastAPI 自動 422),service 層只驗「∩ 作業範圍」等業務規則
PermissionAction = Literal["read", "edit"]


class PermissionItemRequest(BaseModel):
    table_name: str = Field(min_length=1, max_length=200, description="資料表(語意層英文名)")
    column_name: str = Field(
        min_length=1, max_length=200, description="欄位(語意層英文名;`*` = 全欄位)"
    )
    action: PermissionAction = Field(description="動作(read / edit;edit 含新增 / 更新 / 軟刪)")


class ProfileItemResponse(BaseModel):
    uid: UUID = Field(description="授權項對外識別碼")
    table_name: str = Field(description="資料表(語意層英文名)")
    column_name: str = Field(description="欄位(`*` = 全欄位)")
    action: PermissionAction = Field(description="動作(read / edit)")


class ProfileItemListResponse(BaseModel):
    items: list[ProfileItemResponse] = Field(description="該作業下的授權項(排除軟刪)")
    total: int = Field(description="總筆數")


class ProfileItemsReplaceRequest(BaseModel):
    """整批置換「設定檔 × 單一作業」的授權矩陣:空陣列 = 該作業下無任何欄位授權。"""

    items: list[PermissionItemRequest] = Field(description="置換後的完整授權集合")


# ── Role roles ─────────────────────────────────────────────────────────
class RoleResponse(BaseModel):
    uid: UUID = Field(description="Role 對外識別碼")
    permission_profile_uid: UUID = Field(description="綁定的權限設定檔(必綁)")
    name: str = Field(description="角色名(唯一)")
    description: str | None = Field(default=None, description="說明")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間(Asia/Taipei wall-clock)")


class RoleListResponse(BaseModel):
    items: list[RoleResponse] = Field(description="Role 清單(排除軟刪)")
    total: int = Field(description="總筆數")


class RoleCreateRequest(BaseModel):
    """建立 Role;`permission_profile_uid` 為必帶欄位(禁空角色,缺值即 422)。"""

    permission_profile_uid: UUID = Field(description="綁定的權限設定檔(必綁)")
    name: str = Field(min_length=1, max_length=100, description="角色名(未刪列唯一)")
    description: str | None = Field(default=None, description="說明")


class RoleUpdateRequest(BaseModel):
    """部分更新;省略即不變更。設定檔可改綁,但**不可清空**(顯式 null 即 422)。"""

    permission_profile_uid: UUID | None = Field(
        default=None, description="改綁的權限設定檔;省略即不變更"
    )
    name: str | None = Field(
        default=None, min_length=1, max_length=100, description="角色名(未刪列唯一)"
    )
    description: str | None = Field(default=None, description="說明")

    @model_validator(mode="after")
    def _reject_cleared_profile(self) -> Self:
        if (
            "permission_profile_uid" in self.model_fields_set
            and self.permission_profile_uid is None
        ):
            raise ValueError("Role 必綁 1 個權限設定檔,permission_profile_uid 不可清空")
        return self
