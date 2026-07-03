from fastapi import APIRouter

from . import auth, etl_tables, health, sso

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(sso.router, prefix="/sso", tags=["sso"])
router.include_router(etl_tables.router, prefix="/etl-tables", tags=["etl-tables"])
