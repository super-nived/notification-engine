"""
Business logic for the rules feature.

Validates inputs, coordinates repo calls, and triggers scheduler
reloads after rule changes. No FastAPI imports, no direct DB queries.
"""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import RuleConfigError, RuleNotFoundError
from app.db.models import RuleModel
from app.engine.registry import RULE_REGISTRY
from app.engine import scheduler as sched
from app.features.rules import repo
from app.features.rules.schema import RuleCreate, RuleParamsUpdate, RuleUpdate

logger = logging.getLogger(__name__)


def list_rules(db: Session) -> list[RuleModel]:
    """Return all registered rules.

    Args:
        db: Active database session.

    Returns:
        List of ``RuleModel`` instances.
    """
    return repo.get_all(db)


def get_rule(db: Session, rule_id: int) -> RuleModel:
    """Fetch a single rule, raising if not found.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule.

    Returns:
        ``RuleModel`` instance.

    Raises:
        RuleNotFoundError: If no rule with ``rule_id`` exists.
    """
    rule = repo.get_by_id(db, rule_id)
    if not rule:
        raise RuleNotFoundError(rule_id)
    return rule


def create_rule(db: Session, payload: RuleCreate) -> RuleModel:
    """Validate and create a new rule, then reload the scheduler.

    Args:
        db:      Active database session.
        payload: Validated ``RuleCreate`` request body.

    Returns:
        Saved ``RuleModel`` with auto-generated id.

    Raises:
        RuleConfigError: If the rule class is not in the registry.
    """
    _validate_rule_class(payload.rule_class)
    rule = repo.create(db, payload)
    sched.reload_rule(rule.name)
    logger.info("Created rule '%s' (%s)", rule.name, rule.rule_class)
    return rule


def update_rule(db: Session, rule_id: int, payload: RuleUpdate) -> RuleModel:
    """Update a rule's schedule or description, then reload.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule to update.
        payload: Fields to overwrite.

    Returns:
        Updated ``RuleModel``.

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    rule = get_rule(db, rule_id)
    updated = repo.update(db, rule, payload)
    sched.reload_rule(updated.name)
    return updated


def update_params(
    db: Session, rule_id: int, payload: RuleParamsUpdate
) -> RuleModel:
    """Merge new user-editable parameters into the rule, then reload.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule to update.
        payload: New parameter values to merge.

    Returns:
        Updated ``RuleModel``.

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    rule = get_rule(db, rule_id)
    updated = repo.update_params(db, rule, payload)
    sched.reload_rule(updated.name)
    logger.info("Updated params for rule '%s'", updated.name)
    return updated


def toggle_rule(db: Session, rule_id: int, enabled: bool) -> RuleModel:
    """Enable or disable a rule, then reload the scheduler.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule.
        enabled: New enabled state.

    Returns:
        Updated ``RuleModel``.

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    rule = get_rule(db, rule_id)
    updated = repo.toggle(db, rule, enabled)
    sched.reload_rule(updated.name)
    return updated


def delete_rule(db: Session, rule_id: int) -> None:
    """Delete a rule and remove its scheduled job.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule to delete.

    Returns:
        None

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    rule = get_rule(db, rule_id)
    sched._remove_job(rule.name)
    repo.delete(db, rule)
    logger.info("Deleted rule '%s'", rule.name)


def run_rule_now(db: Session, rule_id: int) -> None:
    """Trigger a rule to execute immediately outside its schedule.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule to run.

    Returns:
        None

    Raises:
        RuleNotFoundError: If the rule does not exist.
    """
    rule = get_rule(db, rule_id)
    job = sched.get_scheduler().get_job(rule.name)
    if job:
        job.modify(next_run_time=__import__("datetime").datetime.now())
        logger.info("Triggered immediate run for rule '%s'", rule.name)


def _validate_rule_class(rule_class: str) -> None:
    """Check that a rule class name exists in the registry.

    Args:
        rule_class: Class name string to validate.

    Raises:
        RuleConfigError: If the class is not registered.

    Returns:
        None
    """
    if rule_class not in RULE_REGISTRY:
        raise RuleConfigError(
            f"Rule class '{rule_class}' not found in registry. "
            f"Available: {list(RULE_REGISTRY.keys())}"
        )
