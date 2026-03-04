"""
Example Rule — copy this file to create a new rule.

Steps:
1. Copy: cp example_rule.py your_rule_name.py
2. Rename the class, set ``name`` and ``description``
3. Implement ``detect()`` — return ``[]`` if nothing, events if triggered
4. Register in ``app/engine/registry.py``
5. Create via API: POST /api/v1/rules with your params
"""

import logging
from typing import Any

from app.notifiers.base import BaseNotifier
from app.rule_definitions.base_rule import BaseRule

logger = logging.getLogger(__name__)


class ExampleRule(BaseRule):
    """Template rule — replace this docstring with what your rule detects.

    Args:
        notifiers: List of notifier instances to fire on detection.
    """

    name = "example_rule"
    description = "Replace with what this rule detects."

    def __init__(self, notifiers: list[BaseNotifier], **kwargs: Any) -> None:
        super().__init__(notifiers)
        # Store any params from kwargs here, e.g.:
        # self.collection = kwargs.get("collection", "default_collection")

    def detect(self) -> list[dict[str, Any]]:
        """Detect the condition and return events.

        Returns:
            Empty list if nothing detected, or list of event dicts.

        Raises:
            DataSourceError: If data source fetch fails.
        """
        # 1. Fetch from your datasource
        # 2. Compare against state (if needed)
        # 3. Build and return events

        events: list[dict[str, Any]] = []
        return events
