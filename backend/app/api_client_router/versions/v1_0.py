from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from app.api_client_router.common.envelope import ClientEnvelope, client_error
from app.api_client_router.versions.registry import mount_version

VERSION = "v1.0"

router = APIRouter()


@router.post(
    "/token",
    response_model=ClientEnvelope,
    summary="Client Credentials 換發短效 JWT(骨架佔位,業務流由 task-004 填實)",
)
async def issue_token() -> JSONResponse:
    return client_error("not_implemented", response_code=501)


@router.post(
    "/refresh_token",
    response_model=ClientEnvelope,
    summary="過期 token 語意刷新(骨架佔位,業務流由 task-004 填實)",
)
async def refresh_token() -> JSONResponse:
    return client_error("not_implemented", response_code=501)


def mount(app_or_router: FastAPI | APIRouter) -> None:
    mount_version(app_or_router, VERSION, {"": router})
