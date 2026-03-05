"""
OEE Rule — detects machines whose OEE falls below a configured threshold.

Monitors a configurable PocketBase OEE collection. Users control which
machines to watch and the OEE threshold via the ``PATCH /rules/{id}/params``
API endpoint — no code changes required.

Deduplication: a machine fires an alert only once per alert window. It is
cleared from the alerted set when its OEE recovers above the threshold,
allowing it to fire again on future drops. The alerted set is persisted
between runs via ``self.state``.
"""

import logging
from typing import Any

from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_ALERTED_KEY = "alerted_machines"


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

    # ── State helpers ────────────────────────────────────────────────────────

    def _get_alerted(self) -> set[str]:
        """Return machine IDs currently in an alert state.

        Returns:
            Set of machine ID strings.
        """
        return set(self.state.get(_ALERTED_KEY, []))

    def _save_alerted(self, alerted: set[str]) -> None:
        """Persist the alerted machines set.

        Args:
            alerted: Updated set of machine ID strings.
        """
        self.state.set(_ALERTED_KEY, list(alerted))

    # ── Data fetching ────────────────────────────────────────────────────────

    def _build_low_oee_filter(self) -> str:
        """Build the PocketBase filter for machines below the threshold.

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
            "filter": self._build_low_oee_filter(),
            "sort": "-created",
            "per_page": 100,
        })

    def _fetch_recovered(self, alerted: set[str]) -> set[str]:
        """Return machines that were alerted but have now recovered.

        A machine is considered recovered when its current OEE is at or
        above the threshold. Recovered machines are removed from the alerted
        set so they can fire again on future drops.

        Args:
            alerted: Machine IDs currently in alert state.

        Returns:
            Subset of ``alerted`` whose OEE has recovered.
        """
        recovered: set[str] = set()
        for machine_id in alerted:
            try:
                records = self.datasource.fetch({
                    "collection": self.collection,
                    "filter": (
                        f'machine_id = "{machine_id}" '
                        f'&& oee >= {self.oee_threshold}'
                    ),
                    "sort": "-created",
                    "per_page": 1,
                })
                if records:
                    recovered.add(machine_id)
            except Exception as exc:
                logger.warning(
                    "OEERule: could not check recovery for machine '%s': %s",
                    machine_id,
                    exc,
                )
        return recovered

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

    # ── detect ───────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for machines with OEE below the threshold.

        Fires an alert only for machines not already in the alerted set.
        Clears machines from the alerted set when their OEE recovers above
        the threshold so they can fire again on future drops.

        Returns:
            List of event dicts. Empty if no new machines are below threshold.

        Raises:
            DataSourceError: If the PocketBase fetch fails.
        """
        records = self._fetch_low_oee_records()
        alerted = self._get_alerted()

        # Clear machines whose OEE has recovered
        if alerted:
            recovered = self._fetch_recovered(alerted)
            if recovered:
                alerted -= recovered
                logger.info(
                    "OEERule: %d machine(s) recovered: %s", len(recovered), recovered
                )

        # Alert only machines not already in the alerted set
        new_events: list[dict[str, Any]] = []
        for record in records:
            machine_id = record.get("machine_id", "")
            if machine_id and machine_id not in alerted:
                new_events.append(self._build_event(record))
                alerted.add(machine_id)

        self._save_alerted(alerted)

        if not new_events:
            logger.debug("OEERule: no new machines below %.1f%%", self.oee_threshold)
            return []

        logger.info(
            "OEERule: %d new machine(s) below %.1f%% OEE threshold",
            len(new_events),
            self.oee_threshold,
        )
        return new_events
