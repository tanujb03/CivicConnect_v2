from fastapi import APIRouter
from backend.api.v1 import health, cases, copilot, auth, work_orders, evidence, map, me, incidents, analytics, sync, reference, admin, flags, devices

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(me.router, prefix="/me", tags=["me"])
api_router.include_router(devices.router, prefix="/me", tags=["me"])           # WP5: /me/devices
api_router.include_router(cases.router, prefix="/cases", tags=["cases"])
api_router.include_router(flags.router, tags=["flags"])                         # WP4: /cases/{id}/flags and /flags/{id}/resolve (full paths in the module)
api_router.include_router(work_orders.router, prefix="/work-orders", tags=["work-orders"])
api_router.include_router(evidence.router, prefix="/evidence", tags=["evidence"])
api_router.include_router(map.router, prefix="/map", tags=["map"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(copilot.router, prefix="/copilot", tags=["copilot"])
api_router.include_router(reference.router, prefix="/reference", tags=["reference"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
