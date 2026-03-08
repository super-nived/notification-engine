"""
Scheduled Job Rule — detects newly scheduled jobs in PocketBase.

Monitors a PocketBase collection (default: ASWNDUBAI_Job) for new records
where ``isScheduled = true``. Fires one notification per new scheduled job.

On the first run it baselines to the latest matching record and fires no
alerts. On subsequent runs it fetches only records created after the last
seen timestamp so each job alerts exactly once.

State is persisted via ``self.state`` (PocketBase-backed RuleStateStore).

Upload via dashboard → Create Rule page → Upload New Rule Class.
Then create a rule with:
  - Rule Class   : ScheduledJobRule
  - collection   : ASWNDUBAI_Job          (default, user can override)
  - scheduled_field : isScheduled         (default, field name to check)
  - Schedule     : as required
"""

import logging
from typing import Any

from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_STATE_KEY = "last_seen"
_FALLBACK_TIMESTAMP = "2000-01-01 00:00:00.000Z"


class ScheduledJobRule(BaseRule):
    """Alerts when a new record with isScheduled=true appears in the collection.

    On the first run it baselines to the latest matching record and fires no
    alerts. On subsequent runs it fetches only records created after the last
    seen timestamp so each job alerts exactly once.

    Args:
        datasource:       Authenticated PocketBase connector.
        notifiers:        One or more notifiers to fire on detection.
        collection:       PocketBase collection to monitor.
        scheduled_field:  Boolean field name that indicates a job is scheduled.
    """

    name = "scheduled_job_rule"
    description = (
        "Alerts when a new job record is marked as scheduled "
        "(isScheduled = true) in the monitored PocketBase collection."
    )
    params_schema = [
        {
            "key":     "collection",
            "label":   "PocketBase Collection",
            "type":    "text",
            "default": "ASWNDUBAI_Job",
            "hint":    "The collection to monitor for scheduled jobs. Default: ASWNDUBAI_Job.",
        },
        {
            "key":     "scheduled_field",
            "label":   "Scheduled Field Name",
            "type":    "text",
            "default": "isScheduled",
            "hint":    "Boolean field that marks a job as scheduled. Default: isScheduled.",
        },
    ]

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "ASWNDUBAI_Job",
        scheduled_field: str = "isScheduled",
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection
        self.scheduled_field = scheduled_field

    # ── Filters ──────────────────────────────────────────────────────────────

    def _scheduled_filter(self, since: str | None = None) -> str:
        """Build the PocketBase filter for scheduled jobs.

        Args:
            since: Optional ISO-8601 timestamp — only return records
                   created after this value. Pass None to fetch all.

        Returns:
            PocketBase filter expression string.
        """
        conditions = [f"{self.scheduled_field} = true"]
        if since:
            conditions.append(f'created > "{since}"')
        return " && ".join(conditions)

    # ── Data fetching ─────────────────────────────────────────────────────────

    def _fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the single most recent scheduled job for baseline setup.

        Returns:
            List with at most one record dict.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter":     self._scheduled_filter(),
            "sort":       "-created",
            "per_page":   1,
        })

    def _fetch_since(self, timestamp: str) -> list[dict[str, Any]]:
        """Fetch all scheduled jobs created after ``timestamp``.

        Args:
            timestamp: ISO-8601 lower-bound filter string.

        Returns:
            List of record dicts ordered by created ascending.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter":     self._scheduled_filter(since=timestamp),
            "sort":       "created",
            "per_page":   100,
        })

    # ── Baseline ─────────────────────────────────────────────────────────────

    def _set_baseline(self) -> None:
        """Baseline on first run — no alerts fired.

        Saves the latest scheduled job's created timestamp so only future
        records trigger alerts. Falls back to a far-past sentinel if no
        matching records exist yet.
        """
        records = self._fetch_latest()
        baseline = records[0]["created"] if records else _FALLBACK_TIMESTAMP
        self.state.set(_STATE_KEY, baseline)
        logger.info("ScheduledJobRule: baseline set to %s", baseline)

    # ── Event building ────────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a scheduled job record into an alert event dict.

        Args:
            record: Raw record dict from PocketBaseDataSource.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        job_id   = record.get("id", "N/A")
        job_name = record.get("name", record.get("jobName", record.get("jobNumber", job_id)))
        created  = record.get("created", "N/A")

        return {
            "message": f"Job '{job_name}' has been scheduled (id: {job_id})",
            "data": {
                "id":               job_id,
                "job_name":         job_name,
                "is_scheduled":     record.get(self.scheduled_field, True),
                "created":          created,
                **{k: v for k, v in record.items()
                   if k not in {"id", "created", "updated", "collectionId", "collectionName"}},
            },
        }

    # ── detect ────────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for new scheduled jobs since the last run.

        On first call (no stored state), sets baseline and returns ``[]``.
        On subsequent calls, fetches new matching records, builds events,
        advances state, and returns the events.

        Returns:
            List of event dicts. Empty if no new scheduled jobs found.
        """
        last_seen = self.state.get(_STATE_KEY)

        if last_seen is None:
            self._set_baseline()
            return []

        new_records = self._fetch_since(last_seen)

        if not new_records:
            logger.debug("ScheduledJobRule: no new scheduled jobs since %s", last_seen)
            return []

        events = [self._build_event(r) for r in new_records]
        self.state.set(_STATE_KEY, new_records[-1]["created"])
        logger.info("ScheduledJobRule: %d new scheduled job(s) detected", len(events))
        return events
