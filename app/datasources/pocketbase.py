"""
PocketBase data source connector.

Authenticates as an admin user and fetches records from a PocketBase
collection via the REST API. Token is cached after the first call to
``connect()`` and reused on subsequent calls.

Implements the full ``BaseDataSource`` interface including
``test_connection``, ``list_collections``, and ``list_fields`` so the
dashboard can show a live collection/field picker to users.
"""

import logging
from typing import Any

import requests

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)

_AUTH_PATH = "/api/admins/auth-with-password"
_RECORDS_PATH = "/api/collections/{collection}/records"
_COLLECTIONS_PATH = "/api/collections"
_COLLECTION_PATH = "/api/collections/{collection}"

# PocketBase schema field types → normalised type strings
_PB_TYPE_MAP: dict[str, str] = {
    "text":     "text",
    "editor":   "text",
    "email":    "text",
    "url":      "text",
    "select":   "text",
    "relation": "text",
    "file":     "text",
    "number":   "number",
    "bool":     "bool",
    "date":     "date",
    "json":     "json",
    "autodate": "date",
}


class PocketBaseDataSource(BaseDataSource):
    """Fetches records from a PocketBase collection via REST.

    Args:
        url:            Base URL of the PocketBase instance.
        admin_email:    Admin account email for authentication.
        admin_password: Admin account password.
    """

    def __init__(
        self,
        url: str,
        admin_email: str,
        admin_password: str,
    ) -> None:
        self.url = url.rstrip("/")
        self.admin_email = admin_email
        self.admin_password = admin_password
        self._token: str | None = None

    # ── Connection ────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Authenticate with PocketBase and cache the admin token.

        Raises:
            DataSourceError: If authentication fails or times out.

        Returns:
            None
        """
        try:
            resp = requests.post(
                f"{self.url}{_AUTH_PATH}",
                json={
                    "identity": self.admin_email,
                    "password": self.admin_password,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise DataSourceError(
                "pocketbase", "Authentication request timed out."
            ) from exc
        except requests.HTTPError as exc:
            raise DataSourceError(
                "pocketbase",
                f"Authentication failed with status {exc.response.status_code}.",
            ) from exc
        except requests.ConnectionError as exc:
            raise DataSourceError(
                "pocketbase", f"Cannot reach PocketBase at {self.url}: {exc}"
            ) from exc

        self._token = resp.json()["token"]
        logger.info("PocketBase authenticated as %s", self.admin_email)

    def test_connection(self) -> bool:
        """Authenticate and verify the connection is healthy.

        Returns:
            ``True`` if authentication succeeds.

        Raises:
            DataSourceError: If authentication fails.
        """
        self.connect()
        return True

    # ── Schema discovery ──────────────────────────────────────────────────────

    def list_collections(self) -> list[str]:
        """Return all PocketBase collection names.

        Returns:
            Sorted list of collection name strings.

        Raises:
            DataSourceError: If the request fails.
        """
        if not self._token:
            self.connect()

        try:
            resp = requests.get(
                f"{self.url}{_COLLECTIONS_PATH}",
                headers=self._auth_headers(),
                params={"perPage": 500},
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise DataSourceError("pocketbase", "list_collections timed out.") from exc
        except requests.HTTPError as exc:
            raise DataSourceError(
                "pocketbase",
                f"list_collections failed with status {exc.response.status_code}.",
            ) from exc

        items = resp.json().get("items", [])
        return sorted(c["name"] for c in items)

    def list_fields(self, collection: str) -> list[dict[str, str]]:
        """Return the fields of a PocketBase collection.

        Uses the PocketBase collection schema endpoint. PocketBase
        always includes ``id``, ``created``, and ``updated`` system
        fields, which are injected at the end of the list.

        Args:
            collection: PocketBase collection name.

        Returns:
            List of ``{"name": ..., "type": ...}`` dicts.

        Raises:
            DataSourceError: If the request fails.
        """
        if not self._token:
            self.connect()

        path = _COLLECTION_PATH.format(collection=collection)
        try:
            resp = requests.get(
                f"{self.url}{path}",
                headers=self._auth_headers(),
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise DataSourceError(
                "pocketbase", f"list_fields for '{collection}' timed out."
            ) from exc
        except requests.HTTPError as exc:
            raise DataSourceError(
                "pocketbase",
                f"list_fields for '{collection}' failed: HTTP {exc.response.status_code}.",
            ) from exc

        schema = resp.json().get("schema", [])
        fields: list[dict[str, str]] = [
            {
                "name": f["name"],
                "type": _PB_TYPE_MAP.get(f.get("type", "text"), "text"),
            }
            for f in schema
        ]
        # Inject PocketBase system fields
        fields += [
            {"name": "id",      "type": "text"},
            {"name": "created", "type": "date"},
            {"name": "updated", "type": "date"},
        ]
        return fields

    # ── Data fetching ─────────────────────────────────────────────────────────

    def fetch(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        """Fetch records from a PocketBase collection.

        Supported ``query`` keys:
            collection (str):  Required. Collection name to query.
            filter     (str):  Optional. PocketBase filter expression.
            sort       (str):  Optional. Sort field, e.g. ``-created``.
            per_page   (int):  Optional. Page size, default 100.

        Args:
            query: Dict with the keys described above.

        Returns:
            List of record dicts from the ``items`` field of the response.

        Raises:
            DataSourceError: If the request fails or times out.
        """
        if not self._token:
            self.connect()

        params = self._build_params(query)
        path = _RECORDS_PATH.format(collection=query["collection"])

        try:
            resp = requests.get(
                f"{self.url}{path}",
                headers=self._auth_headers(),
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
        except requests.Timeout as exc:
            raise DataSourceError(
                "pocketbase",
                f"Fetch from '{query['collection']}' timed out.",
            ) from exc
        except requests.HTTPError as exc:
            raise DataSourceError(
                "pocketbase",
                f"Fetch failed with status {exc.response.status_code}.",
            ) from exc

        return resp.json().get("items", [])

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _auth_headers(self) -> dict[str, str]:
        """Return Authorization header dict using the cached token.

        Returns:
            Dict with Bearer Authorization header.
        """
        return {"Authorization": self._token or ""}

    def _build_params(self, query: dict[str, Any]) -> dict[str, Any]:
        """Build HTTP query parameters from the rule query dict.

        Args:
            query: Rule-supplied query dict.

        Returns:
            Dict of HTTP query parameters for the requests call.
        """
        params: dict[str, Any] = {
            "sort": query.get("sort", "created"),
            "perPage": query.get("per_page", 100),
        }
        if "filter" in query:
            params["filter"] = query["filter"]
        if "expand" in query:
            params["expand"] = query["expand"]
        return params
