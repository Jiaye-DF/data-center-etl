from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CoverageScheduleInfo(BaseModel):
    """啟用中排程摘要(適用於所有來源表;下次執行由前端依 cron 推算)。"""

    name: str = Field(description="排程名稱")
    cron_expr: str = Field(description="cron 表達式(UTC+8 解讀)")


class TableCoverageItem(BaseModel):
    """單一來源表的排程涵蓋狀態(納入與否 + 上次同步 / 執行結果)。"""

    uid: UUID = Field(description="來源表快照公開識別碼")
    schema_name: str = Field(description="schema 名稱")
    table_name: str = Field(description="表名稱")
    business_name: str | None = Field(description="業務資料名稱(無則 null)")
    sync_excluded: bool = Field(description="是否被逐表排除增量同步(true=排除)")
    included: bool = Field(
        description="是否實際納入夜間增量(= 未被排除且系統至少一個啟用排程)"
    )
    last_synced_at: datetime | None = Field(
        description="上次同步到 hub 的時間(無則 null)"
    )
    last_run_status: str | None = Field(
        description="該表最新一筆執行結果(pending/running/success/failed/skipped;未跑為 null)"
    )
    row_count: int = Field(description="列數(bounded 探測值)")


class SchemaCoverageSummary(BaseModel):
    """單一 schema 的涵蓋概況(表數與被排除數)。"""

    schema_name: str = Field(description="schema 名稱")
    table_count: int = Field(description="該 schema 來源表總數")
    excluded_count: int = Field(description="該 schema 被排除的表數")


class CoverageSchemaListResponse(BaseModel):
    """依表檢視的 schema 概覽 + 目前套用排程。"""

    items: list[SchemaCoverageSummary] = Field(description="各 schema 涵蓋概況")
    has_enabled_schedule: bool = Field(
        description="系統是否至少有一個啟用中排程(否則全表未涵蓋)"
    )
    schedules: list[CoverageScheduleInfo] = Field(description="目前啟用中排程清單")


class CoverageListResponse(BaseModel):
    """指定 schema 下的來源表涵蓋清單(分頁)。"""

    items: list[TableCoverageItem] = Field(description="來源表涵蓋清單")
    total: int = Field(description="符合條件的總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")
    schedules: list[CoverageScheduleInfo] = Field(description="目前啟用中排程清單")
    has_enabled_schedule: bool = Field(description="系統是否至少有一個啟用中排程")


class ExclusionToggleRequest(BaseModel):
    """逐表排除切換請求。"""

    excluded: bool = Field(description="true=排除該表增量同步;false=納入")
