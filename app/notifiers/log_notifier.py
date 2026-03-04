"""
Log file notifier — writes alert events to a rotating log file.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class LogNotifier(BaseNotifier):
    """Appends a structured alert line to a log file on every event.

    Args:
        path: File path for the alert log. Parent directories are
              created automatically if they do not exist.
    """

    def __init__(self, path: str = "./logs/alerts.log") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def send(self, event: dict[str, Any]) -> None:
        """Append a formatted alert line to the log file.

        Args:
            event: Event dict containing ``rule_name``, ``message``,
                   ``data``, and ``triggered_at``.

        Raises:
            NotifierError: If the log file cannot be written.

        Returns:
            None
        """
        line = self._format_line(event)
        self._write(line)
        logger.info("Alert logged: [%s] %s", event.get("rule_name"), event.get("message"))

    def _format_line(self, event: dict[str, Any]) -> str:
        """Build the log line string from an event dict.

        Args:
            event: Alert event dict.

        Returns:
            Formatted log line ending with a newline character.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        rule = event.get("rule_name", "unknown")
        message = event.get("message", "")
        data = event.get("data", {})
        return f"[{timestamp}] [{rule}] {message} | {data}\n"

    def _write(self, line: str) -> None:
        """Write a line to the log file.

        Args:
            line: Formatted string to append.

        Raises:
            NotifierError: If the file write fails.
        """
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line)
        except OSError as exc:
            raise NotifierError(
                "LogNotifier", f"Failed to write to {self.path}: {exc}"
            ) from exc
