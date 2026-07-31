"""權限階層管理 API 的 Pydantic schema(v1.6.1 task-004;真身在 RDS `client_setting`)。

- 對外一律 `uid`,**禁**曝內部主鍵 `pid`;父子歸屬同樣以 uid 表達(如 `service_uid`)。
- 時間欄位為 naive UTC+8(RDS datetime2 等價慣例,`04-databases/06-timezone.md`)。
- 表 / 欄位名採**語意層英文名**(與資料 API 回傳 JSON key 同一套);`column_name = '*'`
  代表該表全欄位。合法性(須為 confirmed 語意映射)由 service 層驗證,非 schema 層。
- task-005 / 006 於本檔續加設定檔 / Role / 特例權限組的 schema,命名沿用
  `<實體><用途>Request` / `<實體>Response` / `<實體>ListResponse` 慣例。
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

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
