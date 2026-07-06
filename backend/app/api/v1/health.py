from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core import db
from app.core.response import failure, success
from app.schemas.response import ApiResponse

router = APIRouter()


class HealthResponse(BaseModel):
    db: str = Field(description="資料庫連線狀態:ok")


@router.get(
    "/health",
    response_model=ApiResponse[HealthResponse],
    summary="健康檢查(DB 不可達回 503,供 compose healthcheck 正確判定)",
)
async def health() -> Response:
    # 不走 get_db(request-scope 尾端 commit 在 DB 斷線時會再炸成 500);
    # 直接以 engine 短連線探測,失敗回 503 讓 healthcheck / restart 策略介入(scan AD-005)
    try:
        async with db.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        return failure(detail="資料庫不可達", response_code=503, status_code=503)
    body = success(data=HealthResponse(db="ok"))
    return JSONResponse(status_code=200, content=body.model_dump(mode="json"))
