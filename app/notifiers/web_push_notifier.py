"""
Web Push notifier — sends browser push notifications via VAPID.

Single responsibility: deliver one alert event as a browser push
notification to a subscribed endpoint. No rule logic, no scheduling.

The ``config_json`` for this notifier must contain a browser
subscription object captured from the Push API:
    {
        "endpoint": "https://fcm.googleapis.com/fcm/send/...",
        "keys": {
            "p256dh": "<base64>",
            "auth":   "<base64>"
        }
    }
"""

import json
import logging
from typing import Any

from py_vapid import Vapid02
from pywebpush import webpush, WebPushException

from app.core.exceptions import NotifierError
from app.core.settings import settings
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class WebPushNotifier(BaseNotifier):
    """Sends a browser push notification to a subscribed endpoint.

    Uses the VAPID protocol so the browser can verify the notification
    came from your server.

    Args:
        subscription_info: Browser Push API subscription dict containing
                           ``endpoint`` and ``keys`` (``p256dh``, ``auth``).
        vapid_public_key:  VAPID public key in base64url format.
        vapid_private_key: VAPID private key in PEM or base64url format.
        vapid_claims_sub:  ``mailto:`` or URL identifying your server.
    """

    def __init__(
        self,
        subscription_info: dict,
        vapid_public_key: str = "",
        vapid_private_key: str = "",
        vapid_claims_sub: str = "",
    ) -> None:
        self.subscription_info = subscription_info
        self.vapid_public_key = vapid_public_key or settings.VAPID_PUBLIC_KEY
        self.vapid_private_key = vapid_private_key or settings.VAPID_PRIVATE_KEY
        self.vapid_claims_sub = vapid_claims_sub or settings.VAPID_CLAIMS_SUB

    def send(self, event: dict[str, Any]) -> None:
        """Send a browser push notification for the given event.

        Args:
            event: Structured event dict from a rule's ``detect()``.
                   Must contain ``rule_name`` and ``message``.

        Raises:
            NotifierError: If the push delivery fails.

        Returns:
            None
        """
        self._validate_config()
        payload = self._build_payload(event)
        self._push(payload)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _validate_config(self) -> None:
        """Raise NotifierError if required config values are missing.

        Raises:
            NotifierError: If subscription, public key, or private key
                           are not set.
        """
        if not self.subscription_info.get("endpoint"):
            raise NotifierError(
                "WebPushNotifier",
                "subscription_info missing 'endpoint'.",
            )
        if not self.vapid_public_key:
            raise NotifierError(
                "WebPushNotifier",
                "VAPID_PUBLIC_KEY is not set.",
            )
        if not self.vapid_private_key:
            raise NotifierError(
                "WebPushNotifier",
                "VAPID_PRIVATE_KEY is not set.",
            )

    def _build_payload(self, event: dict[str, Any]) -> str:
        """Serialise the event into the push notification payload.

        Args:
            event: Event dict from the rule engine.

        Returns:
            JSON string sent as the push body.
        """
        rule_name = event.get("rule_name", "Rule Engine")
        message = event.get("message", "An alert was triggered.")
        triggered_at = event.get("triggered_at", "")
        data = event.get("data", {})

        # Build a clean summary line from event data fields if available
        summary_parts = []
        for key in ("machine", "machine_id", "collection", "status", "state"):
            val = data.get(key)
            if val:
                summary_parts.append(f"{key.replace('_', ' ').title()}: {val}")
        summary = " | ".join(summary_parts) if summary_parts else ""

        return json.dumps({
            "rule_name": rule_name,
            "title": rule_name,
            "body": message,
            "summary": summary,
            "triggered_at": triggered_at,
            "url": "/dashboard",
        })

    def _push(self, payload: str) -> None:
        """Call pywebpush to deliver the notification.

        Args:
            payload: JSON string to send as the push body.

        Raises:
            NotifierError: On any WebPush delivery failure.
        """
        try:
            vapid = Vapid02.from_string(self.vapid_private_key)
            webpush(
                subscription_info=self.subscription_info,
                data=payload,
                vapid_private_key=vapid,
                vapid_claims={
                    "sub": self.vapid_claims_sub,
                },
            )
            logger.info(
                "WebPush sent to endpoint: %s",
                self.subscription_info.get("endpoint", "")[:60],
            )
        except WebPushException as exc:
            raise NotifierError(
                "WebPushNotifier",
                f"Push delivery failed: {exc}",
            ) from exc
        except Exception as exc:
            raise NotifierError(
                "WebPushNotifier",
                f"Unexpected error during push: {exc}",
            ) from exc
