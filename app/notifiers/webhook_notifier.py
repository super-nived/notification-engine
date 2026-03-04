"""
Webhook notifier — POSTs alert events to an HTTP endpoint.

Compatible with Slack incoming webhooks, Microsoft Teams connectors,
or any custom HTTP receiver.
"""

import logging
from typing import Any

import requests

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class WebhookNotifier(BaseNotifier):
    """POSTs a JSON alert payload to a webhook URL on every event.

    Args:
        url:     HTTP(S) endpoint to POST the alert payload to.
        headers: Optional HTTP headers dict. Defaults to
                 ``{"Content-Type": "application/json"}``.
    """

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}

    def send(self, event: dict[str, Any]) -> None:
        """POST the event as a JSON payload to the configured URL.

        Args:
            event: Event dict containing ``rule_name``, ``message``,
                   ``data``, and ``triggered_at``.

        Raises:
            NotifierError: If the HTTP request fails or times out.

        Returns:
            None
        """
        payload = self._build_payload(event)
        self._post(payload)
        logger.info(
            "Webhook delivered to %s for rule '%s'",
            self.url,
            event.get("rule_name"),
        )

    def _build_payload(self, event: dict[str, Any]) -> dict[str, Any]:
        """Build the JSON payload dict from an event dict.

        Args:
            event: Alert event dict.

        Returns:
            Dict ready to be serialised as JSON and POSTed.
        """
        return {
            "rule": event.get("rule_name", "unknown"),
            "message": event.get("message", ""),
            "triggered_at": event.get("triggered_at", ""),
            "data": event.get("data", {}),
        }

    def _post(self, payload: dict[str, Any]) -> None:
        """Send the HTTP POST request.

        Args:
            payload: JSON-serialisable dict to POST.

        Raises:
            NotifierError: If the request times out or returns an error status.
        """
        try:
            resp = requests.post(
                self.url,
                json=payload,
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise NotifierError(
                "WebhookNotifier",
                f"POST to {self.url} timed out.",
            ) from exc
        except requests.HTTPError as exc:
            raise NotifierError(
                "WebhookNotifier",
                f"POST returned {exc.response.status_code}: {self.url}",
            ) from exc
