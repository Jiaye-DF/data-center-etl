"""原始資料管理 / ETL 資料管理 瀏覽頁的回應 schema(讀 rds_table_meta 快照)。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SchemaSummary(BaseModel):
    schema_name: str = Field(alias="schema", description="schema 名稱")
    table_count: int = Field(description="該 schema 下的 base table 數")

    model_config = {"populate_by_name": True}


class SchemaListResponse(BaseModel):
    items: list[SchemaSummary] = Field(description="非系統 schema 清單")


class ModuleListResponse(BaseModel):
    """指定 schema 下 distinct ERP 模組代碼清單(AD-115:整 schema 聚合,非單頁)。"""

    modules: list[str] = Field(description="distinct ERP 模組代碼(排序;不含未分類)")
    has_unclassified: bool = Field(description="該 schema 是否存在未分類(module_code IS NULL)的表")


class TableSummary(BaseModel):
    name: str = Field(description="表名")
    business_name: str | None = Field(
        default=None, description="業務資料名稱(中文,快照時 JOIN GAT_FILE 落地;缺對應為 null)"
    )
    module_code: str | None = Field(
        default=None,
        description="ERP 模組代碼(GAT_FILE.GAT06,快照時 JOIN 落地;字典缺對應為 null)",
    )
    column_count: int = Field(description="欄位數")
    row_count: int = Field(
        description="bounded row 數(SELECT 1 ... LIMIT 1001 探測);> 1000 代表超過上限"
    )
    snapshot_at: datetime | None = Field(
        default=None, description="此筆 metadata 擷取時間(UTC+8;尚未快照為 null)"
    )
    last_synced_at: datetime | None = Field(
        default=None, description="最近從 RDS 同步到 hub 的時間(UTC+8;未同步為 null)"
    )
    last_transformed_at: datetime | None = Field(
        default=None, description="最近套字典 COMMENT 的時間(UTC+8;未轉換為 null)"
    )


class TableListResponse(BaseModel):
    items: list[TableSummary] = Field(description="表清單(分頁)")
    total: int = Field(description="該 schema 表總數")
    page: int = Field(description="目前頁碼")
    page_size: int = Field(description="每頁筆數")


class SchemaStatSummary(BaseModel):
    """指定 schema 的資料總筆數分布概覽(不做筆數加總,避免 bounded 探測失真)。"""

    schema_name: str = Field(alias="schema", description="schema 名稱")
    table_count: int = Field(description="總表數")
    nonempty_count: int = Field(description="有資料表數(row_count>0)")
    empty_count: int = Field(description="空表數(row_count=0)")
    capped_count: int = Field(description="1000+ 表數(row_count>1000,探測封頂)")

    model_config = {"populate_by_name": True}


class SnapshotRefreshResponse(BaseModel):
    dataset: str = Field(description="重新快照的資料集(source / target)")
    table_count: int = Field(description="本次快照落地的表數")
    snapshot_at: datetime = Field(description="快照擷取時間(UTC+8)")
