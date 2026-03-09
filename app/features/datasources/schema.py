"""
Pydantic schemas for the datasources feature.

Defines request bodies and response models for all datasource endpoints.
No logic, no DB calls — data shapes only.
"""

from typing import Any

from pydantic import BaseModel, Field


class DatasourceCreate(BaseModel):
    """Request body for saving a new datasource connection.

    Attributes:
        name:   Human-readable label, e.g. ``Production PocketBase``.
        type:   Connector type key — ``pocketbase``, ``sqlserver``,
                or ``mongodb``.
        config: Connection parameters specific to the connector type.
                PocketBase: ``{url, admin_email, admin_password}``.
                SQL Server: ``{connection_string}``.
                MongoDB:    ``{uri, database}``.
    """

    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1)
    config: dict[str, Any] = {}


class DatasourceUpdate(BaseModel):
    """Request body for updating an existing datasource connection.

    All fields optional — only provided fields are updated.

    Attributes:
        name:   New label.
        config: New/merged connection parameters.
    """

    name: str | None = None
    config: dict[str, Any] | None = None


class DatasourceOut(BaseModel):
    """Response model for a saved datasource connection.

    Attributes:
        id:   PocketBase record ID.
        name: Human-readable label.
        type: Connector type key.
        config: Connection parameters (credentials omitted from response).
    """

    id: str
    name: str
    type: str
    config: dict[str, Any]

    model_config = {"from_attributes": True}


class FieldOut(BaseModel):
    """Response model for a single field descriptor.

    Attributes:
        name: Field / column name.
        type: Normalised type — ``text``, ``number``, ``bool``, ``date``, ``json``.
    """

    name: str
    type: str
