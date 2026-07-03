from fastapi import APIRouter

from . import auth, health, sso

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(sso.router, prefix="/sso", tags=["sso"])
