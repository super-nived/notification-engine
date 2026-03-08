"""
Job Ready Rule — detects newly released and approved jobs in PocketBase.

Monitors ``OCCDUBAI01_jobDetails`` for jobs that are:
  - jobStatus  = "Released"
  - customerApproved = "YES"
  - internalRoutingError = "" (no routing errors)

On the first run, baselines to the latest matching job and fires no alerts.
On subsequent runs, alerts on any new matching job created after the last seen.
State is persisted via ``self.state`` (PocketBase-backed RuleStateStore).

Upload via dashboard → Create Rule page → Upload New Rule Class.
Then create a rule with:
  - Rule Class : JobReadyRule
  - collection : OCCDUBAI01_jobDetails   (default)
  - Schedule   : as required
"""

import logging
from typing import Any

from app.datasources.pocketbase import PocketBaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_STATE_KEY = "last_seen"
_FALLBACK_TIMESTAMP = "2000-01-01 00:00:00.000Z"


class JobReadyRule(BaseRule):
    """Alerts when a new job becomes ready for production.

    A job is considered ready when all three conditions are met:
      - jobStatus = "Released"
      - customerApproved = "YES"
      - internalRoutingError = "" (blank — no errors)

    On the first run it baselines to the latest matching record and
    fires no alerts. On subsequent runs it fetches only records created
    after the last seen timestamp so each job alerts exactly once.

    Args:
        datasource:  Authenticated PocketBase connector.
        notifiers:   One or more notifiers to fire on detection.
        collection:  PocketBase collection name (default: OCCDUBAI01_jobDetails).
    """

    name = "job_ready_rule"
    description = (
        "Alerts when a new job is Released, customer-approved, "
        "and has no internal routing errors."
    )
    params_schema = [
        {
            "key":     "collection",
            "label":   "PocketBase Collection",
            "type":    "text",
            "default": "OCCDUBAI01_jobDetails",
            "hint":    "PocketBase collection to monitor. Default: OCCDUBAI01_jobDetails.",
        },
        {
            "key":     "job_status",
            "label":   "Job Status Filter",
            "type":    "text",
            "default": "Released",
            "hint":    "Only alert on jobs with this jobStatus value. Default: Released.",
        },
        {
            "key":     "customer_approved",
            "label":   "Customer Approved Filter",
            "type":    "text",
            "default": "YES",
            "hint":    "Only alert on jobs with this customerApproved value. Default: YES.",
        },
    ]

    def __init__(
        self,
        datasource: PocketBaseDataSource,
        notifiers: list[BaseNotifier],
        collection: str = "OCCDUBAI01_jobDetails",
        job_status: str = "Released",
        customer_approved: str = "YES",
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection = collection
        self.job_status = job_status
        self.customer_approved = customer_approved

    # ── Filters ──────────────────────────────────────────────────────────────

    def _ready_filter(self, since: str | None = None) -> str:
        """Build the PocketBase filter for ready jobs.

        Args:
            since: Optional ISO-8601 timestamp — only return records
                   created after this value. Pass None to fetch all.

        Returns:
            PocketBase filter expression string.
        """
        conditions = [
            f'jobStatus = "{self.job_status}"',
            f'customerApproved = "{self.customer_approved}"',
            'internalRoutingError = ""',
        ]
        if since:
            conditions.append(f'created > "{since}"')
        return " && ".join(conditions)

    # ── Data fetching ─────────────────────────────────────────────────────────

    def _fetch_latest(self) -> list[dict[str, Any]]:
        """Fetch the single most recent ready job for baseline setup.

        Returns:
            List with at most one record dict.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter": self._ready_filter(),
            "sort": "-created",
            "per_page": 1,
        })

    def _fetch_since(self, timestamp: str) -> list[dict[str, Any]]:
        """Fetch all ready jobs created after ``timestamp``.

        Args:
            timestamp: ISO-8601 lower-bound filter string.

        Returns:
            List of record dicts ordered by created ascending.

        Raises:
            DataSourceError: If the PocketBase request fails.
        """
        return self.datasource.fetch({
            "collection": self.collection,
            "filter": self._ready_filter(since=timestamp),
            "sort": "created",
            "per_page": 100,
        })

    # ── Baseline ─────────────────────────────────────────────────────────────

    def _set_baseline(self) -> None:
        """Baseline on first run — no alerts fired.

        Saves the latest ready job's created timestamp so only future
        jobs trigger alerts. Falls back to a far-past sentinel if no
        matching jobs exist yet.

        Returns:
            None
        """
        records = self._fetch_latest()
        baseline = records[0]["created"] if records else _FALLBACK_TIMESTAMP
        self.state.set(_STATE_KEY, baseline)
        logger.info("JobReadyRule: baseline set to %s", baseline)

    # ── Event building ────────────────────────────────────────────────────────

    def _build_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a ready job record into an alert event dict.

        Args:
            record: Raw record dict from PocketBaseDataSource.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        job_number = record.get("jobNumber", "N/A")
        customer   = record.get("customerName", "N/A")
        item_code  = record.get("itemCode", "N/A")
        job_qty    = record.get("jobQty", "N/A")
        request_dt = record.get("requestDate", "N/A")
        so_number  = record.get("soNumber", "N/A")

        return {
            "message": (
                f"Job {job_number} is ready for production — "
                f"Customer: {customer}, Item: {item_code}, Qty: {job_qty}"
            ),
            "data": {
                "job_number":       job_number,
                "so_number":        so_number,
                "customer_name":    customer,
                "customer_number":  record.get("customerNumber", "N/A"),
                "item_code":        item_code,
                "job_qty":          job_qty,
                "job_status":       record.get("jobStatus", "N/A"),
                "customer_approved":record.get("customerApproved", "N/A"),
                "request_date":     request_dt,
                "job_creation_date":record.get("jobCreationDate", "N/A"),
                "order_type":       record.get("orderType", "N/A"),
                "product_type":     record.get("productType", "N/A"),
                "description":      record.get("description", "N/A"),
                "created":          record.get("created", "N/A"),
            },
        }

    # ── detect ────────────────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Query PocketBase for new ready jobs since the last run.

        On first call (no stored state), sets baseline and returns ``[]``.
        On subsequent calls, fetches new matching records, builds events,
        advances state, and returns the events.

        Returns:
            List of event dicts. Empty if no new ready jobs found.

        Raises:
            DataSourceError: If the PocketBase fetch fails.
        """
        last_seen = self.state.get(_STATE_KEY)

        if last_seen is None:
            self._set_baseline()
            return []

        new_records = self._fetch_since(last_seen)

        if not new_records:
            logger.debug("JobReadyRule: no new ready jobs since %s", last_seen)
            return []

        events = [self._build_event(r) for r in new_records]
        self.state.set(_STATE_KEY, new_records[-1]["created"])
        logger.info("JobReadyRule: %d new ready job(s) detected", len(events))
        return events
