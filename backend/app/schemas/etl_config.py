from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EtlMappingUpsertRequest(BaseModel):
    source_column: str = Field(min_length=1, max_length=200)
    target_column: str = Field(min_length=1, max_length=200)
    transform_type: str | None = Field(default=None, max_length=50)
    # comment 缺值 / 空白屬商業邏輯違規(每欄位必帶 Comment),由 service 驗證回 400
    comment: str | None = None
    sort_order: int = 0


class EtlTableCreateRequest(BaseModel):
    source_schema: str = Field(min_length=1, max_length=100)
    source_table: str = Field(min_length=1, max_length=200)
    target_schema: str = Field(min_length=1, max_length=100)
    target_table: str = Field(min_length=1, max_length=200)
    description: str | None = None
    is_enabled: bool = True
    mappings: list[EtlMappingUpsertRequest] = Field(default_factory=list)


class EtlTableUpdateRequest(BaseModel):
    target_schema: str | None = Field(default=None, min_length=1, max_length=100)
    target_table: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class EtlMappingsUpdateRequest(BaseModel):
    mappings: list[EtlMappingUpsertRequest]


class EtlMappingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uid: UUID
    source_column: str
    target_column: str
    transform_type: str | None
    comment: str
    sort_order: int


class EtlTableSummaryResponse(BaseModel):
    uid: UUID
    source_schema: str
    source_table: str
    target_schema: str
    target_table: str
    is_enabled: bool
    description: str | None
    mapping_count: int
    last_run_status: str | None
    last_run_at: datetime | None


class EtlTableListResponse(BaseModel):
    items: list[EtlTableSummaryResponse]
    total: int
    page: int
    page_size: int


class EtlTableDetailResponse(EtlTableSummaryResponse):
    mappings: list[EtlMappingResponse]


class EtlTableDeleteResponse(BaseModel):
    message: str
