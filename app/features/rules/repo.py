"""
Data access functions for the rules feature.

Single responsibility: translate RuleCreate/RuleUpdate schemas into
PocketBase repository calls. No business logic here.
All PocketBaseError exceptions propagate to the service layer.
"""

import logging

from app.db import pb_repositories as pb
from app.features.rules.schema import RuleCreate, RuleParamsUpdate, RuleUpdate

logger = logging.getLogger(__name__)


def get_all() -> list[dict]:
    """Return all rules from PocketBase.

    Returns:
        List of rule domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.get_all_rules()


def get_by_id(rule_id: str) -> dict | None:
    """Fetch a rule by its PocketBase record ID.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        Rule domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure.
    """
    return pb.get_rule_by_id(rule_id)


def get_by_name(name: str) -> dict | None:
    """Fetch a rule by its unique name.

    Args:
        name: Unique rule name string.

    Returns:
        Rule domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure.
    """
    return pb.get_rule_by_name(name)


def create(payload: RuleCreate) -> dict:
    """Create a new rule in PocketBase.

    Args:
        payload: Validated ``RuleCreate`` schema instance.

    Returns:
        Created rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    data = {
        "name":             payload.name,
        "schedule":         payload.schedule,
        "description":      payload.description or "",
        "enabled":          True,
        # Structured condition fields
        "datasource_id":    payload.datasource_id or "",
        "collection_name":  payload.collection_name or "",
        "condition_type":   payload.condition_type or "",
        "condition_field":  payload.condition_field or "",
        "condition_op":     payload.condition_op or "eq",
        "condition_value":  payload.condition_value or "",
        "condition_extra":  payload.condition_extra or {},
        # Legacy class-based fields
        "rule_class":       payload.rule_class or "",
        "params_json":      payload.params or {},
    }
    return pb.create_rule(data)


def update(rule: dict, payload: RuleUpdate) -> dict:
    """Update schedule and/or description on an existing rule.

    Args:
        rule:    Existing rule domain dict (must have ``id``).
        payload: Validated ``RuleUpdate`` schema instance.

    Returns:
        Updated rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    data = {}
    if payload.schedule is not None:
        data["schedule"] = payload.schedule
    if payload.description is not None:
        data["description"] = payload.description
    if payload.collection_name is not None:
        data["collection_name"] = payload.collection_name
    if payload.condition_type is not None:
        data["condition_type"] = payload.condition_type
    if payload.condition_field is not None:
        data["condition_field"] = payload.condition_field
    if payload.condition_op is not None:
        data["condition_op"] = payload.condition_op
    if payload.condition_value is not None:
        data["condition_value"] = payload.condition_value
    if payload.condition_extra is not None:
        data["condition_extra"] = payload.condition_extra
    return pb.update_rule(rule["id"], data)


def update_params(rule: dict, payload: RuleParamsUpdate) -> dict:
    """Merge new params into the rule's ``params_json`` field.

    Args:
        rule:    Existing rule domain dict (must have ``id``, ``params_json``).
        payload: Validated ``RuleParamsUpdate`` schema instance.

    Returns:
        Updated rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    existing = rule.get("params_json") or {}
    existing.update(payload.params or {})
    return pb.update_rule(rule["id"], {"params_json": existing})


def toggle(rule: dict, enabled: bool) -> dict:
    """Enable or disable a rule.

    Args:
        rule:    Existing rule domain dict (must have ``id``).
        enabled: ``True`` to enable, ``False`` to disable.

    Returns:
        Updated rule domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.update_rule(rule["id"], {"enabled": enabled})


def delete(rule: dict) -> None:
    """Delete a rule and its notifier configs from PocketBase.

    Args:
        rule: Existing rule domain dict (must have ``id``).

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    pb.delete_rule(rule["id"])
