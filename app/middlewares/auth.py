"""
Authentication middleware placeholder.

Extend this module to add token extraction, validation, and user
context injection for protected API routes.
"""

import logging
from typing import Any, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware stub for request authentication.

    Currently passes all requests through. Extend ``dispatch()`` to
    validate Bearer tokens or API keys on protected routes.

    Args:
        app: The ASGI application instance.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process the request, optionally validating auth headers.

        Args:
            request:   Incoming HTTP request.
            call_next: Next ASGI handler in the middleware chain.

        Returns:
            HTTP response from the next handler.
        """
        # Future: extract and validate Authorization header here
        response = await call_next(request)
        return response
