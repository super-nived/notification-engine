"""
Data access functions for the logs feature.

Thin wrappers that delegate to ``app.db.repositories``. No business
logic — only query composition specific to execution logs.
"""

from sqlalchemy.orm import Session

from app.db import repositories as base_repo
from app.db.models import ExecutionLog


def get_for_rule(db: Session, rule_name: str) -> list[ExecutionLog]:
    """Return all execution logs for a specific rule.

    Args:
        db:        Active database session.
        rule_name: Name of the rule to filter by.

    Returns:
        List of ``ExecutionLog`` instances ordered by ``started_at`` desc.
    """
    return base_repo.get_logs_for_rule(db, rule_name)


def get_all(db: Session) -> list[ExecutionLog]:
    """Return all execution logs across all rules.

    Args:
        db: Active database session.

    Returns:
        List of ``ExecutionLog`` instances ordered by ``run_at`` desc.
    """
    return base_repo.get_all_logs(db)
