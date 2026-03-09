"""
RuleEngine — the single condition evaluator for structured alert rules.

Replaces individual rule class files (DowntimeRule, OEERule, etc.) for
rules created through the dashboard's 3-step builder. Rules created via
the old file-upload path continue to work through their own classes.

Supported condition types
─────────────────────────
new_record    — fires for every record created after the last seen timestamp
                that matches ``condition_field op condition_value``.
threshold     — fires when the latest record's ``condition_field`` crosses
                ``condition_value`` (uses condition_op: lt/gt/lte/gte).
no_data       — fires when no record has arrived within ``window_minutes``
                (default 60). Clears once data arrives again.
change        — fires when ``condition_field`` changes value compared to
                the previously stored value.
count         — fires when the number of matching records in the last
                ``window_minutes`` exceeds ``condition_value``.
field_update  — fires when an existing record's ``condition_field`` matches
                ``condition_value`` and has not been alerted before.
                Tracks alerted record IDs in state. Clears when the field
                no longer matches (e.g. status reset). Use this for
                "record updated to match a condition" scenarios.

Operators (condition_op)
────────────────────────
eq        equals
ne        not equals
lt        less than
gt        greater than
lte       less than or equal
gte       greater than or equal
contains  substring / membership check
changed   (internal — used by the ``change`` type)

condition_extra (json field, optional)
──────────────────────────────────────
window_minutes  (int)  — lookback window for no_data and count (default 60)
count_limit     (int)  — alert threshold for the count type (default 1)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.exceptions import DataSourceError, RuleConfigError
from app.datasources.base import BaseDataSource
from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)

_STATE_LAST_SEEN = "last_seen"
_STATE_PREV_VALUE = "prev_value"
_STATE_NO_DATA_ALERTED = "no_data_alerted"
_FALLBACK_TIMESTAMP = "2000-01-01 00:00:00.000Z"

# Condition types
_NEW_RECORD   = "new_record"
_THRESHOLD    = "threshold"
_NO_DATA      = "no_data"
_CHANGE       = "change"
_COUNT        = "count"
_FIELD_UPDATE = "field_update"

CONDITION_TYPES = [_NEW_RECORD, _THRESHOLD, _NO_DATA, _CHANGE, _COUNT, _FIELD_UPDATE]

_STATE_ALERTED_IDS = "alerted_ids"


class RuleEngine(BaseRule):
    """Evaluates structured alert conditions against any data source.

    This class is instantiated by the scheduler for every rule created
    through the dashboard's 3-step builder. It reads the rule's structured
    fields (condition_type, condition_field, condition_op, condition_value,
    condition_extra) and executes the appropriate detection logic.

    Args:
        datasource:       Authenticated data source connector.
        notifiers:        One or more notifiers to fire on detection.
        collection_name:  Collection / table to monitor.
        condition_type:   One of ``new_record``, ``threshold``, ``no_data``,
                          ``change``, ``count``.
        condition_field:  Field name to evaluate (empty string for no_data).
        condition_op:     Comparison operator string.
        condition_value:  Value to compare against (as string).
        condition_extra:  Dict of optional extras (window_minutes, count_limit).
    """

    name = "rule_engine"
    description = "Structured rule engine — handles all condition types."
    params_schema = []  # structured rules do not use the params form

    def __init__(
        self,
        datasource: BaseDataSource,
        notifiers: list[BaseNotifier],
        collection_name: str = "",
        condition_type: str = _NEW_RECORD,
        condition_field: str = "",
        condition_op: str = "eq",
        condition_value: str = "",
        condition_extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(notifiers)
        self.datasource = datasource
        self.collection_name = collection_name
        self.condition_type = condition_type
        self.condition_field = condition_field
        self.condition_op = condition_op
        self.condition_value = condition_value
        self.condition_extra = condition_extra or {}

        if condition_type not in CONDITION_TYPES:
            raise RuleConfigError(
                f"Unknown condition_type '{condition_type}'. "
                f"Valid types: {CONDITION_TYPES}"
            )

    # ── Public interface ──────────────────────────────────────────────────────

    def detect(self) -> list[dict[str, Any]]:
        """Evaluate the condition and return alert events.

        Returns:
            List of event dicts. Empty if no condition is met.

        Raises:
            DataSourceError: If the data source fetch fails.
        """
        handlers = {
            _NEW_RECORD:   self._detect_new_record,
            _THRESHOLD:    self._detect_threshold,
            _NO_DATA:      self._detect_no_data,
            _CHANGE:       self._detect_change,
            _COUNT:        self._detect_count,
            _FIELD_UPDATE: self._detect_field_update,
        }
        return handlers[self.condition_type]()

    # ── Condition: new_record ─────────────────────────────────────────────────

    def _detect_new_record(self) -> list[dict[str, Any]]:
        """Alert on every new record created after the last seen timestamp.

        On the first run, baselines to the latest matching record and
        fires no alerts. On subsequent runs fires one event per new record.

        Returns:
            List of event dicts.
        """
        last_seen = self.state.get(_STATE_LAST_SEEN)

        if last_seen is None:
            # First run — baseline only
            records = self._fetch(sort="-created", per_page=1)
            baseline = records[0]["created"] if records else _FALLBACK_TIMESTAMP
            self.state.set(_STATE_LAST_SEEN, baseline)
            logger.info("%s: baselined at %s", self.name, baseline)
            return []

        filter_expr = self._build_filter(since=last_seen)
        new_records = self._fetch(filter_expr=filter_expr, sort="created")

        if not new_records:
            return []

        events = [self._record_event(r) for r in new_records]
        self.state.set(_STATE_LAST_SEEN, new_records[-1]["created"])
        logger.info("%s: %d new record(s)", self.name, len(events))
        return events

    # ── Condition: threshold ──────────────────────────────────────────────────

    def _detect_threshold(self) -> list[dict[str, Any]]:
        """Alert when the latest record's field crosses the threshold.

        Fetches the single most recent record and compares
        ``condition_field op condition_value``. Alerts once until
        the condition clears.

        Returns:
            List with one event if threshold is crossed, else empty.
        """
        records = self._fetch(sort="-created", per_page=1)
        if not records:
            return []

        record = records[0]
        raw_value = record.get(self.condition_field)
        if raw_value is None:
            logger.debug("%s: field '%s' not in record", self.name, self.condition_field)
            return []

        try:
            current = float(raw_value)
            threshold = float(self.condition_value)
        except (ValueError, TypeError):
            logger.warning(
                "%s: cannot compare non-numeric values '%s' / '%s'",
                self.name, raw_value, self.condition_value,
            )
            return []

        is_breached = _compare(current, self.condition_op, threshold)
        was_alerted = self.state.get("threshold_alerted", False)

        if is_breached and not was_alerted:
            self.state.set("threshold_alerted", True)
            event = self._record_event(record)
            event["message"] = (
                f"{self.condition_field} is {current} "
                f"({self.condition_op} {threshold})"
            )
            logger.info("%s: threshold breached — %s", self.name, event["message"])
            return [event]

        if not is_breached and was_alerted:
            # Condition cleared — reset for next breach
            self.state.set("threshold_alerted", False)
            logger.info("%s: threshold cleared — %s recovered to %s", self.name, self.condition_field, current)

        return []

    # ── Condition: no_data ────────────────────────────────────────────────────

    def _detect_no_data(self) -> list[dict[str, Any]]:
        """Alert when no record has arrived within the lookback window.

        Returns:
            List with one event if no data found, else empty.
        """
        window_minutes = int(self.condition_extra.get("window_minutes", 60))
        since = (
            datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        ).isoformat()

        filter_expr = f'created >= "{since}"'
        records = self._fetch(filter_expr=filter_expr, sort="-created", per_page=1)

        was_alerted = self.state.get(_STATE_NO_DATA_ALERTED, False)

        if not records and not was_alerted:
            self.state.set(_STATE_NO_DATA_ALERTED, True)
            event = {
                "message": (
                    f"No data received in '{self.collection_name}' "
                    f"for the last {window_minutes} minutes."
                ),
                "data": {
                    "collection":     self.collection_name,
                    "window_minutes": window_minutes,
                },
            }
            logger.info("%s: no data alert fired", self.name)
            return [event]

        if records and was_alerted:
            self.state.set(_STATE_NO_DATA_ALERTED, False)
            logger.info("%s: data received — no_data alert cleared", self.name)

        return []

    # ── Condition: change ─────────────────────────────────────────────────────

    def _detect_change(self) -> list[dict[str, Any]]:
        """Alert when condition_field changes value since last run.

        Returns:
            List with one event if value changed, else empty.
        """
        records = self._fetch(sort="-created", per_page=1)
        if not records:
            return []

        record = records[0]
        current_value = str(record.get(self.condition_field, ""))
        prev_value = self.state.get(_STATE_PREV_VALUE)

        if prev_value is None:
            # First run — store baseline value, no alert
            self.state.set(_STATE_PREV_VALUE, current_value)
            logger.info("%s: change baseline set to '%s'", self.name, current_value)
            return []

        if current_value != str(prev_value):
            self.state.set(_STATE_PREV_VALUE, current_value)
            event = self._record_event(record)
            event["message"] = (
                f"{self.condition_field} changed: "
                f"'{prev_value}' → '{current_value}'"
            )
            logger.info("%s: change detected — %s", self.name, event["message"])
            return [event]

        return []

    # ── Condition: count ──────────────────────────────────────────────────────

    def _detect_count(self) -> list[dict[str, Any]]:
        """Alert when matching records in the window exceed count_limit.

        Returns:
            List with one event if count exceeded, else empty.
        """
        window_minutes = int(self.condition_extra.get("window_minutes", 60))
        count_limit = int(self.condition_extra.get("count_limit", 1))

        since = (
            datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        ).isoformat()

        filter_expr = self._build_filter(since=since)
        records = self._fetch(filter_expr=filter_expr, per_page=500)
        count = len(records)

        was_alerted = self.state.get("count_alerted", False)

        if count > count_limit and not was_alerted:
            self.state.set("count_alerted", True)
            event = {
                "message": (
                    f"{count} records match the condition in the last "
                    f"{window_minutes} minutes (limit: {count_limit})."
                ),
                "data": {
                    "count":          count,
                    "count_limit":    count_limit,
                    "window_minutes": window_minutes,
                    "collection":     self.collection_name,
                },
            }
            logger.info("%s: count alert — %d > %d", self.name, count, count_limit)
            return [event]

        if count <= count_limit and was_alerted:
            self.state.set("count_alerted", False)
            logger.info("%s: count cleared — %d <= %d", self.name, count, count_limit)

        return []

    # ── Condition: field_update ───────────────────────────────────────────────

    def _detect_field_update(self) -> list[dict[str, Any]]:
        """Alert when existing records match the condition (field updated).

        Unlike ``new_record``, this fires for **any** record (old or new)
        whose ``condition_field`` currently satisfies the condition — even
        if the record was created long ago and the field was just updated.

        Tracks alerted record IDs in state so each record fires only once.
        When a previously alerted record no longer matches (e.g. field reset),
        its ID is removed from state so it can fire again if it re-matches.

        Returns:
            List of event dicts for newly matching records.
        """
        filter_expr = _field_filter(
            self.condition_field, self.condition_op, self.condition_value
        )
        matching_records = self._fetch(filter_expr=filter_expr, per_page=500)

        # IDs currently matching the condition
        current_ids: set[str] = {r["id"] for r in matching_records}

        # IDs we have already alerted about (persisted in state)
        alerted_ids: list[str] = self.state.get(_STATE_ALERTED_IDS, [])
        alerted_set: set[str] = set(alerted_ids)

        # New matches = currently matching but not yet alerted
        new_ids = current_ids - alerted_set

        # Cleared matches = previously alerted but no longer matching → remove
        still_alerted = alerted_set & current_ids
        updated_alerted = list(still_alerted | new_ids)
        self.state.set(_STATE_ALERTED_IDS, updated_alerted)

        if not new_ids:
            return []

        # Build events only for newly matching records
        new_records = [r for r in matching_records if r["id"] in new_ids]
        events = [self._record_event(r) for r in new_records]
        for event, record in zip(events, new_records):
            field_value = record.get(self.condition_field, "")
            event["message"] = (
                f"'{self.collection_name}' record updated: "
                f"{self.condition_field}={field_value} (id={record['id']})"
            )
        logger.info("%s: field_update — %d new match(es)", self.name, len(events))
        return events

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch(
        self,
        filter_expr: str = "",
        sort: str = "created",
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch records from the configured collection.

        Args:
            filter_expr: PocketBase/SQL filter string.
            sort:        Sort expression.
            per_page:    Maximum records to return.

        Returns:
            List of record dicts.

        Raises:
            DataSourceError: If the fetch fails.
        """
        query: dict[str, Any] = {
            "collection": self.collection_name,
            "sort":       sort,
            "per_page":   per_page,
        }
        if filter_expr:
            query["filter"] = filter_expr
        return self.datasource.fetch(query)

    def _build_filter(self, since: str | None = None) -> str:
        """Build the filter expression for the condition.

        If ``condition_field`` and ``condition_value`` are set, the filter
        includes the field comparison. A ``since`` timestamp is always
        appended for new_record and count conditions.

        Args:
            since: ISO-8601 lower-bound timestamp, or None.

        Returns:
            Filter expression string, or empty string if no conditions.
        """
        parts: list[str] = []

        if self.condition_field and self.condition_value:
            parts.append(_field_filter(
                self.condition_field,
                self.condition_op,
                self.condition_value,
            ))

        if since:
            parts.append(f'created > "{since}"')

        return " && ".join(parts)

    def _record_event(self, record: dict[str, Any]) -> dict[str, Any]:
        """Build a standard alert event from a record.

        Args:
            record: Raw record dict from the data source.

        Returns:
            Event dict with ``message`` and ``data`` keys.
        """
        field_value = record.get(self.condition_field, "")
        return {
            "message": (
                f"New record in '{self.collection_name}': "
                f"{self.condition_field}={field_value}"
                if self.condition_field
                else f"New record in '{self.collection_name}'"
            ),
            "data": record,
        }


