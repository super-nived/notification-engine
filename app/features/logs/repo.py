"""
Data access functions for the logs feature.

Single responsibility: delegate execution log queries to the
PocketBase repository layer. No business logic here.
All PocketBaseError exceptions propagate to the service layer.
"""

import logging

from app.db import pb_repositories as pb

logger = logging.getLogger(__name__)


def get_for_rule(rule_name: str) -> list[dict]:
    """Return execution logs for a specific rule, newest first.

    Args:
        rule_name: Unique name of the rule to filter by.

    Returns:
        List of execution log domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.get_logs_for_rule(rule_name)


def get_all() -> list[dict]:
    """Return all execution logs across all rules, newest first.

    Args:
        None

    Returns:
        List of execution log domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.get_all_logs()
