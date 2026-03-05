"""
OEE Rule — detects machines whose OEE falls below a configured threshold.

Monitors the ``oee_shift_machine_summary`` PocketBase collection. Users
control which machines to watch and the OEE threshold via the API — no
code changes required.

Deduplication: an alert fires for a machine+shift combination only once.
It clears when the OEE recovers above the threshold, allowing it to fire
again on future drops. State is persisted via ``self.state``.
"""

import logging
from typing import Any

from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_ALERTED_KEY = "alerted_keys"


class OEERule(BaseRule):
    """Detects machines with OEE below ``oee_threshold`` in PocketBase.

    Reads from ``oee_shift_machine_summary``. Key fields used:
        machine_id, shift_id, shift_date, oee, area_id,
        availability_index, performance_index, quality_index,
        total_downtime_minutes, is_active.

    Parameters are fully user-editable via the API:
        collection    — PocketBase collection (default: oee_shift_machine_summary)
        oee_threshold — Alert when OEE is below this value (default: 60.0)
        machine_ids   — List of machine IDs to monitor; empty = all machines

    Args:
        datasource:    Authenticated PocketBase connector.
        notifiers:     One or more notifiers to fire on detection.
        collection:    PocketBase collection name to monitor.
        oee_threshold: Minimum acceptable OEE percentage (0–100).
        machine_ids:   Specific machine IDs to watch. Empty = all machines.
    """

    name = "oee_rule"
    description = "Alerts when a machine OEE drops below the configured threshold."

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "oee_shift_machine_summary",
        oee_threshold: float = 60.0,
        machine_ids: list[str] | None = None,
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection
        self.oee_threshold = float(oee_threshold)
        self.machine_ids = machine_ids or []

    # ── State helpers ────────────────────────────────────────────────────────

    def _alerted_key(self, machine_id: str, shift_id: str) -> str:
        """Build a unique deduplication key for a machine+shift pair.

        Args:
            machine_id: Machine identifier string.
            shift_id:   Shift identifier string.

        Returns:
            Composite key string.
        """
        return f"{machine_id}:{shift_id}"

    def _get_alerted(self) -> set[str]:
        """Return machine+shift keys currently in an alert state.

        Returns:
            Set of composite key strings.
        """
        return set(self.state.get(_ALERTED_KEY, []))

    def _save_alerted(self, alerted: set[str]) -> None:
        """Persist the alerted keys set.

        Args:
            alerted: Updated set of composite key strings.
        """
        self.state.set(_ALERTED_KEY, list(alerted))

    # ── Data fetching ────────────────────────────────────────────────────────

    def _build_low_oee_filter(self) -> str:
        """Build the PocketBase filter for active records below the threshold.

        Only queries records where ``is_active = true`` to avoid alerting
        on completed or historical shifts.

        Returns:
            PocketBase filter expression string.
        """
        base = f"oee < {self.oee_threshold} && is_active = true"
        if not self.machine_ids:
            return base
        machine_filter = " || ".join(
            f'machine_id = "{mid}"' for mid in self.machine_ids
        )
        return f"{base} && ({machine_filter})"

    def _fetch_low_oee_records(self) -> list[dict[str, Any]]:
        """Fetch active records where OEE is below the threshold.

        Returns:
            List of record dicts ordered by shift_date descending.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter": self._build_low_oee_filter(),
            "sort": "-shift_date",
            "per_page": 100,
        })

    def _fetch_recovered(self, alerted: set[str]) -> set[str]:
        """Return machine+shift keys whose OEE has recovered above the threshold.

        Args:
            alerted: Composite keys currently in alert state.

        Returns:
            Subset of ``alerted`` that have recovered.
        """
        recovered: set[str] = set()
        for key in alerted:
            try:
                machine_id, shift_id = key.split(":", 1)
                records = self.datasource.fetch({
                    "collection": self.collection,
                    "filter": (
                        f'machine_id = "{machine_id}" '
                        f'&& shift_id = "{shift_id}" '
                        f'&& oee >= {self.oee_threshold}'
                    ),
                    "sort": "-shift_date",
                    "per_page": 1,
                })
                if records:
                    recovered.add(key)
            except Exception as exc:
                logger.warning(
                    "OEERule: could not check recovery for key '%s': %s", key, exc
                )
        return recovered

    # ── Event building ───────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a low-OEE record into an alert event dict.

        Uses the actual fields from ``oee_shift_machine_summary``.

        Args:
            record: Raw record dict from PocketBaseDataSource.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        machine_id  = record.get("machine_id", "unknown")
        oee_value   = record.get("oee", "N/A")
        shift_id    = record.get("shift_id", "N/A")
        shift_date  = record.get("shift_date", "N/A")
        area_id     = record.get("area_id", "N/A")

        return {
            "message": (
                f"Machine {machine_id} OEE is {oee_value}% "
                f"— below threshold {self.oee_threshold}% "
                f"(shift {shift_id}, {shift_date})"
            ),
            "data": {
                "machine_id":              machine_id,
                "area_id":                 area_id,
                "shift_id":                shift_id,
                "shift_date":              shift_date,
                "oee":                     oee_value,
                "threshold":               self.oee_threshold,
                "availability_index":      record.get("availability_index"),
                "performance_index":       record.get("performance_index"),
                "quality_index":           record.get("quality_index"),
                "total_downtime_minutes":  record.get("total_downtime_minutes"),
            },
        }

    # ── detect ───────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for active machines with OEE below the threshold.

        Deduplicates by machine+shift key — fires once per machine per shift.
        Clears a key when OEE recovers so it can fire again on future drops.

        Returns:
            List of event dicts. Empty if no new machines are below threshold.

        Raises:
            DataSourceError: If the PocketBase fetch fails.
        """
        records = self._fetch_low_oee_records()
        alerted = self._get_alerted()

        # Clear keys whose OEE has recovered
        if alerted:
            recovered = self._fetch_recovered(alerted)
            if recovered:
                alerted -= recovered
                logger.info(
                    "OEERule: %d machine+shift(s) recovered: %s",
                    len(recovered), recovered,
                )

        # Alert only keys not already in the alerted set
        new_events: list[dict[str, Any]] = []
        for record in records:
            machine_id = record.get("machine_id", "")
            shift_id   = record.get("shift_id", "")
            if not machine_id:
                continue
            key = self._alerted_key(machine_id, shift_id)
            if key not in alerted:
                new_events.append(self._build_event(record))
                alerted.add(key)

        self._save_alerted(alerted)

        if not new_events:
            logger.debug("OEERule: no new machines below %.1f%%", self.oee_threshold)
            return []

        logger.info(
            "OEERule: %d new machine+shift(s) below %.1f%% OEE threshold",
            len(new_events), self.oee_threshold,
        )
        return new_events
