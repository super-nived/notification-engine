"""
Business logic for the notifier_config feature.

Validates inputs, coordinates repo calls, and triggers scheduler
reloads after config changes. No FastAPI imports, no direct DB queries.
"""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import NotifierConfigNotFoundError, RuleNotFoundError
from app.db.models import NotifierConfigModel
from app.engine import scheduler as sched
from app.engine.registry import NOTIFIER_REGISTRY
from app.features.notifier_config import repo
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigUpdate,
)
from app.features.rules import repo as rule_repo

logger = logging.getLogger(__name__)


def list_configs(db: Session, rule_id: int) -> list[NotifierConfigModel]:
    """Return all notifier configs for a rule.

    Args:
        db:      Active database session.
        rule_id: Primary key of the parent rule.

    Returns:
        List of ``NotifierConfigModel`` instances.

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    _assert_rule_exists(db, rule_id)
    return repo.get_all_for_rule(db, rule_id)


def get_config(db: Session, config_id: int) -> NotifierConfigModel:
    """Fetch a single notifier config, raising if not found.

    Args:
        db:        Active database session.
        config_id: Primary key of the config.

    Returns:
        ``NotifierConfigModel`` instance.

    Raises:
        NotifierConfigNotFoundError: If no config with ``config_id`` exists.
    """
    config = repo.get_by_id(db, config_id)
    if not config:
        raise NotifierConfigNotFoundError(config_id)
    return config


def create_config(
    db: Session, payload: NotifierConfigCreate
) -> NotifierConfigModel:
    """Validate and create a new notifier config, then reload the scheduler.

    Args:
        db:      Active database session.
        payload: Validated ``NotifierConfigCreate`` request body.

    Returns:
        Saved ``NotifierConfigModel`` with auto-generated ``id``.

    Raises:
        RuleNotFoundError: If the target rule does not exist.
        ValueError: If the notifier type is not in the registry.
    """
    _assert_rule_exists(db, payload.rule_id)
    _validate_notifier_type(payload.notifier_type)
    config = repo.create(db, payload)
    rule = rule_repo.get_by_id(db, payload.rule_id)
    if rule:
        sched.reload_rule(rule.name)
    logger.info(
        "Created notifier config '%s' for rule_id=%d",
        payload.notifier_type,
        payload.rule_id,
    )
    return config


def update_config(
    db: Session, config_id: int, payload: NotifierConfigUpdate
) -> NotifierConfigModel:
    """Update a notifier config's settings, then reload the scheduler.

    Args:
        db:        Active database session.
        config_id: Primary key of the config to update.
        payload:   Fields to overwrite.

    Returns:
        Updated ``NotifierConfigModel``.

    Raises:
        NotifierConfigNotFoundError: If the config does not exist.
    """
    config = get_config(db, config_id)
    updated = repo.update(db, config, payload)
    rule = rule_repo.get_by_id(db, updated.rule_id)
    if rule:
        sched.reload_rule(rule.name)
    return updated


def delete_config(db: Session, config_id: int) -> None:
    """Delete a notifier config and reload the scheduler.

    Args:
        db:        Active database session.
        config_id: Primary key of the config to delete.

    Returns:
        None

    Raises:
        NotifierConfigNotFoundError: If the config does not exist.
    """
    config = get_config(db, config_id)
    rule = rule_repo.get_by_id(db, config.rule_id)
    repo.delete(db, config)
    if rule:
        sched.reload_rule(rule.name)
    logger.info("Deleted notifier config id=%d", config_id)


def _assert_rule_exists(db: Session, rule_id: int) -> None:
    """Raise if a rule with ``rule_id`` does not exist.

    Args:
        db:      Active database session.
        rule_id: Primary key to check.

    Returns:
        None

    Raises:
        RuleNotFoundError: If no matching rule is found.
    """
    if not rule_repo.get_by_id(db, rule_id):
        raise RuleNotFoundError(rule_id)


def _validate_notifier_type(notifier_type: str) -> None:
    """Check that a notifier type exists in the registry.

    Args:
        notifier_type: Registry key string to validate.

    Returns:
        None

    Raises:
        ValueError: If the type is not registered.
    """
    if notifier_type not in NOTIFIER_REGISTRY:
        raise ValueError(
            f"Notifier type '{notifier_type}' not found in registry. "
            f"Available: {list(NOTIFIER_REGISTRY.keys())}"
        )
