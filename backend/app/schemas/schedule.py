from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ScheduleCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200, description="排程名稱(唯一)")
    cron_expr: str = Field(
        min_length=1, max_length=100, description="cron 表達式(以 UTC+8 解讀)"
    )
    is_enabled: bool = Field(default=True, description="是否啟用(停用排程不派工)")
    etl_table_uid: UUID | None = Field(
        default=None, description="指定只跑該表;null 表示對全部啟用表執行"
    )
    description: str | None = Field(default=None, description="排程用途描述")


class ScheduleUpdateRequest(BaseModel):
    name: str | None = Field(
        default=None, min_length=1, max_length=200, description="排程名稱(不改則省略)"
    )
    cron_expr: str | None = Field(
        default=None, min_length=1, max_length=100,
        description="cron 表達式(UTC+8;不改則省略)",
    )
    etl_table_uid: UUID | None = Field(
        default=None, description="指定只跑該表;null 表示對全部啟用表執行"
    )
    description: str | None = Field(default=None, description="排程用途描述")


class ScheduleResponse(BaseModel):
    uid: UUID = Field(description="排程公開識別碼")
    name: str = Field(description="排程名稱")
    cron_expr: str = Field(description="cron 表達式(UTC+8 解讀)")
    is_enabled: bool = Field(description="是否啟用(停用排程不派工)")
    etl_table_uid: UUID | None = Field(description="指定表 uid;null 表示全部啟用表")
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
