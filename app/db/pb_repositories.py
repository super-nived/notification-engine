"""
PocketBase repository layer.

Single responsibility: translate between the application's domain
objects (plain dicts / dataclasses) and PocketBase REST records.

No business logic. No HTTP calls — those are in ``pb_client``.
All PocketBaseError exceptions propagate up to the service layer.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.db.pb_client import (
    PocketBaseError,
    pb_create,
    pb_delete,
    pb_get,
    pb_list,
    pb_update,
)

logger = logging.getLogger(__name__)

# ── Collection names ───────────────────────────────────────────────────────────
RULES_COL = "ASWNDUBAI_rules"
NOTIFIERS_COL = "ASWNDUBAI_notifier_configs"
LOGS_COL = "ASWNDUBAI_execution_logs"


# ── Rule helpers ───────────────────────────────────────────────────────────────


def _rule_to_domain(rec: dict[str, Any]) -> dict[str, Any]:
    """Map a PocketBase rules record to a domain dict.

    Args:
        rec: Raw PocketBase record dict.

    Returns:
        Domain dict with normalized field names.
    """
    return {
        "id": rec["id"],
        "name": rec.get("name", ""),
        "rule_class": rec.get("rule_class", ""),
        "schedule": rec.get("schedule", ""),
        "description": rec.get("description", ""),
        "enabled": rec.get("enabled", True),
        "params_json": rec.get("params_json") or {},
        "created_at": rec.get("created", ""),
        "last_run_at": rec.get("last_run_at"),
        "last_status": rec.get("last_status"),
        # state is read/written by RuleStateStore — not exposed in domain dict
        # scheduler needs notifiers list — fetched separately when needed
        "notifiers": [],
    }


# ── Rules CRUD ─────────────────────────────────────────────────────────────────


def get_all_rules() -> list[dict[str, Any]]:
    """Return all rules from PocketBase.

    Returns:
        List of rule domain dicts ordered by creation date.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(RULES_COL, sort="created")
    return [_rule_to_domain(r) for r in records]


def get_enabled_rules() -> list[dict[str, Any]]:
    """Return only enabled rules.

    Returns:
        List of enabled rule domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(RULES_COL, filter_expr="enabled=true", sort="created")
    return [_rule_to_domain(r) for r in records]


def get_rule_by_id(rule_id: str) -> dict[str, Any] | None:
    """Fetch a single rule by PocketBase record ID.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        Rule domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure (404 returns None).
    """
    try:
        rec = pb_get(RULES_COL, rule_id)
        return _rule_to_domain(rec)
    except PocketBaseError as exc:
        if "404" in exc.detail:
            return None
        raise


def get_rule_by_name(name: str) -> dict[str, Any] | None:
    """Fetch a single rule by its unique name.

    Args:
        name: Unique rule name string.

    Returns:
        Rule domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure.
    """
    records = pb_list(RULES_COL, filter_expr=f'name="{name}"')
    if not records:
        return None
    return _rule_to_domain(records[0])


def create_rule(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new rule in PocketBase.

    Args:
        data: Dict with ``name``, ``rule_class``, ``schedule``,
              ``description``, ``enabled``, ``params_json``.

    Returns:
        Created rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rec = pb_create(RULES_COL, data)
    logger.info("Created rule '%s' in PocketBase (id=%s)", data.get("name"), rec["id"])
    return _rule_to_domain(rec)


def update_rule(rule_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update fields on an existing rule.

    Args:
        rule_id: PocketBase record ID.
        data:    Fields to update.

    Returns:
        Updated rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rec = pb_update(RULES_COL, rule_id, data)
    return _rule_to_domain(rec)


def update_rule_last_run(rule_name: str, status: str) -> None:
    """Record the latest run timestamp and status on a rule.

    Args:
        rule_name: Unique name of the rule.
        status:    Run outcome, e.g. ``ok``, ``error``.

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rule = get_rule_by_name(rule_name)
    if not rule:
        logger.warning("update_rule_last_run: rule '%s' not found", rule_name)
        return
    now = datetime.now(timezone.utc).isoformat()
    pb_update(RULES_COL, rule["id"], {"last_run_at": now, "last_status": status})


def get_rule_state(rule_name: str) -> dict[str, Any]:
    """Read the ``state`` JSON field for a rule.

    PocketBase returns json fields already parsed, so no manual
    deserialisation is needed.

    Args:
        rule_name: Unique rule name string.

    Returns:
        State dict. Empty dict if the rule is not found or state is unset.

    Raises:
        PocketBaseError: On network failure.
    """
    records = pb_list(RULES_COL, filter_expr=f'name="{rule_name}"')
    if not records:
        logger.warning("get_rule_state: rule '%s' not found", rule_name)
        return {}
    state = records[0].get("state")
    if not isinstance(state, dict):
        return {}
    return state


