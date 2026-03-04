"""
OEE Rule — detects machines whose OEE falls below a configured threshold.

Monitors a configurable PocketBase OEE collection. Users control which
machines to watch and the OEE threshold via the ``PATCH /rules/{id}/params``
API endpoint — no code changes required.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)


class OEERule(BaseRule):
    """Detects machines with OEE below ``oee_threshold`` in PocketBase.

    Parameters are fully user-editable via the API:
        collection    — PocketBase collection to query (default: oee_realtime_status)
        oee_threshold — Alert when OEE is below this value (default: 60.0)
        machine_ids   — List of machine IDs to monitor; empty list = all machines

    Args:
        datasource:    Authenticated PocketBase connector.
        notifiers:     One or more notifiers to fire on detection.
        collection:    PocketBase collection name to monitor.
        oee_threshold: Minimum acceptable OEE value (0–100).
        machine_ids:   List of machine IDs to filter. Empty = all machines.
    """

    name = "oee_rule"
    description = "Alerts when a machine OEE drops below the configured threshold."

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "oee_realtime_status",
        oee_threshold: float = 60.0,
        machine_ids: list[str] | None = None,
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection
        self.oee_threshold = float(oee_threshold)
        self.machine_ids = machine_ids or []

    # ── Data fetching ────────────────────────────────────────────────────────

    def _build_filter(self) -> str:
        """Build the PocketBase filter string for the OEE query.

        Filters for records where ``oee < threshold``. If ``machine_ids``
        is non-empty, adds an additional machine ID filter.

        Returns:
            PocketBase filter expression string.
        """
        base = f"oee < {self.oee_threshold}"
        if not self.machine_ids:
            return base
        machine_filter = " || ".join(
            f'machine_id = "{mid}"' for mid in self.machine_ids
        )
        return f"{base} && ({machine_filter})"

    def _fetch_low_oee_records(self) -> list[dict[str, Any]]:
        """Fetch all records where OEE is below the threshold.

        Returns:
            List of record dicts matching the OEE filter.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter": self._build_filter(),
            "sort": "-created",
            "per_page": 100,
        })

    # ── Event building ───────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a single low-OEE record into an alert event dict.

        Args:
            record: Raw record dict from PocketBaseDataSource.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        machine = record.get("machine_id", "unknown")
        oee_value = record.get("oee", "N/A")
        return {
            "message": (
                f"Machine {machine} OEE is {oee_value}% "
                f"— below threshold {self.oee_threshold}%"
            ),
            "data": {
                "id": record.get("id"),
                "machine_id": machine,
                "oee": oee_value,
                "threshold": self.oee_threshold,
                "shift": record.get("shift", "N/A"),
                "recorded_at": record.get("created", "N/A"),
            },
        }

    def _build_events(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Convert a list of low-OEE records into alert events.

        Args:
            records: List of raw record dicts.

        Returns:
            List of event dicts, one per record.
        """
        return [self._build_event(r) for r in records]

    # ── detect ───────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for machines with OEE below the threshold.

        Fetches records matching the OEE filter and machine ID filter,
        then returns one event per matching record.

        Returns:
            List of event dicts. Empty if no machines are below threshold.

        Raises:
            DataSourceError: If the PocketBase fetch fails.
        """
        records = self._fetch_low_oee_records()

        if not records:
            logger.debug(
                "OEERule: no machines below %.1f%%", self.oee_threshold
            )
            return []

        events = self._build_events(records)
        logger.info(
            "OEERule: %d machine(s) below %.1f%% OEE threshold",
            len(events),
            self.oee_threshold,
        )
        return events
