"""
Business logic for the rules feature.

Single responsibility: validate inputs, coordinate repo calls, and
trigger scheduler reloads. No FastAPI imports, no DB queries.
All PocketBaseError exceptions propagate to the router/handler layer.
"""

import logging

from app.core.exceptions import RuleConfigError, RuleNotFoundError
from app.engine import scheduler as sched
from app.engine.registry import RULE_REGISTRY  # re-exported for router
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
    # Structured rules (datasource_id set) skip class validation entirely.
    # Legacy class-based rules must have a registered rule_class.
    if not payload.datasource_id:
        _validate_rule_class(payload.rule_class)
    rule = repo.create(payload)
    sched.reload_rule(rule["name"])
    logger.info("Created rule '%s' (datasource=%s class=%s)", rule["name"], rule.get("datasource_id"), rule["rule_class"])
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


def list_rule_classes() -> list[dict]:
    """Return all registered rule classes with their metadata.

    Returns:
        List of dicts with ``class_name``, ``name``, ``description``,
        and ``params_schema`` for each registered class.
    """
    result = []
    for class_name, cls in RULE_REGISTRY.items():
        result.append({
            "class_name":   class_name,
            "name":         getattr(cls, "name", ""),
            "description":  getattr(cls, "description", ""),
            "params_schema": getattr(cls, "params_schema", []),
        })
    return result


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


def upload_rule_class(filename: str, source_code: str) -> str:
    """Validate and save an uploaded rule class file, then register it.

    Validates that the file:
    - Is syntactically valid Python.
    - Contains exactly one BaseRule subclass.
    - Has non-empty name and description class attributes.

    Args:
        filename:    Original uploaded filename (e.g. my_rule.py).
        source_code: Full Python source code string.

    Returns:
        The registered class name string.

    Raises:
        RuleConfigError: If validation fails for any reason.
    """
    import ast
    import importlib.util
    import inspect
    import sys
    import tempfile
    from pathlib import Path

    from app.engine.registry import register_rule_class
    from app.rule_definitions.base_rule import BaseRule

    # ── Syntax check ─────────────────────────────────────────────────────────
    try:
        ast.parse(source_code)
    except SyntaxError as exc:
        raise RuleConfigError(f"Syntax error in uploaded file: {exc}")

    # ── Save to rule_definitions/ ─────────────────────────────────────────────
    rules_dir = Path(__file__).parent.parent.parent / "rule_definitions"
    safe_name = Path(filename).stem.replace(" ", "_") + ".py"
    dest = rules_dir / safe_name

    try:
        dest.write_text(source_code, encoding="utf-8")
    except OSError as exc:
        raise RuleConfigError(f"Could not save rule file: {exc}")

    # ── Load and inspect the module ───────────────────────────────────────────
    try:
        spec = importlib.util.spec_from_file_location(dest.stem, dest)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception as exc:
        dest.unlink(missing_ok=True)
        raise RuleConfigError(f"Failed to import uploaded rule: {exc}")

    # ── Find BaseRule subclasses ───────────────────────────────────────────────
    found = [
        (name, cls)
        for name, cls in inspect.getmembers(module, inspect.isclass)
        if issubclass(cls, BaseRule) and cls is not BaseRule
        and cls.__module__ == module.__name__
    ]

    if not found:
        dest.unlink(missing_ok=True)
        raise RuleConfigError(
            "No BaseRule subclass found in the uploaded file. "
            "Make sure your class extends BaseRule."
        )

    if len(found) > 1:
        dest.unlink(missing_ok=True)
        raise RuleConfigError(
            f"Found {len(found)} BaseRule subclasses: {[n for n,_ in found]}. "
            "Upload one rule class per file."
        )

    class_name, cls = found[0]

    # ── Validate required class attributes ────────────────────────────────────
    if not getattr(cls, "name", "").strip():
        dest.unlink(missing_ok=True)
        raise RuleConfigError(
            f"Class '{class_name}' must define a non-empty 'name' class attribute."
        )

    if not getattr(cls, "description", "").strip():
        dest.unlink(missing_ok=True)
        raise RuleConfigError(
            f"Class '{class_name}' must define a non-empty 'description' class attribute."
        )

    register_rule_class(class_name, cls)
    logger.info("Uploaded and registered rule class '%s' from '%s'", class_name, filename)
    return class_name
