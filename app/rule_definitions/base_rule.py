"""
Abstract base class for all rule definitions.

Every rule must extend ``BaseRule`` and implement ``detect()``.
The engine calls ``run()`` — which calls ``detect()``, enriches each
event with metadata, fires all notifiers, and returns a result dict.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import NotifierError
from app.notifiers.base import BaseNotifier

logger = logging.getLogger(__name__)


class BaseRule(ABC):
    """Contract every rule definition must satisfy.

    Subclasses set ``name`` and ``description`` as class attributes
    and implement ``detect()``.

    Class Attributes:
        name:        Unique snake_case identifier for the rule.
        description: One sentence describing what the rule detects.

    Args:
        notifiers: List of notifier instances to fire when events are detected.
    """

    name: str = ""
    description: str = ""

    def __init__(self, notifiers: list[BaseNotifier]) -> None:
        self.notifiers = notifiers

    @abstractmethod
    def detect(self) -> list[dict[str, Any]]:
        """Query the data source and return new alert events.

        Returns an empty list if nothing new was detected.
        Returns one dict per detected event containing at minimum:
            message (str):  Human-readable description.
            data    (dict): Raw fields from the source record.

        Returns:
            List of event dicts. Empty if no new events.

        Raises:
            DataSourceError: If the data source fetch fails.
            OSError:         If the state file cannot be read or written.
        """

    def run(self) -> dict[str, Any]:
        """Execute the rule and fire notifiers for each detected event.

        Calls ``detect()``, enriches every event with ``rule_name`` and
        ``triggered_at``, then sends each event to every notifier.
        Notifier failures are logged per-notifier and do not stop
        remaining notifiers from running.

        Returns:
            Result dict with keys:
                started_at   (str): ISO-8601 start timestamp.
                finished_at  (str): ISO-8601 finish timestamp.
                status       (str): ``ok``, ``error``, or ``partial``.
                events_count (int): Number of events detected.
                error        (str | None): Error message if status != ``ok``.
        """
        started_at = datetime.now(timezone.utc)
        result = self._execute(started_at)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result

    def _execute(self, started_at: datetime) -> dict[str, Any]:
        """Run detection and notifier dispatch, returning a result dict.

        Args:
            started_at: Datetime when the run began.

        Returns:
            Partial result dict (without ``finished_at``).
        """
        try:
            events = self.detect()
        except Exception as exc:
            logger.error("Rule '%s' detect() failed: %s", self.name, exc)
            return self._result(started_at, "error", 0, str(exc))

        for event in events:
            self._enrich_event(event, started_at)
            self._dispatch(event)

        return self._result(started_at, "ok", len(events))

    def _enrich_event(
        self, event: dict[str, Any], started_at: datetime
    ) -> None:
        """Attach ``rule_name`` and ``triggered_at`` to an event in-place.

        Args:
            event:      Event dict to enrich.
            started_at: Datetime to use as the triggered_at timestamp.

        Returns:
            None
        """
        event["rule_name"] = self.name
        event["triggered_at"] = started_at.isoformat()

    def _dispatch(self, event: dict[str, Any]) -> None:
        """Send an event to all notifiers, logging failures individually.

        A failing notifier does not stop other notifiers from running.

        Args:
            event: Enriched event dict to deliver.

        Returns:
            None
        """
        for notifier in self.notifiers:
            try:
                notifier.send(event)
            except NotifierError as exc:
                logger.error(
                    "Notifier %s failed for rule '%s': %s",
                    notifier.__class__.__name__,
                    self.name,
                    exc,
                )

    def _result(
        self,
        started_at: datetime,
        status: str,
        events_count: int,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Build the standard result dict returned by ``run()``.

        Args:
            started_at:   Datetime when the run began.
            status:       Execution status string.
            events_count: Number of events detected.
            error:        Optional error message string.

        Returns:
            Result dict with ``started_at``, ``status``,
            ``events_count``, and ``error`` keys.
        """
        return {
            "started_at": started_at.isoformat(),
            "status": status,
            "events_count": events_count,
            "error": error,
        }
