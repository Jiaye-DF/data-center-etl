from uuid import UUID

from pydantic import BaseModel, Field


class UserListItemResponse(BaseModel):
    uid: UUID = Field(description="使用者公開識別碼")
    username: str = Field(description="帳號")
    display_name: str | None = Field(
        default=None, description="顯示名稱(SSO 姓名;無則前端 fallback 帳號)"
    )
    provider: str = Field(description='登入來源:"local" | "sso"')
    role: str = Field(description="角色 code(admin / viewer)")


class UserListResponse(BaseModel):
    items: list[UserListItemResponse] = Field(description="使用者清單")
    total: int = Field(description="總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class RoleAssignRequest(BaseModel):
    role: str = Field(
        min_length=1, max_length=50, description="目標角色 code(如 admin / viewer)"
    )
