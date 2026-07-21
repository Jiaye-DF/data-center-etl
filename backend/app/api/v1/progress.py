"""全局進度聚合 API(AD-121):sync / snapshot(source・target)/ apply 一次回,
前端 layout 只輪詢本端點(收斂閒置輪詢面,避免 4 條輪詢放大 SSO 回源驗證)。

admin-only(member 403);snapshot / apply 進度只讀 Redis,sync 重用 /runs/active 查詢。
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.progress import GlobalProgressResponse
from app.schemas.response import ApiResponse
from app.services.schedule_service import RunService
from app.services.snapshot_service import SnapshotService
from app.worker.tasks import get_apply_progress

router = APIRouter()


@router.get(
    "",
    response_model=ApiResponse[GlobalProgressResponse],
    summary="聚合查詢全局進度(sync / snapshot source+target / apply;單一輪詢端點)",
)
async def get_global_progress(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[GlobalProgressResponse]:
    data = GlobalProgressResponse(
        sync=await RunService(db).get_active_run(),
        snapshot_source=await SnapshotService.get_refresh_progress("source"),
        snapshot_target=await SnapshotService.get_refresh_progress("target"),
        apply=await get_apply_progress(),
    )
    return success(data=data)
