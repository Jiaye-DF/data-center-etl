"""原始資料管理 / ETL 資料管理 瀏覽頁的回應 schema(RDS 結構內省)。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SchemaSummary(BaseModel):
    schema_name: str = Field(alias="schema", description="schema 名稱")
    table_count: int = Field(description="該 schema 下的 base table 數")

    model_config = {"populate_by_name": True}


class SchemaListResponse(BaseModel):
    items: list[SchemaSummary] = Field(description="非系統 schema 清單")


class TableSummary(BaseModel):
    name: str = Field(description="表名")
    column_count: int = Field(description="欄位數")
    row_count: int = Field(
        description="bounded row 數(SELECT 1 ... LIMIT 1001 探測);> 1000 代表超過上限"
    )


class TableListResponse(BaseModel):
    items: list[TableSummary] = Field(description="表清單(分頁)")
    total: int = Field(description="該 schema 表總數")
    page: int = Field(description="目前頁碼")
    page_size: int = Field(description="每頁筆數")


class ColumnInfo(BaseModel):
    name: str = Field(description="欄位名")
    data_type: str = Field(description="PostgreSQL 型別")
    nullable: bool = Field(description="是否可為 NULL")
    ordinal_position: int = Field(description="欄位順序")


class ColumnListResponse(BaseModel):
    columns: list[ColumnInfo] = Field(description="欄位清單")
