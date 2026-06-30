from fastapi.responses import JSONResponse

from app.schemas.response import ApiResponse


def success[T](data: T | None = None, response_code: int = 200) -> ApiResponse[T]:
    return ApiResponse[T](success=True, data=data, detail=None, response_code=response_code)


def failure(detail: str, response_code: int = 400, status_code: int = 400) -> JSONResponse:
    body = ApiResponse[object](
        success=False, data=None, detail=detail, response_code=response_code
    )
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))