def update_rule_state(rule_name: str, state: dict[str, Any]) -> None:
    """Persist the ``state`` JSON field for a rule.

    PocketBase accepts a dict directly for json fields — no manual
    serialisation needed.

    Args:
        rule_name: Unique rule name string.
        state:     Dict to store in the json field.

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(RULES_COL, filter_expr=f'name="{rule_name}"')
    if not records:
        logger.warning("update_rule_state: rule '%s' not found", rule_name)
        return
    rule_id = records[0]["id"]
    pb_update(RULES_COL, rule_id, {"state": state})


def delete_rule(rule_id: str) -> None:
    """Delete a rule and its notifier configs from PocketBase.

    PocketBase does not auto-cascade deletes on linked collections,
    so notifier configs are deleted explicitly first.

    Args:
        rule_id: PocketBase record ID of the rule.

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    notifiers = get_notifiers_for_rule(rule_id)
    for n in notifiers:
        pb_delete(NOTIFIERS_COL, n["id"])
    pb_delete(RULES_COL, rule_id)
    logger.info("Deleted rule id=%s and %d notifier(s)", rule_id, len(notifiers))


# ── Notifier config helpers ────────────────────────────────────────────────────


def _notifier_to_domain(rec: dict[str, Any]) -> dict[str, Any]:
    """Map a PocketBase notifier_configs record to a domain dict.

    Args:
        rec: Raw PocketBase record dict.

    Returns:
        Domain dict with normalized field names.
    """
    return {
        "id": rec["id"],
        "rule_id": rec.get("rule_id", ""),
        "notifier_type": rec.get("notifier_type", ""),
        "config_json": rec.get("config_json", "{}"),
    }


# ── Notifier configs CRUD ──────────────────────────────────────────────────────


def get_notifiers_for_rule(rule_id: str) -> list[dict[str, Any]]:
    """Return all notifier configs attached to a rule.

    Args:
        rule_id: PocketBase record ID of the parent rule.

    Returns:
        List of notifier config domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(NOTIFIERS_COL, filter_expr=f'rule_id="{rule_id}"')
    return [_notifier_to_domain(r) for r in records]


def get_notifier_by_id(config_id: str) -> dict[str, Any] | None:
    """Fetch a single notifier config by ID.

    Args:
        config_id: PocketBase record ID.

    Returns:
        Notifier config domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure (404 returns None).
    """
    try:
        rec = pb_get(NOTIFIERS_COL, config_id)
        return _notifier_to_domain(rec)
    except PocketBaseError as exc:
        if "404" in exc.detail:
            return None
        raise


def create_notifier_config(data: dict[str, Any]) -> dict[str, Any]:
    """Create a notifier config in PocketBase.

    Args:
        data: Dict with ``rule_id``, ``notifier_type``, ``config_json``.

    Returns:
        Created notifier config domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rec = pb_create(NOTIFIERS_COL, data)
    logger.info(
        "Created notifier '%s' for rule_id=%s",
        data.get("notifier_type"),
        data.get("rule_id"),
    )
    return _notifier_to_domain(rec)


def update_notifier_config(config_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Update a notifier config in PocketBase.

    Args:
        config_id: PocketBase record ID.
        data:      Fields to update.

    Returns:
        Updated notifier config domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rec = pb_update(NOTIFIERS_COL, config_id, data)
    return _notifier_to_domain(rec)


def delete_notifier_config(config_id: str) -> None:
    """Delete a notifier config by ID.

    Args:
        config_id: PocketBase record ID.

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    pb_delete(NOTIFIERS_COL, config_id)
    logger.info("Deleted notifier config id=%s", config_id)


# ── Execution log helpers ──────────────────────────────────────────────────────


def _log_to_domain(rec: dict[str, Any]) -> dict[str, Any]:
    """Map a PocketBase execution_logs record to a domain dict.

    Args:
        rec: Raw PocketBase record dict.

    Returns:
        Domain dict with normalized field names.
    """
    return {
        "id": rec["id"],
        "rule_name": rec.get("rule_name", ""),
        "started_at": rec.get("started_at", ""),
        "finished_at": rec.get("finished_at"),
        "status": rec.get("status", ""),
        "events_count": rec.get("events_count", 0),
        "error": rec.get("error"),
    }


# ── Execution logs CRUD ────────────────────────────────────────────────────────


def create_execution_log(data: dict[str, Any]) -> dict[str, Any]:
    """Persist an execution log entry to PocketBase.

    Args:
        data: Dict with ``rule_name``, ``started_at``, ``finished_at``,
              ``status``, ``events_count``, ``error``.

    Returns:
        Created execution log domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    rec = pb_create(LOGS_COL, data)
    return _log_to_domain(rec)


def get_logs_for_rule(rule_name: str, limit: int = 50) -> list[dict[str, Any]]:
    """Return recent execution logs for a specific rule.

    Args:
        rule_name: Unique rule name to filter by.
        limit:     Maximum number of records to return.

    Returns:
        List of execution log domain dicts, newest first.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(
        LOGS_COL,
        filter_expr=f'rule_name="{rule_name}"',
        sort="-started_at",
        per_page=limit,
    )
    return [_log_to_domain(r) for r in records]


def get_all_logs(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent execution logs across all rules.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of execution log domain dicts, newest first.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    records = pb_list(LOGS_COL, sort="-started_at", per_page=limit)
    return [_log_to_domain(r) for r in records]
