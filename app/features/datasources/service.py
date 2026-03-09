"""
Business logic for the datasources feature.

Single responsibility: validate inputs, coordinate repo calls, and
instantiate connectors for schema discovery.
No FastAPI imports, no direct DB calls.
All PocketBaseError and DataSourceError exceptions propagate to the router.
"""

import logging

from app.core.exceptions import DataSourceError, RuleConfigError, RuleNotFoundError
from app.db import pb_repositories as pb
from app.engine.registry import DATASOURCE_REGISTRY
from app.features.datasources.schema import DatasourceCreate, DatasourceUpdate

logger = logging.getLogger(__name__)


def list_datasources() -> list[dict]:
    """Return all saved datasource connections.

    Returns:
        List of datasource domain dicts.

    Raises:
        PocketBaseError: On network or HTTP failure.
    """
    return pb.get_all_datasources()


def get_datasource(datasource_id: str) -> dict:
    """Fetch a single datasource, raising if not found.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        Datasource domain dict.

    Raises:
        RuleNotFoundError: If the datasource does not exist.
        PocketBaseError:   On network failure.
    """
    ds = pb.get_datasource_by_id(datasource_id)
    if not ds:
        raise RuleNotFoundError(datasource_id)
    return ds


def create_datasource(payload: DatasourceCreate) -> dict:
    """Validate and save a new datasource connection.

    Args:
        payload: Validated ``DatasourceCreate`` request body.

    Returns:
        Created datasource domain dict.

    Raises:
        RuleConfigError: If the datasource type is not registered.
        PocketBaseError: On network or HTTP failure.
    """
    _validate_type(payload.type)
    return pb.create_datasource({
        "name":   payload.name,
        "type":   payload.type,
        "config": payload.config,
    })


def update_datasource(datasource_id: str, payload: DatasourceUpdate) -> dict:
    """Update a datasource connection.

    Args:
        datasource_id: PocketBase record ID string.
        payload:       Fields to overwrite.

    Returns:
        Updated datasource domain dict.

    Raises:
        RuleNotFoundError: If the datasource does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    get_datasource(datasource_id)  # raises if not found
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    return pb.update_datasource(datasource_id, data)


def delete_datasource(datasource_id: str) -> None:
    """Delete a datasource connection.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        None

    Raises:
        RuleNotFoundError: If the datasource does not exist.
        PocketBaseError:   On network or HTTP failure.
    """
    get_datasource(datasource_id)  # raises if not found
    pb.delete_datasource(datasource_id)


def test_datasource(datasource_id: str) -> bool:
    """Instantiate the connector and run a connection test.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        ``True`` if the connection succeeds.

    Raises:
        RuleNotFoundError: If the datasource record does not exist.
        DataSourceError:   If the connection test fails.
    """
    ds = get_datasource(datasource_id)
    connector = _build_connector(ds)
    return connector.test_connection()


def list_collections(datasource_id: str) -> list[str]:
    """Return all collection/table names for a saved datasource.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        Sorted list of collection name strings.

    Raises:
        RuleNotFoundError: If the datasource record does not exist.
        DataSourceError:   If the request to the data source fails.
    """
    ds = get_datasource(datasource_id)
    connector = _build_connector(ds)
    return connector.list_collections()


def list_fields(datasource_id: str, collection: str) -> list[dict]:
    """Return field descriptors for a collection in a saved datasource.

    Args:
        datasource_id: PocketBase record ID string.
        collection:    Collection / table name to inspect.

    Returns:
        List of ``{"name": ..., "type": ...}`` dicts.

    Raises:
        RuleNotFoundError: If the datasource record does not exist.
        DataSourceError:   If the request to the data source fails.
    """
    ds = get_datasource(datasource_id)
    connector = _build_connector(ds)
    return connector.list_fields(collection)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _validate_type(ds_type: str) -> None:
    """Check that a datasource type is registered.

    Args:
        ds_type: Datasource type key string.

    Raises:
        RuleConfigError: If the type is not registered.
    """
    if ds_type not in DATASOURCE_REGISTRY:
        raise RuleConfigError(
            f"Datasource type '{ds_type}' not registered. "
            f"Available: {list(DATASOURCE_REGISTRY.keys())}"
        )


def _build_connector(ds: dict) -> object:
    """Instantiate a datasource connector from a domain dict.

    Args:
        ds: Datasource domain dict with ``type`` and ``config``.

    Returns:
        Instantiated connector implementing ``BaseDataSource``.

    Raises:
        RuleConfigError: If the type is not registered.
        DataSourceError: If instantiation fails.
    """
    ds_type = ds["type"]
    cls = DATASOURCE_REGISTRY.get(ds_type)
    if not cls:
        raise RuleConfigError(f"Datasource type '{ds_type}' not in registry.")

    cfg = ds.get("config") or {}

    try:
        if ds_type == "pocketbase":
            from app.core.settings import settings
            return cls(
                url=cfg.get("url", settings.PB_URL),
                admin_email=cfg.get("admin_email", settings.PB_ADMIN_EMAIL),
                admin_password=cfg.get("admin_password", settings.PB_ADMIN_PASSWORD),
            )
        if ds_type == "sqlserver":
            from app.core.settings import settings
            return cls(
                connection_string=cfg.get(
                    "connection_string", settings.SQLSERVER_CONNECTION_STRING
                )
            )
        if ds_type == "mongodb":
            from app.core.settings import settings
            return cls(
                uri=cfg.get("uri", settings.MONGO_URI),
                database=cfg.get("database", settings.MONGO_DB),
            )
    except Exception as exc:
        raise DataSourceError(ds_type, f"Failed to instantiate connector: {exc}") from exc

    raise RuleConfigError(f"No builder defined for datasource type '{ds_type}'.")
