"""
Abstract base class for all data source connectors.

Every new data source must extend ``BaseDataSource`` and implement all
abstract methods. The engine and the API treat all data sources
identically through this interface.

Implementing ``list_collections``, ``list_fields``, and ``test_connection``
enables the dashboard's data-source picker — users browse their actual
schema instead of typing collection names by hand.
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseDataSource(ABC):
    """Contract that every data source connector must satisfy.

    A data source is responsible for:
    - Testing its own connection.
    - Reporting which collections / tables are available.
    - Reporting which fields each collection contains.
    - Fetching records based on a query dict passed by the rule engine.

    It does not know about rules, notifiers, or the scheduler.
    """

    @abstractmethod
    def test_connection(self) -> bool:
        """Verify that the data source is reachable and credentials work.

        Returns:
            ``True`` if the connection succeeds.

        Raises:
            DataSourceError: If the connection attempt fails.
        """

    @abstractmethod
    def list_collections(self) -> list[str]:
        """Return a list of all available collection / table names.

        Returns:
            Sorted list of collection name strings.

        Raises:
            DataSourceError: If the request fails.
        """

    @abstractmethod
    def list_fields(self, collection: str) -> list[dict[str, str]]:
        """Return the fields of a specific collection.

        Each dict in the returned list contains at minimum:
            ``name`` (str) — field name.
            ``type`` (str) — normalised type string, one of:
                ``text``, ``number``, ``bool``, ``date``, ``json``.

        Args:
            collection: Collection / table name to inspect.

        Returns:
            List of field descriptor dicts, e.g.
            ``[{"name": "isScheduled", "type": "bool"}, ...]``.

        Raises:
            DataSourceError: If the request fails.
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
