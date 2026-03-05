"""
WebSocket connection manager.

Single responsibility: track all active WebSocket connections and
broadcast messages to every connected client. No business logic,
no rule knowledge, no HTTP concerns.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Maintains the set of active WebSocket connections and broadcasts events.

    Thread-safe for use with FastAPI's async event loop. All send
    failures are caught and logged — a broken client never crashes
    the broadcast or affects other clients.
    """

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Store the main event loop for use by background threads.

        Called once at startup from the async lifespan context so
        APScheduler threads can submit broadcasts via
        ``run_coroutine_threadsafe``.

        Args:
            loop: The running asyncio event loop from the main thread.

        Returns:
            None
        """
        self._loop = loop

    @property
    def event_loop(self) -> asyncio.AbstractEventLoop | None:
        """Return the stored event loop, or None if not yet set.

        Returns:
            The main asyncio event loop, or None.
        """
        return self._loop

    # ── Connection lifecycle ──────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection.

        Args:
            websocket: Incoming WebSocket connection to accept.

        Returns:
            None
        """
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total connections: %d",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active set.

        Safe to call even if the connection is not in the list.

        Args:
            websocket: WebSocket connection to remove.

        Returns:
            None
        """
        try:
            self._connections.remove(websocket)
        except ValueError:
            pass
        logger.info(
            "WebSocket client disconnected. Total connections: %d",
            len(self._connections),
        )

    # ── Broadcasting ──────────────────────────────────────────────────────────

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """Send a JSON payload to all connected clients.

        Failed sends are caught per-client and logged without raising,
        so one broken connection never prevents others from receiving.

        Args:
            payload: Dict to serialise and broadcast as JSON text.

        Returns:
            None
        """
        if not self._connections:
            return

        message = json.dumps(payload)
        dead: list[WebSocket] = []

        for websocket in self._connections:
            try:
                await websocket.send_text(message)
            except Exception as exc:
                logger.warning(
                    "Failed to send to WebSocket client, removing: %s", exc
                )
                dead.append(websocket)

        # Clean up dead connections after the loop
        for ws in dead:
            self.disconnect(ws)

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        """Return the number of currently active connections.

        Returns:
            Integer count of active WebSocket connections.
        """
        return len(self._connections)


# Module-level singleton — shared across the notifier and the router
manager = ConnectionManager()
