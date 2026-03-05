"""
FastAPI lifespan context manager.

Handles startup and shutdown events in a single place.
Starts the APScheduler on startup and stops it cleanly on shutdown.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.core.logging import configure_logging
from app.db.pb_client import authenticate
from app.engine.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle.

    On startup:
    - Configures logging.
    - Authenticates with PocketBase admin API.
    - Starts the background scheduler and loads all enabled rules.

    On shutdown:
    - Stops the background scheduler gracefully.

    Args:
        app: The FastAPI application instance.

    Yields:
        None — control is yielded to the running application.
    """
    configure_logging()
    logger.info("Starting Notification Rule Engine")
    authenticate()

    # Store the main async event loop so background threads (APScheduler)
    # can submit coroutines to it via run_coroutine_threadsafe.
    from app.features.stream.manager import manager
    manager.set_event_loop(asyncio.get_event_loop())

    start_scheduler()
    yield
    logger.info("Shutting down Notification Rule Engine")
    stop_scheduler()
