"""
MongoDB data source connector.

Connects to a MongoDB instance via pymongo and fetches documents
from a collection. Install ``pymongo`` to use this connector.

Implements the full ``BaseDataSource`` interface including
``test_connection``, ``list_collections``, and ``list_fields``
(inferred from a sample document) so the dashboard can show a live
collection/field picker to users.
"""

import logging
from typing import Any

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)

# Python/BSON type names → normalised type strings
_MONGO_TYPE_MAP: dict[str, str] = {
    "str":      "text",
    "int":      "number",
    "float":    "number",
    "Decimal128": "number",
    "bool":     "bool",
    "datetime": "date",
    "dict":     "json",
    "list":     "json",
    "ObjectId": "text",
}


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

    # ── Connection ────────────────────────────────────────────────────────────

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

    def test_connection(self) -> bool:
        """Ping MongoDB to verify the connection.

        Returns:
            ``True`` if the ping succeeds.

        Raises:
            DataSourceError: If the connection fails.
        """
        self.connect()
        return True

    # ── Schema discovery ──────────────────────────────────────────────────────

    def list_collections(self) -> list[str]:
        """Return all collection names in the connected database.

        Returns:
            Sorted list of collection name strings.

        Raises:
            DataSourceError: If the request fails.
        """
        if not self._db:
            self.connect()

        try:
            return sorted(self._db.list_collection_names())
        except Exception as exc:
            raise DataSourceError(
                "mongodb", f"list_collections failed: {exc}"
            ) from exc

    def list_fields(self, collection: str) -> list[dict[str, str]]:
        """Infer fields from a sample document in the collection.

        Samples the most recently inserted document and maps the keys
        to normalised type strings based on their Python value types.
        Returns an empty list if the collection has no documents.

        Args:
            collection: MongoDB collection name.

        Returns:
            List of ``{"name": ..., "type": ...}`` dicts.

        Raises:
            DataSourceError: If the query fails.
        """
        if not self._db:
            self.connect()

        try:
            doc = self._db[collection].find_one(
                {}, sort=[("_id", -1)]
            )
        except Exception as exc:
            raise DataSourceError(
                "mongodb", f"list_fields for '{collection}' failed: {exc}"
            ) from exc

        if not doc:
            return []

        fields: list[dict[str, str]] = []
        for key, value in doc.items():
            if key == "_id":
                continue
            type_name = type(value).__name__
            fields.append({
                "name": key,
                "type": _MONGO_TYPE_MAP.get(type_name, "text"),
            })
        return fields

    # ── Data fetching ─────────────────────────────────────────────────────────

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
            col = self._db[query["collection"]]
            cursor = col.find(query.get("filter", {}))
            cursor = self._apply_sort(cursor, query)
            cursor = self._apply_limit(cursor, query)
            return [{k: v for k, v in doc.items() if k != "_id"} for doc in cursor]
        except Exception as exc:
            raise DataSourceError(
                "mongodb", f"Fetch failed: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the pymongo client connection.

        Returns:
            None
        """
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _apply_sort(self, cursor: Any, query: dict[str, Any]) -> Any:
        """Apply sort to a pymongo cursor if specified in the query."""
        if "sort" in query:
            return cursor.sort(query["sort"])
        return cursor

    def _apply_limit(self, cursor: Any, query: dict[str, Any]) -> Any:
        """Apply limit to a pymongo cursor if specified in the query."""
        if "limit" in query:
            return cursor.limit(query["limit"])
        return cursor
