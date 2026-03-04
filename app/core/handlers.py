"""
Global exception handlers for the FastAPI application.

Registers handlers that convert domain exceptions into structured
JSON responses with appropriate HTTP status codes. Register all
handlers in ``register_handlers(app)``.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    DataSourceError,
    NotifierConfigNotFoundError,
    NotifierError,
    RuleConfigError,
    RuleNotFoundError,
    SchedulerError,
)
from app.db.pb_client import PocketBaseError

logger = logging.getLogger(__name__)


def _error_response(status: int, error: str, detail: str) -> JSONResponse:
    """Build a consistent JSON error response body.

    Args:
        status: HTTP status code.
        error:  Short error type label.
        detail: Human-readable description of the problem.

    Returns:
        JSONResponse with ``status``, ``error``, and ``detail`` keys.
    """
    return JSONResponse(
        status_code=status,
        content={"status": status, "error": error, "detail": detail},
    )


def register_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI application.

    Args:
        app: The FastAPI application instance to attach handlers to.

    Returns:
        None
    """

    @app.exception_handler(RuleNotFoundError)
    async def rule_not_found(
        request: Request, exc: RuleNotFoundError
    ) -> JSONResponse:
        logger.warning("RuleNotFoundError: %s", exc)
        return _error_response(404, "RuleNotFoundError", str(exc))

    @app.exception_handler(RuleConfigError)
    async def rule_config_error(
        request: Request, exc: RuleConfigError
    ) -> JSONResponse:
        logger.error("RuleConfigError: %s", exc)
        return _error_response(422, "RuleConfigError", str(exc))

    @app.exception_handler(DataSourceError)
    async def datasource_error(
        request: Request, exc: DataSourceError
    ) -> JSONResponse:
        logger.error("DataSourceError: %s", exc)
        return _error_response(502, "DataSourceError", str(exc))

    @app.exception_handler(NotifierError)
    async def notifier_error(
        request: Request, exc: NotifierError
    ) -> JSONResponse:
        logger.error("NotifierError: %s", exc)
        return _error_response(502, "NotifierError", str(exc))

    @app.exception_handler(NotifierConfigNotFoundError)
    async def notifier_config_not_found(
        request: Request, exc: NotifierConfigNotFoundError
    ) -> JSONResponse:
        logger.warning("NotifierConfigNotFoundError: %s", exc)
        return _error_response(404, "NotifierConfigNotFoundError", str(exc))

    @app.exception_handler(SchedulerError)
    async def scheduler_error(
        request: Request, exc: SchedulerError
    ) -> JSONResponse:
        logger.error("SchedulerError: %s", exc)
        return _error_response(500, "SchedulerError", str(exc))

    @app.exception_handler(PocketBaseError)
    async def pocketbase_error(
        request: Request, exc: PocketBaseError
    ) -> JSONResponse:
        logger.error("PocketBaseError: %s", exc)
        return _error_response(502, "PocketBaseError", str(exc))
