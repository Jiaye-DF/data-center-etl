from collections.abc import Mapping

from fastapi import APIRouter, FastAPI

CLIENT_ROUTE_PREFIX = "/api/client"


def mount_version(
    app_or_router: FastAPI | APIRouter,
    version: str,
    overrides: Mapping[str, APIRouter] | None = None,
) -> None:
    """把某版本的 router 掛到 `{version}` 之下(掛載目標已帶 `/api/client` prefix)。

    `overrides`:key = 掛載段(service 名;空字串 = 版本根,如 `/token`),value = 該版本 router。
    新版本 = 新增一個薄檔案只宣告差異,未列出的段沿用前版。
    """
    for segment, router in (overrides or {}).items():
        prefix = f"/{version}/{segment}" if segment else f"/{version}"
        app_or_router.include_router(router, prefix=prefix, tags=[f"api-client-{version}"])
