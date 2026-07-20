"""RDS 資料集瀏覽 API:原始資料管理(source)與 ETL 資料管理(target)共用。

dataset ∈ {source, target}:
- source → AWS_RDS_SOURCE_DB(erp_migration_test,Raw 原始資料)
- target → AWS_RDS_TARGET_DB(erp_etl_hub_test,ETL 轉換後資料)

瀏覽端點改讀 rds_table_meta 快照(不即時打 RDS)。全端點 admin-only(member 403)。
"""

from datetime import date, datetime, time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.rawdata import (
    SchemaListResponse,
    SchemaStatSummary,
    SnapshotRefreshResponse,
    TableListResponse,
)
from app.schemas.data_query import DataQueryResponse
from app.schemas.response import ApiResponse
from app.services.data_query_service import DataQueryService
from app.services.snapshot_service import SnapshotService, TableFilters

router = APIRouter()

Dataset = Literal["source", "target"]
RowFilter = Literal["all", "nonempty", "empty"]
SyncedFilter = Literal["all", "synced", "unsynced"]
TransformedFilter = Literal["all", "transformed", "untransformed"]


def _end_of_day(value: date | None) -> datetime | None:
    """截止日轉當日 23:59:59.999999 上界(含當日)。"""
    return datetime.combine(value, time.max) if value is not None else None


@router.get(
    "/{dataset}/schemas",
    response_model=ApiResponse[SchemaListResponse],
    summary="列出資料集內所有非系統 schema 與表數(讀快照)",
)
async def list_schemas(
    dataset: Dataset,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SchemaListResponse]:
    data = await SnapshotService(db).list_schemas(dataset)
    return success(data=data)


@router.get(
    "/{dataset}/tables",
    response_model=ApiResponse[TableListResponse],
    summary="分頁列出指定 schema 的表(讀快照,含業務名 / 同步時間;預設隱藏 0 筆表)",
)
async def list_tables(
    dataset: Dataset,
    schema: Annotated[str, Query(min_length=1, max_length=128)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    rows: Annotated[RowFilter, Query()] = "nonempty",
    synced: Annotated[SyncedFilter, Query()] = "all",
    transformed: Annotated[TransformedFilter, Query()] = "all",
    synced_before: Annotated[date | None, Query()] = None,
    transformed_before: Annotated[date | None, Query()] = None,
    keyword: Annotated[str, Query(max_length=128)] = "",
    keyword_exact: Annotated[
        bool, Query(description="true=keyword 為下拉選定表名,精準等值;false=子字串模糊")
    ] = False,
    row_min: Annotated[
        int | None, Query(ge=0, description="資料總筆數下限(含);row_count 探測上限 1001")
    ] = None,
    row_max: Annotated[
        int | None, Query(ge=0, description="資料總筆數上限(含);>1000 一律視為 1000+")
    ] = None,
) -> ApiResponse[TableListResponse]:
    filters = TableFilters(
        rows=rows,
        synced=synced,
        transformed=transformed,
        synced_before=_end_of_day(synced_before),
        transformed_before=_end_of_day(transformed_before),
        keyword=keyword,
        exact=keyword_exact,
        row_min=row_min,
        row_max=row_max,
    )
    data = await SnapshotService(db).list_tables(
        dataset, schema, page=page, page_size=page_size, filters=filters
    )
    return success(data=data)


@router.get(
    "/{dataset}/summary",
    response_model=ApiResponse[SchemaStatSummary],
    summary="指定 schema 的資料總筆數分布概覽(表數 / 有資料 / 空表 / 1000+;讀快照)",
)
async def schema_summary(
    dataset: Dataset,
    schema: Annotated[str, Query(min_length=1, max_length=128)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SchemaStatSummary]:
    data = await SnapshotService(db).list_summary(dataset, schema)
    return success(data=data)


@router.get(
    "/{dataset}/tables/{schema_name}/{table_name}/rows",
    response_model=ApiResponse[DataQueryResponse],
    summary="查指定表資料列(key 轉 confirmed 英文語意名;未 confirmed 欄不出現)",
)
async def query_table_rows(
    dataset: Dataset,
    schema_name: str,
    table_name: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ApiResponse[DataQueryResponse]:
    data = await DataQueryService(db).query_rows(
        dataset=dataset,
        schema_name=schema_name,
        table_name=table_name,
        limit=limit,
        offset=offset,
    )
    return success(data=data)


@router.post(
    "/{dataset}/snapshot/refresh",
    response_model=ApiResponse[SnapshotRefreshResponse],
    summary="重建資料集結構快照(內省 RDS + JOIN 字典業務名,落地 rds_table_meta)",
)
async def refresh_snapshot(
    dataset: Dataset,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SnapshotRefreshResponse]:
    data = await SnapshotService(db).refresh(dataset, actor_uid=user.uid)
    return success(data=data)
