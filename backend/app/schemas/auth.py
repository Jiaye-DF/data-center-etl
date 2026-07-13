from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100, description="帳號")
    password: str = Field(min_length=1, description="密碼(不落 log)")


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: UUID = Field(description="使用者公開識別碼")
    username: str = Field(description="帳號")
    display_name: str | None = Field(
        default=None, description="顯示名稱(SSO 姓名;無則前端 fallback 帳號)"
    )
    role: str = Field(description="角色:admin(可寫)/ member(唯讀)")
    provider: str = Field(
        default="local",
        description='登入來源(模式 B 分流依據;08-df-sso.md):"local" | "sso"',
    )


class LogoutResponse(BaseModel):
    message: str = Field(description="操作結果訊息")
