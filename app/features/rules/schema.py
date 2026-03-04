"""
Pydantic schemas for the rules feature.

Defines request bodies and response models for all rule endpoints.
No logic, no DB calls — data shapes only.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RuleCreate(BaseModel):
    """Request body for creating a new rule.

    Attributes:
        name:        Unique snake_case rule identifier.
        rule_class:  Python class name — must exist in the registry.
        schedule:    Cron expression, e.g. ``* * * * *``.
        description: One sentence describing what the rule detects.
        params:      User-editable rule parameters as a free-form dict.
    """

    name: str = Field(..., min_length=1, max_length=100)
    rule_class: str = Field(..., min_length=1)
    schedule: str = Field(..., min_length=1)
    description: str = ""
    params: dict[str, Any] = {}


class RuleUpdate(BaseModel):
    """Request body for updating a rule's schedule or description.

    All fields are optional — only provided fields are updated.

    Attributes:
        schedule:    New cron expression.
        description: Updated description.
    """

    schedule: str | None = None
    description: str | None = None


class RuleParamsUpdate(BaseModel):
    """Request body for updating a rule's user-editable parameters.

    Attributes:
        params: New parameter dict to merge into the existing params.
    """

    params: dict[str, Any]


class RuleToggle(BaseModel):
    """Request body for enabling or disabling a rule.

    Attributes:
        enabled: ``True`` to enable, ``False`` to disable.
    """

    enabled: bool


class RuleOut(BaseModel):
    """Response model for a rule record.

    Attributes:
        id:          Database primary key.
        name:        Unique rule name.
        rule_class:  Registry class name.
        schedule:    Cron expression.
        description: Rule description.
        enabled:     Whether the rule is active.
        params_json: JSON string of current parameters.
        created_at:  When the rule was registered.
        last_run_at: Timestamp of last execution.
        last_status: Status of last execution.
    """

    id: int
    name: str
    rule_class: str
    schedule: str
    description: str
    enabled: bool
    params_json: str
    created_at: datetime
    last_run_at: datetime | None
    last_status: str | None

    model_config = {"from_attributes": True}
