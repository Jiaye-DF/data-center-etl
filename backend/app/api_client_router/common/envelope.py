from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ClientEnvelope(BaseModel):
    """對外統一回應封套(成功 / 失敗同構;`data` 恆為陣列,失敗時為空陣列)。"""

    success: bool
    response_code: int
    detail: str
    data: list[dict[str, object]]


def client_success(
    data: list[dict[str, object]] | None = None,
    *,
    detail: str = "",
    response_code: int = 200,
) -> JSONResponse:
    envelope = ClientEnvelope(
        success=True, response_code=response_code, detail=detail, data=data or []
    )
    return JSONResponse(status_code=response_code, content=envelope.model_dump(mode="json"))


def client_error(
    detail: str,
    *,
    response_code: int,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    # detail 僅基本錯誤資訊,禁洩內部設計;HTTP status 與 response_code 一致
    envelope = ClientEnvelope(
        success=False, response_code=response_code, detail=detail, data=[]
    )
    return JSONResponse(
        status_code=response_code,
        content=envelope.model_dump(mode="json"),
        headers=headers,
    )
