"""
Business logic for the logs feature.

Coordinates repo calls and applies pagination. No FastAPI imports,
no direct DB queries, no side effects.
"""

import logging

from sqlalchemy.orm import Session

from app.db.models import ExecutionLog
from app.features.logs import repo
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)


def list_all_logs(
    db: Session, page: int, size: int
) -> dict:
    """Return a paginated list of all execution logs.

    Args:
        db:   Active database session.
        page: Page number (1-based).
        size: Items per page.

    Returns:
        Paginated result dict with ``items``, ``page``, ``size``, ``total``.
    """
    logs = repo.get_all(db)
    return paginate(logs, page, size)


def list_logs_for_rule(
    db: Session, rule_name: str, page: int, size: int
) -> dict:
    """Return a paginated list of execution logs for a specific rule.

    Args:
        db:        Active database session.
        rule_name: Name of the rule.
        page:      Page number (1-based).
        size:      Items per page.

    Returns:
        Paginated result dict with ``items``, ``page``, ``size``, ``total``.
    """
    logs = repo.get_for_rule(db, rule_name)
    return paginate(logs, page, size)
