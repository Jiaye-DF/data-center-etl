from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ScheduleUpdateRequest(BaseModel):
    """更新排程(僅 cron / 啟停 / 描述;v1.3.1 起禁改綁定來源表)。"""

    cron_expr: str | None = Field(
        default=None, min_length=1, max_length=100,
        description="cron 表達式(UTC+8;不改則省略)",
    )
    is_enabled: bool | None = Field(
        default=None, description="是否啟用(停用排程不派工;不改則省略)"
    )
    description: str | None = Field(default=None, description="排程用途描述")


class ScheduleResponse(BaseModel):
    uid: UUID = Field(description="排程公開識別碼")
    name: str = Field(description="排程名稱(一表一排程為 schema.table)")
    cron_expr: str = Field(description="cron 表達式(UTC+8 解讀)")
    is_enabled: bool = Field(description="是否啟用(停用排程不派工)")
    job_desc: str = Field(description="此排程做什麼(固定為增量同步全部表)")
    last_run_status: str | None = Field(
        description="上次執行狀態(pending/running/success/failed;無執行為 null)"
    )
    last_run_finished_at: datetime | None = Field(
        description="上次執行結束時間(無執行或尚未結束為 null)"
    )
    description: str | None = Field(description="排程用途描述")
    created_at: datetime = Field(description="建立時間(Asia/Taipei wall-clock)")
    updated_at: datetime = Field(description="最後更新時間")


class ScheduleTableViewItem(BaseModel):
    """逐表視角一列:來源表 meta × 其排程 × 每表最新執行結果(LEFT JOIN,無排程欄位為 null)。"""

    table_name: str = Field(description="來源表名稱")
    business_name: str | None = Field(description="業務資料名稱(快照落地;無則 null)")
    schedule_uid: UUID | None = Field(description="對應排程 uid(尚無排程為 null)")
    cron_expr: str | None = Field(description="cron 表達式(尚無排程為 null)")
    is_enabled: bool | None = Field(description="是否啟用(尚無排程為 null)")
    description: str | None = Field(description="排程用途描述")
    last_synced_at: datetime | None = Field(
        description="最近同步到 hub 的時間(未同步為 null)"
    )
    last_run_status: str | None = Field(
        description="此表最新一次執行狀態(pending/running/success/failed/skipped;無執行為 null)"
    )


class ScheduleTableViewListResponse(BaseModel):
    items: list[ScheduleTableViewItem] = Field(description="逐表視角清單")
    total: int = Field(description="符合過濾條件的總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class ScheduleSchemaSummary(BaseModel):
    schema_name: str = Field(description="schema 名稱")
    table_count: int = Field(description="該 schema 來源表數")
    enabled_count: int = Field(description="該 schema 已啟用排程數")


class ScheduleSchemaSummaryListResponse(BaseModel):
    items: list[ScheduleSchemaSummary] = Field(
        description="各 schema 摘要(依 schema 名排序)"
    )


class ScheduleBatchEnabledRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = Field(description="目標啟停狀態(true=啟用 / false=停用)")
    schema_name: str | None = Field(
        default=None,
        alias="schema",
        description="限定 schema(省略為全部 schema 的來源表排程)",
    )


class ScheduleBatchEnabledResponse(BaseModel):
    affected: int = Field(description="實際變更啟停狀態的排程筆數")
