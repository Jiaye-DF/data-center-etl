from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """稽核紀錄單筆回應(不含 pid / is_deleted 等內部欄)。"""

    model_config = ConfigDict(from_attributes=True)

    uid: UUID = Field(description="稽核紀錄對外識別碼(UUID)")
    actor_uid: UUID | None = Field(
        default=None, description="操作者 uid(登入失敗等匿名事件為 null)"
    )
    actor_username: str | None = Field(
        default=None, description="操作者帳號(事件當下快照)"
    )
    action: str = Field(
        description="事件類型(login_success / login_failed / schedule_create ...)"
    )
    target_type: str | None = Field(
        default=None, description="目標物件類型(etl_table / schedule / etl_run ...)"
    )
    target_uid: UUID | None = Field(default=None, description="目標物件 uid")
    detail: str | None = Field(
        default=None, description="事件摘要(繁中;不含任何密碼 / token 內容)"
    )
    created_at: datetime = Field(description="事件時間(UTC+8)")


class AuditLogListResponse(BaseModel):
    """稽核紀錄清單回應(分頁,最新在前)。"""

    items: list[AuditLogResponse] = Field(description="稽核紀錄清單(最新在前)")
    total: int = Field(description="總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")
