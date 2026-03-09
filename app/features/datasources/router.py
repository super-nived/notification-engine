"""
HTTP endpoints for datasource connection management.

Single responsibility: validate HTTP input, call the service layer,
return a standard response. No business logic here.
"""

from fastapi import APIRouter

from app.features.datasources import service
from app.features.datasources.schema import (
    DatasourceCreate,
    DatasourceOut,
    DatasourceUpdate,
    FieldOut,
)
from app.utils.response import success

router = APIRouter(prefix="/datasources", tags=["Datasources"])


@router.get("/", response_model=dict)
def list_datasources():
    """List all saved datasource connections.

    Returns:
        Standard success response containing a list of datasource objects.
    """
    items = [DatasourceOut.model_validate(d) for d in service.list_datasources()]
    return success(data=items, message="Datasources fetched")


@router.post("/", response_model=dict, status_code=201)
def create_datasource(payload: DatasourceCreate):
    """Save a new datasource connection.

    Args:
        payload: Datasource creation request body.

    Returns:
        Standard success response with the created datasource.
    """
    ds = service.create_datasource(payload)
    return success(data=DatasourceOut.model_validate(ds), message="Datasource created")


@router.get("/{datasource_id}", response_model=dict)
def get_datasource(datasource_id: str):
    """Fetch a single datasource by PocketBase record ID.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        Standard success response with the datasource object.
    """
    ds = service.get_datasource(datasource_id)
    return success(data=DatasourceOut.model_validate(ds))


@router.patch("/{datasource_id}", response_model=dict)
def update_datasource(datasource_id: str, payload: DatasourceUpdate):
    """Update a datasource connection's name or config.

    Args:
        datasource_id: PocketBase record ID string.
        payload:       Fields to overwrite.

    Returns:
        Standard success response with the updated datasource.
    """
    ds = service.update_datasource(datasource_id, payload)
    return success(data=DatasourceOut.model_validate(ds), message="Datasource updated")


@router.delete("/{datasource_id}", status_code=204)
def delete_datasource(datasource_id: str):
    """Delete a saved datasource connection.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        No content (204).
    """
    service.delete_datasource(datasource_id)


@router.get("/{datasource_id}/test", response_model=dict)
def test_datasource(datasource_id: str):
    """Test connectivity for a saved datasource.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        Standard success response confirming the connection.
    """
    service.test_datasource(datasource_id)
    return success(message="Connection successful")


@router.get("/{datasource_id}/collections", response_model=dict)
def list_collections(datasource_id: str):
    """Return all collection/table names for a saved datasource.

    Args:
        datasource_id: PocketBase record ID string.

    Returns:
        Standard success response containing a list of collection name strings.
    """
    collections = service.list_collections(datasource_id)
    return success(data=collections, message="Collections fetched")


@router.get("/{datasource_id}/fields", response_model=dict)
def list_fields(datasource_id: str, collection: str):
    """Return field descriptors for a collection in a saved datasource.

    Query parameters:
        collection: Collection / table name to inspect.

    Args:
        datasource_id: PocketBase record ID string.
        collection:    Collection name query parameter.

    Returns:
        Standard success response containing a list of field descriptor dicts.
    """
    fields = service.list_fields(datasource_id, collection)
    items = [FieldOut.model_validate(f) for f in fields]
    return success(data=items, message="Fields fetched")
