from fastapi import APIRouter

from . import v1_0


def build_client_router() -> APIRouter:
    """組出 `/api/client` 命名空間 router(prefix 由 main.py 掛上;每版本一個薄掛載檔)。"""
    router = APIRouter()
    v1_0.mount(router)
    return router
