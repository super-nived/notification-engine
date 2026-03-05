"""
WebSocket notifier — broadcasts alert events to all connected clients.

Single responsibility: receive an alert event from the rule engine
and broadcast it to every active WebSocket connection via the
ConnectionManager. No HTTP logic, no rule logic, no scheduling.
"""

import asyncio
import logging
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class WebSocketNotifier(BaseNotifier):
    """Broadcasts alert events in real time to all connected WebSocket clients.

    The notifier is synchronous (called from APScheduler threads) but
    the ConnectionManager is async. It resolves this by running the
    broadcast coroutine on the current event loop safely.

    No constructor arguments are required — it uses the module-level
    ConnectionManager singleton from ``app.features.stream.manager``.
    """

    def send(self, event: dict[str, Any]) -> None:
        """Broadcast an alert event to all connected WebSocket clients.

        Args:
            event: Structured event dict from a rule's ``detect()``.
                   Always contains ``rule_name``, ``message``,
                   ``data``, and ``triggered_at``.

        Raises:
            NotifierError: If the broadcast cannot be scheduled on
                           the event loop.

        Returns:
            None
        """
        payload = self._build_payload(event)
        self._broadcast(payload)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _build_payload(self, event: dict[str, Any]) -> dict[str, Any]:
        """Construct the JSON-serialisable payload to broadcast.

        Args:
            event: Raw event dict from the rule engine.

        Returns:
            Clean dict with typed fields for frontend consumption.
        """
        return {
            "type":         "alert",
            "rule_name":    event.get("rule_name", ""),
            "message":      event.get("message", ""),
            "triggered_at": event.get("triggered_at", ""),
            "data":         event.get("data", {}),
        }

    def _broadcast(self, payload: dict[str, Any]) -> None:
        """Schedule the async broadcast on the running event loop.

        APScheduler runs rule jobs in a thread pool, not in the async
        event loop. This method safely submits the coroutine to the
        existing loop so the WebSocket send runs in the correct context.

        Args:
            payload: Dict to broadcast to all connected clients.

        Raises:
            NotifierError: If no event loop is running or the broadcast
                           cannot be submitted.

        Returns:
            None
        """
        # Late import to avoid circular import at module load time
        from app.features.stream.manager import manager

        try:
            loop = manager.event_loop
            if loop is None or not loop.is_running():
                logger.warning(
                    "WebSocketNotifier: event loop not available, broadcast skipped."
                )
                return
            asyncio.run_coroutine_threadsafe(
                manager.broadcast(payload), loop
            )
            logger.info(
                "WebSocket broadcast queued for rule '%s' to %d client(s).",
                payload.get("rule_name"),
                manager.connection_count,
            )
        except Exception as exc:
            raise NotifierError(
                "WebSocketNotifier",
                f"Failed to schedule broadcast: {exc}",
            ) from exc
