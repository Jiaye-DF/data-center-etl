from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="排程名稱(唯一)")
    cron_expr: str = Field(
        min_length=1, max_length=100, description="cron 表達式(以 UTC+8 解讀)"
    )
    is_enabled: bool = Field(default=True, description="是否啟用(停用排程不派工)")
    description: str | None = Field(default=None, description="排程用途描述")


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="排程名稱(不改則省略)"
    )
    cron_expr: str | None = Field(
        default=None, min_length=1, max_length=100,
        description="cron 表達式(UTC+8;不改則省略)",
    )
    description: str | None = Field(default=None, description="排程用途描述")


class ScheduleResponse(BaseModel):
    uid: UUID = Field(description="排程公開識別碼")
    name: str = Field(description="排程名稱")
    cron_expr: str = Field(description="cron 表達式(UTC+8 解讀)")
    is_enabled: bool = Field(description="是否啟用(停用排程不派工)")
    job_desc: str = Field(description="此排程做什麼(固定為增量同步全部表)")
    last_run_status: str | None = Field(
        description="上次執行狀態(pending/running/success/partial/failed;無執行為 null)"
    )
    last_run_finished_at: datetime | None = Field(
        description="上次執行結束時間(無執行或尚未結束為 null)"
    )
    description: str | None = Field(description="排程用途描述")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間")


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse] = Field(description="排程清單")
    total: int = Field(description="總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class ScheduleDeleteResponse(BaseModel):
    message: str = Field(description="操作結果訊息")
