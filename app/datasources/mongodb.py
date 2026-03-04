"""
MongoDB data source connector.

Connects to a MongoDB instance via pymongo and fetches documents
from a collection. Install ``pymongo`` to use this connector.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)


class MongoDataSource(BaseDataSource):
    """Fetches documents from a MongoDB collection via pymongo.

    Args:
        uri:      MongoDB connection URI, e.g. ``mongodb://localhost:27017``.
        database: Name of the MongoDB database to connect to.
    """

    def __init__(self, uri: str, database: str) -> None:
        self.uri = uri
        self.database = database
        self._client = None
        self._db = None

    def connect(self) -> None:
        """Establish a pymongo client connection and ping the server.

        Raises:
            DataSourceError: If the connection or ping fails.

        Returns:
            None
        """
        try:
            from pymongo import MongoClient
            self._client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            self._client.admin.command("ping")
            self._db = self._client[self.database]
        except Exception as exc:
            raise DataSourceError(
                "mongodb", f"Connection failed: {exc}"
            ) from exc

        logger.info("MongoDB connected to database '%s'", self.database)

    def fetch(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch documents from a MongoDB collection.

        Supported ``query`` keys:
            collection (str):   Required. MongoDB collection name.
            filter     (dict):  Optional. pymongo filter dict.
            sort       (list):  Optional. List of (field, direction) tuples.
            limit      (int):   Optional. Maximum documents to return.

        Args:
            query: Dict with the keys described above.

        Returns:
            List of document dicts with ``_id`` field removed.

        Raises:
            DataSourceError: If the fetch fails.
        """
        if not self._db:
            self.connect()

        try:
            collection = self._db[query["collection"]]
            cursor = collection.find(query.get("filter", {}))
            cursor = self._apply_sort(cursor, query)
            cursor = self._apply_limit(cursor, query)
            return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        except Exception as exc:
            raise DataSourceError(
                "mongodb", f"Fetch failed: {exc}"
            ) from exc

    def _apply_sort(self, cursor: Any, query: dict[str, Any]) -> Any:
        """Apply sort to a pymongo cursor if specified in the query.

        Args:
            cursor: Active pymongo cursor.
            query:  Rule query dict possibly containing ``sort``.

        Returns:
            Cursor with sort applied, or unchanged cursor.
        """
        if "sort" in query:
            return cursor.sort(query["sort"])
        return cursor

    def _apply_limit(self, cursor: Any, query: dict[str, Any]) -> Any:
        """Apply limit to a pymongo cursor if specified in the query.

        Args:
            cursor: Active pymongo cursor.
            query:  Rule query dict possibly containing ``limit``.

        Returns:
            Cursor with limit applied, or unchanged cursor.
        """
        if "limit" in query:
            return cursor.limit(query["limit"])
        return cursor

    def disconnect(self) -> None:
        """Close the pymongo client connection.

        Returns:
            None
        """
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")
