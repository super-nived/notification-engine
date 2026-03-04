"""
Business logic for the logs feature.

Single responsibility: coordinate repo calls and apply pagination.
No FastAPI imports, no direct DB queries, no side effects.
All PocketBaseError exceptions propagate to the router/handler layer.
"""

import logging

from app.features.logs import repo
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)


def list_all_logs(page: int, size: int) -> dict:
    """Return a paginated list of all execution logs.

    Args:
        page: Page number (1-based).
        size: Items per page.

    Returns:
        Paginated result dict with ``items``, ``page``, ``size``, ``total``.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    logs = repo.get_all()
    return paginate(logs, page, size)


def list_logs_for_rule(rule_name: str, page: int, size: int) -> dict:
    """Return a paginated list of execution logs for a specific rule.

    Args:
        rule_name: Unique name of the rule.
        page:      Page number (1-based).
        size:      Items per page.

    Returns:
        Paginated result dict with ``items``, ``page``, ``size``, ``total``.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    logs = repo.get_for_rule(rule_name)
    return paginate(logs, page, size)
