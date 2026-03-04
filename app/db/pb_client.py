"""
PocketBase HTTP client.

Single responsibility: authenticate with PocketBase admin API and
expose low-level CRUD primitives. No business logic here.

All network errors are caught and re-raised as ``PocketBaseError``
so callers never deal with raw ``requests`` exceptions.
"""

import logging
from typing import Any

import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout

from app.core.settings import settings

logger = logging.getLogger(__name__)

# ── Module-level token cache ───────────────────────────────────────────────────
_token: str = ""


class PocketBaseError(Exception):
    """Raised for any PocketBase HTTP or connectivity failure.

    Args:
        operation: Short description of what was being attempted.
        detail:    Error detail from the response or exception.
    """

    def __init__(self, operation: str, detail: str) -> None:
        super().__init__(f"PocketBase [{operation}] failed: {detail}")
        self.operation = operation
        self.detail = detail


# ── Authentication ─────────────────────────────────────────────────────────────


def authenticate() -> None:
    """Authenticate as PocketBase admin and cache the Bearer token.

    Called once at startup via ``app.core.events``.

    Raises:
        PocketBaseError: If the request fails or credentials are wrong.

    Returns:
        None
    """
    global _token
    url = f"{settings.PB_URL}/api/admins/auth-with-password"
    try:
        resp = requests.post(
            url,
            json={
                "identity": settings.PB_ADMIN_EMAIL,
                "password": settings.PB_ADMIN_PASSWORD,
            },
            timeout=10,
        )
        resp.raise_for_status()
        _token = resp.json()["token"]
        logger.info("PocketBase admin authenticated successfully.")
    except Timeout:
        raise PocketBaseError("authenticate", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError("authenticate", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError("authenticate", f"Connection refused: {exc}")


def _headers() -> dict[str, str]:
    """Return Authorization headers using the cached token.

    Returns:
        Dict with ``Authorization`` Bearer header.
    """
    return {"Authorization": f"Bearer {_token}"}


# ── CRUD primitives ────────────────────────────────────────────────────────────


def pb_list(
    collection: str,
    filter_expr: str = "",
    sort: str = "-created",
    per_page: int = 200,
) -> list[dict[str, Any]]:
    """Fetch records from a PocketBase collection.

    Args:
        collection:  PocketBase collection name.
        filter_expr: PocketBase filter string, e.g. ``enabled=true``.
        sort:        Sort expression, e.g. ``-created``.
        per_page:    Maximum records to retrieve.

    Returns:
        List of record dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    url = f"{settings.PB_URL}/api/collections/{collection}/records"
    params: dict[str, Any] = {"perPage": per_page, "sort": sort}
    if filter_expr:
        params["filter"] = filter_expr
    try:
        resp = requests.get(url, headers=_headers(), params=params, timeout=10)
        resp.raise_for_status()
        return resp.json().get("items", [])
    except Timeout:
        raise PocketBaseError(f"list:{collection}", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError(f"list:{collection}", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError(f"list:{collection}", f"Connection error: {exc}")


def pb_get(collection: str, record_id: str) -> dict[str, Any]:
    """Fetch a single record by ID.

    Args:
        collection: PocketBase collection name.
        record_id:  PocketBase record ID string.

    Returns:
        Record dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    url = f"{settings.PB_URL}/api/collections/{collection}/records/{record_id}"
    try:
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Timeout:
        raise PocketBaseError(f"get:{collection}/{record_id}", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError(f"get:{collection}/{record_id}", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError(f"get:{collection}/{record_id}", f"Connection error: {exc}")


def pb_create(collection: str, data: dict[str, Any]) -> dict[str, Any]:
    """Create a new record in a collection.

    Args:
        collection: PocketBase collection name.
        data:       Field values for the new record.

    Returns:
        Created record dict including PocketBase ``id``.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    url = f"{settings.PB_URL}/api/collections/{collection}/records"
    try:
        resp = requests.post(url, headers=_headers(), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Timeout:
        raise PocketBaseError(f"create:{collection}", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError(f"create:{collection}", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError(f"create:{collection}", f"Connection error: {exc}")


def pb_update(collection: str, record_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Partially update a record (PATCH).

    Args:
        collection: PocketBase collection name.
        record_id:  PocketBase record ID string.
        data:       Fields to update.

    Returns:
        Updated record dict.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    url = f"{settings.PB_URL}/api/collections/{collection}/records/{record_id}"
    try:
        resp = requests.patch(url, headers=_headers(), json=data, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Timeout:
        raise PocketBaseError(f"update:{collection}/{record_id}", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError(f"update:{collection}/{record_id}", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError(f"update:{collection}/{record_id}", f"Connection error: {exc}")


def pb_delete(collection: str, record_id: str) -> None:
    """Delete a record by ID.

    Args:
        collection: PocketBase collection name.
        record_id:  PocketBase record ID string.

    Returns:
        None

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    url = f"{settings.PB_URL}/api/collections/{collection}/records/{record_id}"
    try:
        resp = requests.delete(url, headers=_headers(), timeout=10)
        resp.raise_for_status()
    except Timeout:
        raise PocketBaseError(f"delete:{collection}/{record_id}", "Request timed out")
    except HTTPError as exc:
        raise PocketBaseError(f"delete:{collection}/{record_id}", f"HTTP {exc.response.status_code}: {exc.response.text}")
    except ConnectionError as exc:
        raise PocketBaseError(f"delete:{collection}/{record_id}", f"Connection error: {exc}")
