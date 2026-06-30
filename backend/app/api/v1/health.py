from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.response import success
from app.schemas.response import ApiResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=ApiResponse[dict[str, str]],
    summary="健康檢查",
)
async def health(db: Annotated[AsyncSession, Depends(get_db)]) -> ApiResponse[dict[str, str]]:
    db_ok = "ok"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_ok = "fail"
    return success(data={"db": db_ok})
