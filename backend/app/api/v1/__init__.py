from fastapi import APIRouter

from . import (
    audit_logs,
    auth,
    dashboard,
    datasets,
    health,
    roles,
    runs,
    schedules,
    sso,
    sync,
    users,
)

router = APIRouter()
router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(sso.router, prefix="/sso", tags=["sso"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
router.include_router(schedules.router, prefix="/schedules", tags=["schedules"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit-logs"])
router.include_router(sync.router, prefix="/sync", tags=["sync"])
router.include_router(roles.router, prefix="/roles", tags=["roles"])
router.include_router(users.router, prefix="/users", tags=["users"])
