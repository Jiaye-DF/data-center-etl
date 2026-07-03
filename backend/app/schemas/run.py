from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RunSummaryResponse(BaseModel):
    uid: UUID
    trigger_type: str
    status: str
    schedule_uid: UUID | None
    schedule_name: str | None
    started_at: datetime | None
    finished_at: datetime | None
    total_tables: int
    success_tables: int
    failed_tables: int
    error_message: str | None
    created_at: datetime


class RunListResponse(BaseModel):
    items: list[RunSummaryResponse]
    total: int
    page: int
    page_size: int


class RunLogResponse(BaseModel):
    uid: UUID
    etl_table_uid: UUID | None
    source_schema: str
    source_table: str
    status: str
    row_count: int | None
    duration_ms: int | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    error_stack: str | None


class RunLogListResponse(BaseModel):
    items: list[RunLogResponse]
    total: int
    page: int
    page_size: int


class RunTriggerRequest(BaseModel):
    # NULL 表示對全部啟用表執行一輪;指定則只跑該表
    etl_table_uid: UUID | None = None


class RunTriggerResponse(BaseModel):
    task_id: str
    # 佇列模式(redis broker)下 run 由 worker 建立,enqueue 當下尚無 run → None;
    # 就地執行 broker(InMemoryBroker)則可直接回傳新建 run 的 uid
    run_uid: UUID | None
