"""
Desktop notifier — displays a popup via ``notify-send`` (Linux).

Requires ``libnotify-bin`` to be installed on the system:
    sudo apt install libnotify-bin
"""

import logging
import subprocess
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class DesktopNotifier(BaseNotifier):
    """Shows an OS desktop popup notification using ``notify-send``.

    Args:
        timeout_ms: How long the popup stays visible in milliseconds.
                    Default is 5000 (5 seconds).
    """

    def __init__(self, timeout_ms: int = 5000) -> None:
        self.timeout_ms = timeout_ms

    def send(self, event: dict[str, Any]) -> None:
        """Display a desktop popup for the given event.

        Args:
            event: Event dict containing ``rule_name`` and ``message``.

        Raises:
            NotifierError: If ``notify-send`` is not found or returns
                           a non-zero exit code.

        Returns:
            None
        """
        title = self._build_title(event)
        body = event.get("message", "")
        self._notify(title, body)
        logger.info("Desktop notification shown: %s", title)

    def _build_title(self, event: dict[str, Any]) -> str:
        """Build the popup title string from an event dict.

        Args:
            event: Alert event dict.

        Returns:
            Title string formatted as ``[rule_name] Alert``.
        """
        rule = event.get("rule_name", "unknown")
        return f"[{rule}] Alert"

    def _notify(self, title: str, body: str) -> None:
        """Invoke ``notify-send`` as a subprocess.

        Args:
            title: Popup title string.
            body:  Popup body text.

        Raises:
            NotifierError: If ``notify-send`` is missing or fails.
        """
        try:
            result = subprocess.run(
                ["notify-send", "-t", str(self.timeout_ms), title, body],
                capture_output=True,
                timeout=5,
            )
        except FileNotFoundError as exc:
            raise NotifierError(
                "DesktopNotifier",
                "notify-send not found. Install libnotify-bin.",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise NotifierError(
                "DesktopNotifier", "notify-send timed out."
            ) from exc

        if result.returncode != 0:
            raise NotifierError(
                "DesktopNotifier",
                f"notify-send exited {result.returncode}: "
                f"{result.stderr.decode().strip()}",
            )
