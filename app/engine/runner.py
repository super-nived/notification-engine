"""
Rule runner — executes a single rule and persists the result.

Called by the scheduler on every cron tick. Isolates execution logging
from the scheduler so each concern stays in its own module.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ExecutionLog
from app.db import repositories as repo
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)


def run_rule(rule: BaseRule, db: Session) -> None:
    """Execute a rule and write the result to the execution log.

    Calls ``rule.run()``, builds an ``ExecutionLog`` record from the
    result, updates the rule's ``last_run_at`` and ``last_status``,
    and commits both writes in one transaction.

    DB write failures are caught and logged so they never silence the
    rule's own output.

    Args:
        rule: Instantiated ``BaseRule`` subclass to execute.
        db:   Active database session for writing the execution log.

    Returns:
        None
    """
    result = rule.run()
    _persist_result(rule.name, result, db)


def _persist_result(
    rule_name: str,
    result: dict,
    db: Session,
) -> None:
    """Write execution result to the database.

    Args:
        rule_name: Name of the rule that was executed.
        result:    Result dict returned by ``BaseRule.run()``.
        db:        Active database session.

    Returns:
        None
    """
    try:
        log = _build_log(rule_name, result)
        repo.create_execution_log(db, log)
        repo.update_rule_last_run(db, rule_name, result["status"])
    except Exception as exc:
        logger.error(
            "Failed to persist execution log for rule '%s': %s",
            rule_name,
            exc,
        )


def _build_log(rule_name: str, result: dict) -> ExecutionLog:
    """Construct an ``ExecutionLog`` ORM instance from a result dict.

    Args:
        rule_name: Name of the rule that ran.
        result:    Result dict from ``BaseRule.run()``.

    Returns:
        Unsaved ``ExecutionLog`` instance ready to insert.
    """
    return ExecutionLog(
        rule_name=rule_name,
        started_at=datetime.fromisoformat(result["started_at"]),
        finished_at=datetime.fromisoformat(
            result.get("finished_at", result["started_at"])
        ),
        status=result["status"],
        events_count=result["events_count"],
        error=result.get("error"),
    )
