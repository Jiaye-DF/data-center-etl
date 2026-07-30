from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ApiClientResponse(BaseModel):
    """API Client 單筆回應(對外只給 uid;永不含 secret_hash / pid)。"""

    uid: UUID = Field(description="API Client 公開識別碼")
    client_id: str = Field(description="取 token 用識別碼(dc_ + 24 字元 hex)")
    name: str = Field(description="應用系統名稱")
    description: str | None = Field(default=None, description="用途說明")
    status: str = Field(description="狀態(enabled / disabled;disabled 即拒發 token)")
    rate_limit_per_minute: int = Field(description="每分鐘請求上限")
    rate_limit_per_10min: int = Field(description="每 10 分鐘請求上限")
    active_secret_count: int = Field(description="有效(active)密鑰把數(單一密鑰制,恆為 0 或 1)")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")


class ApiClientListResponse(BaseModel):
    items: list[ApiClientResponse] = Field(description="API Client 清單(排除軟刪)")
    total: int = Field(description="總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class ApiClientCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="應用系統名稱")
    description: str | None = Field(default=None, description="用途說明")


class ApiClientUpdateRequest(BaseModel):
    """部分更新;省略即不變更(client_id 不可改)。"""

    name: str | None = Field(
        default=None, min_length=1, max_length=255, description="應用系統名稱"
    )
    description: str | None = Field(default=None, description="用途說明")
    status: Literal["enabled", "disabled"] | None = Field(
        default=None, description="狀態(enabled / disabled)"
    )
    rate_limit_per_minute: int | None = Field(
        default=None, ge=1, description="每分鐘請求上限(≥ 1)"
    )
    rate_limit_per_10min: int | None = Field(
        default=None, ge=1, description="每 10 分鐘請求上限(≥ 1)"
    )


class ApiClientCreatedResponse(BaseModel):
    """建立結果;`client_secret` 明文即時回傳(DB 存 bcrypt 雜湊 + 可逆加密明文)。"""

    client: ApiClientResponse = Field(description="新建的 API Client")
    secret_uid: UUID = Field(description="初始密鑰公開識別碼(汰換時使用)")
    client_secret: str = Field(description="明文密鑰(admin 後續可於儀表板重新檢視)")


class ApiClientSecretIssuedResponse(BaseModel):
    """新核發密鑰;`client_secret` 明文即時回傳,admin 後續可於儀表板重新檢視。"""

    secret_uid: UUID = Field(description="新密鑰公開識別碼(汰換時使用)")
    client_secret: str = Field(description="明文密鑰(admin 後續可於儀表板重新檢視)")
    active_secret_count: int = Field(description="核發後有效密鑰把數")


class ApiClientSecretResponse(BaseModel):
    """密鑰單筆回應(永不含 secret_hash / pid;明文須另呼 reveal 端點)。"""

    uid: UUID = Field(description="密鑰公開識別碼(汰換時使用)")
    status: str = Field(description="狀態(active / retired)")
    created_at: datetime = Field(description="核發時間(Asia/Taipei wall-clock)")
    revealable: bool = Field(
        description="是否可檢視明文(false = task-009 前核發的舊密鑰,須輪替後才可檢視)"
    )


class ApiClientSecretListResponse(BaseModel):
    items: list[ApiClientSecretResponse] = Field(
        description="該 Client 全部密鑰(排除軟刪,依核發時間升冪)"
    )
    total: int = Field(description="總筆數")


class ApiClientSecretRevealResponse(BaseModel):
    """admin 檢視密鑰明文(user 裁定:secret 可逆加密儲存,僅 admin 後台可解密檢視)。"""

    secret_uid: UUID = Field(description="密鑰公開識別碼")
    client_secret: str = Field(description="解密後的明文密鑰")
