"""
Rule runner — executes a single rule and persists the result.

Single responsibility: call rule.run(), build the log payload, and
write it to PocketBase. Isolated from the scheduler so each concern
stays in its own module.
All DB write failures are caught and logged so they never silence a
rule's own output.
"""

import logging

from app.db import pb_repositories as pb
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)


def run_rule(rule: BaseRule) -> None:
    """Execute a rule and write the result to the execution log.

    Calls ``rule.run()``, persists the log to PocketBase, and updates
    the rule's ``last_run_at`` / ``last_status`` fields.

    Args:
        rule: Instantiated ``BaseRule`` subclass to execute.

    Returns:
        None
    """
    result = rule.run()
    _persist_result(rule.name, result)


def _persist_result(rule_name: str, result: dict) -> None:
    """Write execution result to PocketBase.

    Args:
        rule_name: Name of the rule that was executed.
        result:    Result dict returned by ``BaseRule.run()``.

    Returns:
        None
    """
    try:
        log_data = {
            "rule_name": rule_name,
            "started_at": result["started_at"],
            "finished_at": result.get("finished_at", result["started_at"]),
            "status": result["status"],
            "events_count": result.get("events_count", 0),
            "error": result.get("error"),
        }
        pb.create_execution_log(log_data)
        pb.update_rule_last_run(rule_name, result["status"])
    except Exception as exc:
        logger.error(
            "Failed to persist execution log for rule '%s': %s",
            rule_name,
            exc,
        )
