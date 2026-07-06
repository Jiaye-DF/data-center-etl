"""RDS 資料集瀏覽 API:原始資料管理(source)與 ETL 資料管理(target)共用。

dataset ∈ {source, target}:
- source → AWS_RDS_SOURCE_DB(erp_migration_test,Raw 原始資料)
- target → AWS_RDS_TARGET_DB(erp_etl_hub_test,ETL 轉換後資料)
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_login
from app.core.response import success
from app.etl import introspect
from app.models.user import User
from app.schemas.rawdata import (
    ColumnListResponse,
    SchemaListResponse,
    TableListResponse,
)
from app.schemas.response import ApiResponse

router = APIRouter()

Dataset = Literal["source", "target"]


@router.get(
    "/{dataset}/schemas",
    response_model=ApiResponse[SchemaListResponse],
    summary="列出資料集內所有非系統 schema 與表數",
)
async def list_schemas(
    dataset: Dataset,
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[SchemaListResponse]:
    items = await introspect.list_schemas(dataset)
    return success(data=SchemaListResponse(items=items))


@router.get(
    "/{dataset}/tables",
    response_model=ApiResponse[TableListResponse],
    summary="分頁列出指定 schema 的表(含欄位數與 row 估算)",
)
async def list_tables(
    dataset: Dataset,
    schema: Annotated[str, Query(min_length=1, max_length=128)],
    _user: Annotated[User, Depends(require_login)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ApiResponse[TableListResponse]:
    data = await introspect.list_tables(
        dataset, schema, page=page, page_size=page_size
    )
    return success(data=TableListResponse(**data))


@router.get(
    "/{dataset}/tables/{schema}/{table}/columns",
    response_model=ApiResponse[ColumnListResponse],
    summary="列出指定表的欄位結構",
)
async def list_columns(
    dataset: Dataset,
    schema: str,
    table: str,
    _user: Annotated[User, Depends(require_login)],
) -> ApiResponse[ColumnListResponse]:
    columns = await introspect.list_columns(dataset, schema, table)
    return success(data=ColumnListResponse(columns=columns))
