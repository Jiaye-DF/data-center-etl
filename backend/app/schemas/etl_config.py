from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EtlMappingUpsertRequest(BaseModel):
    source_column: str = Field(
        min_length=1, max_length=200,
        description="來源欄名(多來源表須為 <來源表>.<欄名> 限定名,見 fixed.md §2)",
    )
    target_column: str = Field(min_length=1, max_length=200, description="目標欄名")
    transform_type: str | None = Field(
        default=None, max_length=50,
        description="轉換型別:str / int / float;null 表示不轉換",
    )
    # comment 缺值 / 空白屬商業邏輯違規(每欄位必帶 Comment),由 service 驗證回 400
    comment: str | None = Field(
        default=None, description="欄位 Comment(必填;缺值 / 空白由 service 回 400)"
    )
    sort_order: int = Field(default=0, description="欄位排序(小到大)")


class EtlTableCreateRequest(BaseModel):
    source_schema: str = Field(min_length=1, max_length=100, description="來源 schema")
    source_table: str = Field(
        min_length=1, max_length=200,
        description="來源表名(多來源以逗號合併,見 fixed.md §2)",
    )
    target_schema: str = Field(min_length=1, max_length=100, description="目標 schema")
    target_table: str = Field(min_length=1, max_length=200, description="目標表名")
    description: str | None = Field(default=None, description="表用途描述")
    is_enabled: bool = Field(default=True, description="是否啟用(停用表不處理)")
    mappings: list[EtlMappingUpsertRequest] = Field(
        default_factory=list, description="欄位對照清單"
    )


class EtlTableUpdateRequest(BaseModel):
    target_schema: str | None = Field(
        default=None, min_length=1, max_length=100, description="目標 schema(不改則省略)"
    )
    target_table: str | None = Field(
        default=None, min_length=1, max_length=200, description="目標表名(不改則省略)"
    )
    description: str | None = Field(default=None, description="表用途描述")


class EtlMappingsUpdateRequest(BaseModel):
    mappings: list[EtlMappingUpsertRequest] = Field(
        description="全量欄位對照(整批取代既有 mapping)"
    )


class EtlMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: UUID = Field(description="mapping 公開識別碼")
    source_column: str = Field(description="來源欄名")
    target_column: str = Field(description="目標欄名")
    transform_type: str | None = Field(description="轉換型別:str / int / float;null 不轉換")
    comment: str = Field(description="欄位 Comment")
    sort_order: int = Field(description="欄位排序")


class EtlTableSummaryResponse(BaseModel):
    uid: UUID = Field(description="納管表公開識別碼")
    source_schema: str = Field(description="來源 schema")
    source_table: str = Field(description="來源表名(多來源為逗號合併)")
    target_schema: str = Field(description="目標 schema")
    target_table: str = Field(description="目標表名")
    is_enabled: bool = Field(description="是否啟用(停用表不處理)")
    description: str | None = Field(description="表用途描述")
    mapping_count: int = Field(description="啟用中 mapping 欄位數")
    last_run_status: str | None = Field(description="最近一次執行狀態(未跑過為 null)")
    last_run_at: datetime | None = Field(description="最近一次執行時間(未跑過為 null)")


class EtlTableListResponse(BaseModel):
    items: list[EtlTableSummaryResponse] = Field(description="納管表清單")
    total: int = Field(description="總筆數")
    page: int = Field(description="目前頁碼(1 起算)")
    page_size: int = Field(description="每頁筆數")


class EtlTableDetailResponse(EtlTableSummaryResponse):
    mappings: list[EtlMappingResponse] = Field(description="欄位對照明細(依 sort_order)")


class EtlTableDeleteResponse(BaseModel):
    message: str = Field(description="操作結果訊息")
