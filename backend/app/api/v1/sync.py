"""同步觸發 API:逐表 / 全量鏡像來源 → hub(admin;member 403)。

- `POST /sync/table`(admin):body {schema, table} → enqueue 單表 mirror_sync。
- `POST /sync/all`(admin):enqueue 全量 mirror_sync(worker 端 DS 優先)。
- 皆回 202 Accepted(enqueue 語意);佇列模式下 run 由 worker 建立,run_uid 可能為 null。
"""

from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.response import ApiResponse
from app.schemas.sync import (
    SyncFilteredRequest,
    SyncTableRequest,
    SyncTriggerResponse,
)
from app.services.snapshot_service import TableFilters
from app.services.sync_service import SyncService

router = APIRouter()


def _end_of_day(value: date | None) -> datetime | None:
    """截止日轉當日 23:59:59.999999 上界(含當日)。"""
    return datetime.combine(value, time.max) if value is not None else None


@router.post(
    "/table",
    response_model=ApiResponse[SyncTriggerResponse],
    status_code=202,
    summary="同步單表:enqueue 鏡像來源 schema.table → hub(admin)",
)
async def sync_table(
    payload: SyncTableRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SyncTriggerResponse]:
    data = await SyncService(db).sync_table(
        payload.schema_name, payload.table, actor_uid=user.uid
    )
    return success(data=data, response_code=202)


@router.post(
    "/all",
    response_model=ApiResponse[SyncTriggerResponse],
    status_code=202,
    summary="全量同步:enqueue 鏡像所有來源表 → hub(DS 優先;admin)",
)
async def sync_all(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SyncTriggerResponse]:
    data = await SyncService(db).sync_all(actor_uid=user.uid)
    return success(data=data, response_code=202)


@router.post(
    "/filtered",
    response_model=ApiResponse[SyncTriggerResponse],
    status_code=202,
    summary="篩選同步:只 enqueue 符合進階篩選條件的來源表 → hub(admin)",
)
async def sync_filtered(
    payload: SyncFilteredRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[SyncTriggerResponse]:
    filters = TableFilters(
        rows=payload.rows,
        synced=payload.synced,
        transformed=payload.transformed,
        synced_before=_end_of_day(payload.synced_before),
        transformed_before=_end_of_day(payload.transformed_before),
        keyword=payload.keyword,
        exact=payload.keyword_exact,
    )
    data = await SyncService(db).sync_filtered(
        payload.schema_name, filters, actor_uid=user.uid
    )
    return success(data=data, response_code=202)
