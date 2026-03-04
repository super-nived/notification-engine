"""
Data access functions for the notifier_config feature.

Single responsibility: translate NotifierConfig schemas into
PocketBase repository calls. No business logic here.
All PocketBaseError exceptions propagate to the service layer.
"""

import json
import logging

from app.db import pb_repositories as pb
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigUpdate,
)

logger = logging.getLogger(__name__)


def get_all_for_rule(rule_id: str) -> list[dict]:
    """Return all notifier configs attached to a rule.

    Args:
        rule_id: PocketBase record ID of the parent rule.

    Returns:
        List of notifier config domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.get_notifiers_for_rule(rule_id)


def get_by_id(config_id: str) -> dict | None:
    """Fetch a notifier config by its PocketBase record ID.

    Args:
        config_id: PocketBase record ID string.

    Returns:
        Notifier config domain dict, or ``None`` if not found.

    Raises:
        PocketBaseError: On network failure.
    """
    return pb.get_notifier_by_id(config_id)


def create(payload: NotifierConfigCreate) -> dict:
    """Create a new notifier config in PocketBase.

    Args:
        payload: Validated ``NotifierConfigCreate`` schema instance.

    Returns:
        Created notifier config domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    data = {
        "rule_id": str(payload.rule_id),
        "notifier_type": payload.notifier_type,
        "config_json": json.dumps(payload.config_json or {}),
    }
    return pb.create_notifier_config(data)


def update(config: dict, payload: NotifierConfigUpdate) -> dict:
    """Update the config_json on an existing notifier config.

    Args:
        config:  Existing notifier config domain dict (must have ``id``).
        payload: Validated ``NotifierConfigUpdate`` schema instance.

    Returns:
        Updated notifier config domain dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    data = {}
    if payload.config_json is not None:
        data["config_json"] = json.dumps(payload.config_json)
    return pb.update_notifier_config(config["id"], data)


def delete(config: dict) -> None:
    """Delete a notifier config from PocketBase.

    Args:
        config: Existing notifier config domain dict (must have ``id``).

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    pb.delete_notifier_config(config["id"])
