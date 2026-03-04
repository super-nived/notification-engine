"""
Abstract base class for all notification channel implementations.

Every new notifier must extend ``BaseNotifier`` and implement
``send()``. The rule engine calls ``send()`` on each notifier
for every detected event.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseNotifier(ABC):
    """Contract that every notification channel must satisfy.

    A notifier is responsible for delivering one event through exactly
    one channel (file, email, webhook, desktop popup, etc.).

    It does not know about rules, schedules, or data sources.
    """

    @abstractmethod
    def send(self, event: dict[str, Any]) -> None:
        """Deliver a notification for the given event.

        The ``event`` dict will always contain:
            rule_name    (str): Name of the rule that detected the event.
            message      (str): Human-readable description.
            data         (dict): Raw record fields from the data source.
            triggered_at (str): ISO-8601 UTC timestamp of detection.

        Args:
            event: Structured event dict produced by a rule's ``detect()``.

        Raises:
            NotifierError: If delivery fails.

        Returns:
            None
        """
