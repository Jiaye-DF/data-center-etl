from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RoleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: UUID = Field(description="角色公開識別碼")
    code: str = Field(description="角色代碼(唯一)")
    name: str = Field(description="顯示名稱")
    description: str | None = Field(default=None, description="描述")
    is_builtin: bool = Field(description="系統內建標記(禁刪 / 禁改代碼)")


class RoleListResponse(BaseModel):
    items: list[RoleResponse] = Field(description="角色清單")