# ── Comparison helpers ────────────────────────────────────────────────────────


def _compare(value: float, op: str, threshold: float) -> bool:
    """Compare a numeric value against a threshold using an operator string.

    Args:
        value:     Left-hand side of the comparison.
        op:        Operator string (lt, gt, lte, gte, eq, ne).
        threshold: Right-hand side of the comparison.

    Returns:
        ``True`` if the comparison holds, else ``False``.
    """
    ops = {
        "lt":  value < threshold,
        "gt":  value > threshold,
        "lte": value <= threshold,
        "gte": value >= threshold,
        "eq":  value == threshold,
        "ne":  value != threshold,
    }
    return ops.get(op, False)


def _normalise_bool(value: str) -> str | None:
    """Normalise any truthy/falsy string to PocketBase ``true``/``false``.

    Accepts: true/True/TRUE/1/yes/on → "true"
             false/False/FALSE/0/no/off → "false"

    Returns:
        ``"true"``, ``"false"``, or ``None`` if the value is not boolean.
    """
    if value.lower() in ("true", "1", "yes", "on"):
        return "true"
    if value.lower() in ("false", "0", "no", "off"):
        return "false"
    return None


def _field_filter(field: str, op: str, value: str) -> str:
    """Build a PocketBase-compatible filter expression for one field.

    Handles three value categories automatically:
    - Boolean  → no quotes, lowercase true/false (isScheduled = true)
    - Numeric  → no quotes               (oee < 60)
    - Text     → double-quoted           (jobStatus = "Released")

    Args:
        field:  Field name.
        op:     Operator string (eq/ne/lt/gt/lte/gte/contains).
        value:  Value to compare against (as string from condition_value).

    Returns:
        PocketBase filter expression string.
    """
    pb_op_map = {
        "eq":       "=",
        "ne":       "!=",
        "lt":       "<",
        "gt":       ">",
        "lte":      "<=",
        "gte":      ">=",
        "contains": "~",
    }
    pb_op = pb_op_map.get(op, "=")

    # Boolean — normalise any variant to true/false (no quotes)
    bool_val = _normalise_bool(value)
    if bool_val is not None:
        return f"{field} {pb_op} {bool_val}"

    # Numeric — no quotes
    try:
        float(value)
        return f"{field} {pb_op} {value}"
    except ValueError:
        pass

    # Text — double-quoted
    return f'{field} {pb_op} "{value}"'
