"""
Business logic for the notifier_config feature.

Single responsibility: validate inputs, coordinate repo calls, and
trigger scheduler reloads. No FastAPI imports, no DB queries.
All PocketBaseError exceptions propagate to the router/handler layer.
"""

import logging

from app.core.exceptions import NotifierConfigNotFoundError, RuleNotFoundError
from app.engine import scheduler as sched
from app.engine.registry import NOTIFIER_REGISTRY
from app.features.notifier_config import repo
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigUpdate,
)
from app.features.rules import repo as rule_repo

logger = logging.getLogger(__name__)


def list_configs(rule_id: str) -> list[dict]:
    """Return all notifier configs for a rule.

    Args:
        rule_id: PocketBase record ID of the parent rule.

    Returns:
        List of notifier config domain dicts.

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    _assert_rule_exists(rule_id)
    return repo.get_all_for_rule(rule_id)


def get_config(config_id: str) -> dict:
    """Fetch a single notifier config, raising if not found.

    Args:
        config_id: PocketBase record ID string.

    Returns:
        Notifier config domain dict.

    Raises:
        NotifierConfigNotFoundError: If no config with ``config_id`` exists.
        PocketBaseError:             On network failure.
    """
    config = repo.get_by_id(config_id)
    if not config:
        raise NotifierConfigNotFoundError(config_id)
    return config


def create_config(payload: NotifierConfigCreate) -> dict:
    """Validate and create a new notifier config, then reload the scheduler.

    Args:
        payload: Validated ``NotifierConfigCreate`` request body.

    Returns:
        Created notifier config domain dict.

    Raises:
        RuleNotFoundError: If the target rule does not exist.
        RuleConfigError:   If the notifier type is not in the registry.
        PocketBaseError:   On network or HTTP failure.
    """
    _assert_rule_exists(str(payload.rule_id))
    _validate_notifier_type(payload.notifier_type)
    config = repo.create(payload)
    rule = rule_repo.get_by_id(str(payload.rule_id))
    if rule:
        sched.reload_rule(rule["name"])
    logger.info(
        "Created notifier config '%s' for rule_id=%s",
        payload.notifier_type,
        payload.rule_id,
    )
    return config


def update_config(config_id: str, payload: NotifierConfigUpdate) -> dict:
    """Update a notifier config's settings, then reload the scheduler.

    Args:
        config_id: PocketBase record ID string.
        payload:   Fields to overwrite.

    Returns:
        Updated notifier config domain dict.

    Raises:
        NotifierConfigNotFoundError: If the config does not exist.
        PocketBaseError:             On network or HTTP failure.
    """
    config = get_config(config_id)
    updated = repo.update(config, payload)
    rule = rule_repo.get_by_id(updated["rule_id"])
    if rule:
        sched.reload_rule(rule["name"])
    return updated


def delete_config(config_id: str) -> None:
    """Delete a notifier config and reload the scheduler.

    Args:
        config_id: PocketBase record ID string.

    Returns:
        None

    Raises:
        NotifierConfigNotFoundError: If the config does not exist.
        PocketBaseError:             On network or HTTP failure.
    """
    config = get_config(config_id)
    rule = rule_repo.get_by_id(config["rule_id"])
    repo.delete(config)
    if rule:
        sched.reload_rule(rule["name"])
    logger.info("Deleted notifier config id=%s", config_id)


def _assert_rule_exists(rule_id: str) -> None:
    """Raise if a rule with ``rule_id`` does not exist in PocketBase.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        None

    Raises:
        RuleNotFoundError: If no matching rule is found.
        PocketBaseError:   On network failure.
    """
    if not rule_repo.get_by_id(rule_id):
        raise RuleNotFoundError(rule_id)


def _validate_notifier_type(notifier_type: str) -> None:
    """Check that a notifier type exists in the registry.

    Args:
        notifier_type: Registry key string to validate.

    Returns:
        None

    Raises:
        RuleConfigError: If the type is not registered.
    """
    if notifier_type not in NOTIFIER_REGISTRY:
        from app.core.exceptions import RuleConfigError
        raise RuleConfigError(
            f"Notifier type '{notifier_type}' not found in registry. "
            f"Available: {list(NOTIFIER_REGISTRY.keys())}"
        )
