"""
Abstract base class for all data source connectors.

Every new data source must extend ``BaseDataSource`` and implement
``connect()`` and ``fetch()``. The engine treats all data sources
identically through this interface.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseDataSource(ABC):
    """Contract that every data source connector must satisfy.

    A data source is responsible for:
    - Establishing a connection to an external database or API.
    - Fetching records based on a query dict passed by a rule.

    It does not know about rules, notifiers, or the scheduler.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the external data source.

        Should store any session/token/client on ``self`` for reuse
        in subsequent ``fetch()`` calls.

        Raises:
            DataSourceError: If the connection cannot be established.

        Returns:
            None
        """

    @abstractmethod
    def fetch(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch records from the data source matching the query.

        Args:
            query: Data source-specific query parameters as a dict.
                   Each connector documents its own supported keys.

        Returns:
            List of record dicts. Empty list if no records match.

        Raises:
            DataSourceError: If the fetch operation fails.
        """
