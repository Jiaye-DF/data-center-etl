from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cron_expr: str = Field(min_length=1, max_length=100)
    is_enabled: bool = True
    # NULL 表示對全部啟用表執行(對齊 schedules.etl_table_pid 語意)
    etl_table_uid: UUID | None = None
    description: str | None = None


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    cron_expr: str | None = Field(default=None, min_length=1, max_length=100)
    etl_table_uid: UUID | None = None
    description: str | None = None


class ScheduleResponse(BaseModel):
    uid: UUID
    name: str
    cron_expr: str
    is_enabled: bool
    etl_table_uid: UUID | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class ScheduleListResponse(BaseModel):
    items: list[ScheduleResponse]
    total: int
    page: int
    page_size: int


class ScheduleDeleteResponse(BaseModel):
    message: str
