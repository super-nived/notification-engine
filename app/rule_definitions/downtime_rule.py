"""
Downtime Rule — detects new shift downtime entries in PocketBase.

Monitors a configurable PocketBase collection and fires an alert
event for every record created after the last seen timestamp.

Each alert includes:
  - Machine display name (resolved via PocketBase ``expand=machines``)
  - Reason code
  - Duration calculated from ``start_date`` / ``end_date``

State is persisted between runs via ``self.state`` (PocketBase-backed
``RuleStateStore``), replacing the old plain-text file approach.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_FALLBACK_TIMESTAMP = "2000-01-01 00:00:00.000Z"
_STATE_KEY = "last_seen"
# PocketBase datetime format used in start_date / end_date fields
_PB_DT_FORMAT = "%Y-%m-%d %H:%M:%S.%fZ"
_PB_DT_FORMAT_SHORT = "%Y-%m-%d %H:%M:%SZ"


class DowntimeRule(BaseRule):
    """Detects new entries in a PocketBase shift downtime collection.

    On the first run, baselines to the latest existing record and fires
    no alerts. On subsequent runs, fetches only records created after
    the stored timestamp and returns one event per new record.

    Each event message is:
        "Downtime alert: <machine_name> — <reason_code> for <duration>"

    Args:
        datasource:  Authenticated PocketBase connector.
        notifiers:   One or more notifiers to fire on detection.
        collection:  PocketBase collection name to monitor.
    """

    name = "downtime_rule"
    description = "Alerts when a new shift downtime entry is added, with machine name and duration."
    params_schema = [
        {
            "key":     "collection",
            "label":   "PocketBase Collection",
            "type":    "text",
            "default": "ASWNDUBAI_shift_downtime",
            "hint":    "The exact collection name in PocketBase to monitor for new downtime entries.",
        },
    ]

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "ASWNDUBAI_shift_downtime",
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection

    # ── Data fetching ────────────────────────────────────────────────────────

    def _fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the single most recent record for baseline setup.

        Returns:
            List with at most one record dict.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "sort":       "-created",
            "per_page":   1,
            "expand":     "machines",
        })

    def _fetch_since(self, timestamp: str) -> list[dict[str, Any]]:
        """Fetch all records created strictly after ``timestamp``.

        Args:
            timestamp: ISO-8601 lower-bound filter string.

        Returns:
            List of record dicts ordered by created ascending.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter":     f'created > "{timestamp}"',
            "sort":       "created",
            "per_page":   100,
            "expand":     "machines",
        })

    # ── Duration calculation ──────────────────────────────────────────────────

    @staticmethod
    def _calc_duration(start: str, end: str) -> str:
        """Calculate a human-readable duration between two PocketBase datetime strings.

        Tries both full-microsecond and second-precision formats.

        Args:
            start: Start datetime string from PocketBase.
            end:   End datetime string from PocketBase.

        Returns:
            Duration string like ``"2h 30m"`` or ``"45m"`` or ``"N/A"`` on failure.
        """
        if not start or not end:
            return "N/A"

        def _parse(dt_str: str) -> datetime | None:
            for fmt in (_PB_DT_FORMAT, _PB_DT_FORMAT_SHORT):
                try:
                    return datetime.strptime(dt_str, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            return None

        dt_start = _parse(start)
        dt_end = _parse(end)

        if dt_start is None or dt_end is None:
            return "N/A"

        total_seconds = max(int((dt_end - dt_start).total_seconds()), 0)
        hours, remainder = divmod(total_seconds, 3600)
        minutes = remainder // 60

        if hours and minutes:
            return f"{hours}h {minutes}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"

    # ── Event building ───────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a single PocketBase record into an alert event dict.

        Resolves machine display name from the expanded ``machines`` relation.
        Calculates downtime duration from ``start_date`` and ``end_date``.

        Args:
            record: Raw record dict from PocketBaseDataSource (with expand).

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        # Resolve machine name from expand.machines (list of relation records)
        machine_name = "Unknown"
        machine_id = ""
        expanded = record.get("expand", {})
        machines_expand = expanded.get("machines", [])
        if machines_expand:
            first_machine = machines_expand[0] if isinstance(machines_expand, list) else machines_expand
            machine_name = first_machine.get("displayName") or first_machine.get("name") or "Unknown"
            machine_id = first_machine.get("id", "")

        reason_code = record.get("reason_code", "N/A")
        start_date = record.get("start_date", "")
        end_date = record.get("end_date", "")
        duration = self._calc_duration(start_date, end_date)

        return {
            "message": (
                f"Downtime alert: {machine_name} — "
                f"{reason_code} for {duration}"
            ),
            "data": {
                "id":           record["id"],
                "machine_id":   machine_id,
                "machine_name": machine_name,
                "reason_code":  reason_code,
                "start_date":   start_date,
                "end_date":     end_date,
                "duration":     duration,
                "created":      record.get("created", ""),
            },
        }

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
        last_seen = self.state.get(_STATE_KEY)

        if last_seen is None:
            # First run — baseline only, no alerts
            records = self._fetch_latest()
            baseline = records[0]["created"] if records else _FALLBACK_TIMESTAMP
            self.state.set(_STATE_KEY, baseline)
            logger.info("DowntimeRule: baseline set to %s", baseline)
            return []

        new_records = self._fetch_since(last_seen)

        if not new_records:
            logger.debug("DowntimeRule: no new records since %s", last_seen)
            return []

        events = [self._build_event(r) for r in new_records]
        self.state.set(_STATE_KEY, new_records[-1]["created"])
        logger.info("DowntimeRule: %d new record(s) detected", len(events))
        return events
