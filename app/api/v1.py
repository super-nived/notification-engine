"""
API v1 router aggregator.

Mounts all feature routers under a single ``/api/v1`` prefix.
No business logic — only router registration.
"""

from fastapi import APIRouter

from app.features.logs.router import router as logs_router
from app.features.notifier_config.router import router as notifier_config_router
from app.features.rules.router import router as rules_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(rules_router)
api_router.include_router(notifier_config_router)
api_router.include_router(logs_router)
