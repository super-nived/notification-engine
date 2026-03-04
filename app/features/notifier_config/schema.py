"""
Pydantic schemas for the notifier_config feature.

Defines request bodies and response models for notifier config endpoints.
No logic, no DB calls — data shapes only.
"""

from typing import Any

from pydantic import BaseModel, Field


class NotifierConfigCreate(BaseModel):
    """Request body for attaching a notifier to a rule.

    Attributes:
        rule_id:        Primary key of the rule to attach to.
        notifier_type:  Registry key, e.g. ``email``, ``webhook``.
        config_json:    Notifier-specific settings as a free-form dict.
    """

    rule_id: int
    notifier_type: str = Field(..., min_length=1)
    config_json: dict[str, Any] = {}


class NotifierConfigUpdate(BaseModel):
    """Request body for updating a notifier config's settings.

    All fields are optional — only provided fields are updated.

    Attributes:
        config_json: New settings dict to replace the existing one.
    """

    config_json: dict[str, Any] | None = None


class NotifierConfigOut(BaseModel):
    """Response model for a notifier config record.

    Attributes:
        id:             Database primary key.
        rule_id:        Foreign key to the owning rule.
        notifier_type:  Registry key for this notifier.
        config_json:    JSON string of notifier settings.
    """

    id: int
    rule_id: int
    notifier_type: str
    config_json: str

    model_config = {"from_attributes": True}
