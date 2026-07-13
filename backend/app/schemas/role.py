from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    code: str = Field(description="角色代碼(admin / member)")
    name: str = Field(description="顯示名稱")
    description: str | None = Field(default=None, description="描述")


class RoleListResponse(BaseModel):
    items: list[RoleResponse] = Field(description="角色清單")
