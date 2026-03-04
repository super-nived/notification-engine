"""
PocketBase data source connector.

Authenticates as an admin user and fetches records from a PocketBase
collection via the REST API. Token is cached after the first call to
``connect()`` and reused on subsequent ``fetch()`` calls.
"""

import logging
from typing import Any

import requests

from app.core.exceptions import DataSourceError
from app.datasources.base import BaseDataSource

logger = logging.getLogger(__name__)

_AUTH_PATH = "/api/admins/auth-with-password"
_RECORDS_PATH = "/api/collections/{collection}/records"


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

        self._token = resp.json()["token"]
        logger.info("PocketBase authenticated as %s", self.admin_email)

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
                headers={"Authorization": self._token},
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

    def _build_params(self, query: dict[str, Any]) -> dict[str, Any]:
        """Build the HTTP query parameters dict from the query dict.

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
        return params
