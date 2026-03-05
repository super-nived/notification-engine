"""
API v1 router aggregator.

Mounts all feature routers under a single ``/api/v1`` prefix.
No business logic — only router registration.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.settings import settings
from app.features.logs.router import router as logs_router
from app.features.notifier_config.router import router as notifier_config_router
from app.features.rules.router import router as rules_router
from app.features.stream.router import router as stream_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(rules_router)
api_router.include_router(notifier_config_router)
api_router.include_router(logs_router)
api_router.include_router(stream_router)


@api_router.get("/vapid-public-key", tags=["Web Push"])
def get_vapid_public_key() -> JSONResponse:
    """Return the VAPID public key for browser push subscription.

    The dashboard fetches this key to subscribe the browser to push
    notifications without hardcoding the key in the frontend.

    Returns:
        JSON with ``publicKey`` field.
    """
    return JSONResponse({"publicKey": settings.VAPID_PUBLIC_KEY})
