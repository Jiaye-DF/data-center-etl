from fastapi import APIRouter

from . import (
    audit_logs,
    auth,
    datasets,
    health,
    runs,
    schedules,
    sso,
    sync,
)

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(sso.router, prefix="/sso", tags=["sso"])
router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit-logs"])
router.include_router(sync.router, prefix="/sync", tags=["sync"])
