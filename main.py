"""
Application entry point.

Creates the FastAPI app, attaches middleware, registers exception handlers,
and mounts the v1 API router. All startup/shutdown logic lives in
``app.core.events`` via the lifespan context manager.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.v1 import api_router
from app.core.events import lifespan
from app.core.handlers import register_handlers
from app.middlewares.auth import AuthMiddleware

app = FastAPI(
    title="Notification Rule Engine",
    version="1.0.0",
    description=(
        "A pluggable rule engine that monitors external data sources "
        "and dispatches notifications when conditions are met."
    ),
    lifespan=lifespan,
)

# Middleware
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_handlers(app)

# Routes
app.include_router(api_router)


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the management dashboard HTML file.

    Returns:
        The dashboard.html file.
    """
    return FileResponse("dashboard.html", media_type="text/html")


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    """Return service liveness status.

    Returns:
        Dict with ``status`` key set to ``ok``.
    """
    return {"status": "ok"}
