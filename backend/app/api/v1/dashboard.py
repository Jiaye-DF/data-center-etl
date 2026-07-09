"""總覽儀表板 API:單一聚合端點,回同步健康 / 待處理失敗表 / 排程概況 / 資料規模。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.response import success
from app.models.user import User
from app.schemas.dashboard import DashboardOverview
from app.schemas.response import ApiResponse
from app.services.dashboard_service import DashboardService

router = APIRouter()


@router.get(
    "/overview",
    response_model=ApiResponse[DashboardOverview],
    summary="總覽儀表板聚合(同步健康 / 待處理失敗表 / 排程概況 / 資料規模;讀自有 DB)",
)
async def overview(
    db: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_admin)],
) -> ApiResponse[DashboardOverview]:
    return success(data=await DashboardService(db).overview())
