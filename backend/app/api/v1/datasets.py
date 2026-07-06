"""RDS 資料集瀏覽 API:原始資料管理(source)與 ETL 資料管理(target)共用。

dataset ∈ {source, target}:
- source → AWS_RDS_SOURCE_DB(erp_migration_test,Raw 原始資料)
- target → AWS_RDS_TARGET_DB(erp_etl_hub_test,ETL 轉換後資料)

瀏覽端點改讀 rds_table_meta 快照(不即時打 RDS);快照重建走 POST snapshot/refresh(admin)。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_login
from app.core.response import success
from app.models.user import User
from app.schemas.rawdata import (
    SchemaListResponse,
    SnapshotRefreshResponse,
    TableListResponse,
)
from app.schemas.response import ApiResponse
from app.services.snapshot_service import SnapshotService

router = APIRouter()

Dataset = Literal["source", "target"]


@router.get(
    "/{dataset}/schemas",
    response_model=ApiResponse[SchemaListResponse],
    summary="列出資料集內所有非系統 schema 與表數(讀快照)",
)
async def list_schemas(
    dataset: Dataset,
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_login)],
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
    _user: Annotated[User, Depends(require_login)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    hide_empty: Annotated[bool, Query()] = True,
) -> ApiResponse[TableListResponse]:
    data = await SnapshotService(db).list_tables(
        dataset, schema, page=page, page_size=page_size, hide_empty=hide_empty
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
