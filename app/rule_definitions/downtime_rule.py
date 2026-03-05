"""
Downtime Rule — detects new shift downtime entries in PocketBase.

Monitors a configurable PocketBase collection and fires an alert
event for every record created after the last seen timestamp.
State is persisted between runs via ``self.state`` (PocketBase-backed
``RuleStateStore``), replacing the old plain-text file approach.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_FALLBACK_TIMESTAMP = "2000-01-01 00:00:00.000Z"
_STATE_KEY = "last_seen"


class DowntimeRule(BaseRule):
    """Detects new entries in a PocketBase shift downtime collection.

    On the first run, baselines to the latest existing record and fires
    no alerts. On subsequent runs, fetches only records created after
    the stored timestamp and returns one event per new record.

    State is stored in PocketBase via ``self.state`` so it survives
    restarts and is not tied to a specific server path.

    Args:
        datasource:  Authenticated PocketBase connector.
        notifiers:   One or more notifiers to fire on detection.
        collection:  PocketBase collection name to monitor.
    """

    name = "downtime_rule"
    description = "Alerts when a new shift downtime entry is added."

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "ASWNDUBAI_shift_downtime",
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection

    # ── State helpers ────────────────────────────────────────────────────────

    def _read_state(self) -> str | None:
        """Read last-seen timestamp from the rule state store.

        Returns:
            Timestamp string if previously set, else ``None``.
        """
        return self.state.get(_STATE_KEY)

    def _write_state(self, timestamp: str) -> None:
        """Persist last-seen timestamp to the rule state store.

        Args:
            timestamp: ISO-8601 timestamp string to save.
        """
        self.state.set(_STATE_KEY, timestamp)

    # ── Data fetching ────────────────────────────────────────────────────────

    def _fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the single most recent record for baseline setup.

        Returns:
            List with at most one record dict.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "sort": "-created",
            "per_page": 1,
        })

    def _fetch_since(self, timestamp: str) -> list[dict[str, Any]]:
        """Fetch all records created strictly after ``timestamp``.

        Args:
            timestamp: ISO-8601 lower-bound filter string.

        Returns:
            List of record dicts ordered by created ascending.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter": f'created > "{timestamp}"',
            "sort": "created",
            "per_page": 100,
        })

    # ── Baseline ─────────────────────────────────────────────────────────────

    def _set_baseline(self) -> None:
        """Set initial state on the very first run — no alerts fired.

        Fetches the latest record and saves its timestamp so that only
        future records trigger alerts. Falls back to a far-past sentinel
        if the collection is empty.

        Returns:
            None
        """
        records = self._fetch_latest()
        baseline = records[0]["created"] if records else _FALLBACK_TIMESTAMP
        self._write_state(baseline)
        logger.info("DowntimeRule: baseline set to %s", baseline)

    # ── Event building ───────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a single PocketBase record into an alert event dict.

        Args:
            record: Raw record dict from PocketBaseDataSource.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        machines = ", ".join(record.get("machines", [])) or "N/A"
        return {
            "message": (
                f"New downtime entry — "
                f"reason: {record.get('reason_code', 'N/A')}"
            ),
            "data": {
                "id": record["id"],
                "machines": machines,
                "reason_code": record.get("reason_code", "N/A"),
                "start_date": record.get("start_date", "N/A"),
                "end_date": record.get("end_date", "N/A"),
                "created": record["created"],
            },
        }

    def _build_events(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert a list of records into alert events.

        Args:
            records: List of raw record dicts.

        Returns:
            List of event dicts, one per record.
        """
        return [self._build_event(r) for r in records]

    # ── detect ───────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for new downtime entries since the last run.

        On first call (no stored state), sets baseline and returns ``[]``.
        On subsequent calls, fetches new records, builds events, advances
        state, and returns the events.

        Returns:
            List of event dicts. Empty if nothing new was found.

        Raises:
            DataSourceError: If the PocketBase fetch fails.
        """
        last_seen = self._read_state()

        if last_seen is None:
            self._set_baseline()
            return []

        new_records = self._fetch_since(last_seen)

        if not new_records:
            logger.debug("DowntimeRule: no new records since %s", last_seen)
            return []

        events = self._build_events(new_records)
        self._write_state(new_records[-1]["created"])
        logger.info(
            "DowntimeRule: %d new record(s) detected", len(events)
        )
        return events
