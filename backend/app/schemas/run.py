from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    """etl_runs 狀態(對齊 DB CHECK 約束;`partial` 已依 scan AD-004 決策移除,
    任一表失敗即整輪 failed,無部分成功狀態)。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class RunLogStatus(StrEnum):
    """etl_run_logs 單表狀態(對齊 DB CHECK 約束)。"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerType(StrEnum):
    """執行觸發方式。"""

    SCHEDULE = "schedule"
    MANUAL = "manual"


class RunSummaryResponse(BaseModel):
    uid: UUID = Field(description="執行紀錄公開識別碼")
    trigger_type: TriggerType = Field(description="觸發方式:schedule(排程)/ manual(手動)")
    status: RunStatus = Field(description="整輪狀態:pending / running / success / failed")
    schedule_uid: UUID | None = Field(description="觸發排程 uid(手動觸發為 null)")
    schedule_name: str | None = Field(description="觸發排程名稱(手動觸發為 null)")
    started_at: datetime | None = Field(description="開始時間(Asia/Taipei wall-clock)")
    finished_at: datetime | None = Field(description="結束時間(執行中為 null)")
    total_tables: int = Field(description="本輪處理表總數(含 skipped)")
    success_tables: int = Field(description="成功表數")
    failed_tables: int = Field(description="失敗表數")
    error_message: str | None = Field(description="整輪錯誤摘要(全綠為 null)")
    created_at: datetime = Field(description="紀錄建立時間(Asia/Taipei wall-clock)")


class RunListResponse(BaseModel):
    items: list[RunSummaryResponse] = Field(description="執行紀錄清單(最新在前)")
    total: int = Field(description="符合過濾條件的總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class RunLogResponse(BaseModel):
    uid: UUID = Field(description="逐表 log 公開識別碼")
    etl_table_uid: UUID | None = Field(description="對應納管表 uid(表已移除納管為 null)")
    source_schema: str = Field(description="來源 schema")
    source_table: str = Field(description="來源表名(多來源為逗號合併,見 fixed.md §2)")
    status: RunLogStatus = Field(
        description="單表狀態:pending / running / success / failed / skipped"
    )
    row_count: int | None = Field(description="寫入筆數(失敗 / skipped 為 null)")
    duration_ms: int | None = Field(description="耗時毫秒")
    started_at: datetime | None = Field(description="單表開始時間")
    finished_at: datetime | None = Field(description="單表結束時間")
    error_message: str | None = Field(description="錯誤訊息(機密已遮罩;成功為 null)")
    error_stack: str | None = Field(description="stack trace(機密已遮罩;成功為 null)")


class RunLogListResponse(BaseModel):
    items: list[RunLogResponse] = Field(description="逐表詳細 log 清單")
    total: int = Field(description="符合過濾條件的總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class RunTriggerRequest(BaseModel):
    etl_table_uid: UUID | None = Field(
        default=None, description="指定只跑該表;null 表示對全部啟用表執行一輪"
    )


class RunTriggerResponse(BaseModel):
    task_id: str = Field(description="taskiq 任務識別碼")
    run_uid: UUID | None = Field(
        description=(
            "新建 run 的 uid;佇列模式(redis broker)下 run 由 worker 建立,"
            "enqueue 當下尚無 run → null(見 fixed.md §15)"
        )
    )
