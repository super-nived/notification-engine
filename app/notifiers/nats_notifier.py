"""
NATS notifier — publishes alert events to a NATS subject.

NATS is a lightweight, high-performance message broker used in
industrial and IoT systems. Each alert event is published as a
JSON message to the configured subject so any NATS subscriber
(microservice, mobile app, SCADA system, etc.) can consume it.

Requires:
    pip install nats-py

Config keys (stored in notifier config_json):
    url      — NATS server URL, e.g. nats://localhost:4222
    subject  — NATS subject to publish to, e.g. alerts.production
"""

import asyncio
import json
import logging
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class NatsNotifier(BaseNotifier):
    """Publishes alert events as JSON messages to a NATS subject.

    Uses the ``nats-py`` async client, run synchronously via
    ``asyncio.run()`` so it fits the existing synchronous notifier
    interface without requiring changes to the scheduler or runner.

    Args:
        url:     NATS server URL (e.g. ``nats://localhost:4222``).
        subject: NATS subject to publish to (e.g. ``alerts.downtime``).
    """

    def __init__(
        self,
        url: str = "nats://localhost:4222",
        subject: str = "alerts.notification_engine",
    ) -> None:
        self.url = url
        self.subject = subject

    def send(self, event: dict[str, Any]) -> None:
        """Publish the event as a JSON message to the NATS subject.

        Args:
            event: Event dict with ``rule_name``, ``message``,
                   ``data``, and ``triggered_at``.

        Raises:
            NotifierError: If the NATS publish fails.

        Returns:
            None
        """
        try:
            asyncio.run(self._publish(event))
        except Exception as exc:
            raise NotifierError(
                "NatsNotifier",
                f"Failed to publish to NATS subject '{self.subject}': {exc}",
            ) from exc

    async def _publish(self, event: dict[str, Any]) -> None:
        """Async publish — connects, publishes, then closes cleanly.

        Args:
            event: Alert event dict to serialise and publish.
        """
        try:
            import nats
        except ImportError as exc:
            raise NotifierError(
                "NatsNotifier",
                "nats-py is not installed. Run: pip install nats-py",
            ) from exc

        payload = json.dumps({
            "rule":         event.get("rule_name", "unknown"),
            "message":      event.get("message", ""),
            "triggered_at": event.get("triggered_at", ""),
            "data":         event.get("data", {}),
        }).encode()

        nc = await nats.connect(self.url)
        try:
            await nc.publish(self.subject, payload)
            await nc.flush()
            logger.info(
                "NATS: published to '%s' for rule '%s'",
                self.subject,
                event.get("rule_name"),
            )
        finally:
            await nc.drain()
