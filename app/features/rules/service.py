"""
Business logic for the rules feature.

Single responsibility: validate inputs, coordinate repo calls, and
trigger scheduler reloads. No FastAPI imports, no DB queries.
All PocketBaseError exceptions propagate to the router/handler layer.
"""

import logging

from app.core.exceptions import RuleConfigError, RuleNotFoundError
from app.engine import scheduler as sched
from app.engine.registry import RULE_REGISTRY
from app.features.rules import repo
from app.features.rules.schema import RuleCreate, RuleParamsUpdate, RuleUpdate

logger = logging.getLogger(__name__)


def list_rules() -> list[dict]:
    """Return all registered rules.

    Returns:
        List of rule domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return repo.get_all()


def get_rule(rule_id: str) -> dict:
    """Fetch a single rule, raising if not found.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        Rule domain dict.

    Raises:
        RuleNotFoundError: If no rule with ``rule_id`` exists.
        PocketBaseError:   On network failure.
    """
    rule = repo.get_by_id(rule_id)
    if not rule:
        raise RuleNotFoundError(rule_id)
    return rule


def create_rule(payload: RuleCreate) -> dict:
    """Validate and create a new rule, then reload the scheduler.

    Args:
        payload: Validated ``RuleCreate`` request body.

    Returns:
        Created rule domain dict.

    Raises:
        RuleConfigError: If the rule class is not in the registry.
        PocketBaseError: On network or HTTP failure.
    """
    _validate_rule_class(payload.rule_class)
    rule = repo.create(payload)
    sched.reload_rule(rule["name"])
    logger.info("Created rule '%s' (%s)", rule["name"], rule["rule_class"])
    return rule


def update_rule(rule_id: str, payload: RuleUpdate) -> dict:
    """Update a rule's schedule or description, then reload the scheduler.

    Args:
        rule_id: PocketBase record ID string.
        payload: Fields to overwrite.

    Returns:
        Updated rule domain dict.

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    rule = get_rule(rule_id)
    updated = repo.update(rule, payload)
    sched.reload_rule(updated["name"])
    return updated


def update_params(rule_id: str, payload: RuleParamsUpdate) -> dict:
    """Merge new params into the rule's params_json, then reload.

    Args:
        rule_id: PocketBase record ID string.
        payload: New parameter values to merge.

    Returns:
        Updated rule domain dict.

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    rule = get_rule(rule_id)
    updated = repo.update_params(rule, payload)
    sched.reload_rule(updated["name"])
    logger.info("Updated params for rule '%s'", updated["name"])
    return updated


def toggle_rule(rule_id: str, enabled: bool) -> dict:
    """Enable or disable a rule, then reload the scheduler.

    Args:
        rule_id: PocketBase record ID string.
        enabled: New enabled state.

    Returns:
        Updated rule domain dict.

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    rule = get_rule(rule_id)
    updated = repo.toggle(rule, enabled)
    sched.reload_rule(updated["name"])
    return updated


def delete_rule(rule_id: str) -> None:
    """Delete a rule and remove its scheduled job.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        None

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    rule = get_rule(rule_id)
    sched._remove_job(rule["name"])
    repo.delete(rule)
    logger.info("Deleted rule '%s'", rule["name"])


def run_rule_now(rule_id: str) -> None:
    """Trigger a rule to execute immediately outside its schedule.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        None

    Raises:
        RuleNotFoundError: If the rule does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    import datetime
    rule = get_rule(rule_id)
    job = sched.get_scheduler().get_job(rule["name"])
    if job:
        job.modify(next_run_time=datetime.datetime.now())
        logger.info("Triggered immediate run for rule '%s'", rule["name"])


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
