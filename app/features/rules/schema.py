"""
Pydantic schemas for the rules feature.

Defines request bodies and response models for all rule endpoints.
No logic, no DB calls — data shapes only.

Rules can be created in two ways:
1. Structured (Grafana model) — provide datasource_id, collection_name,
   condition_type, condition_field, condition_op, condition_value.
   The scheduler builds a RuleEngine instance automatically.

2. Legacy class-based — provide rule_class (Python class name in registry).
   Kept for backward compatibility and developer-uploaded custom rules.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RuleCreate(BaseModel):
    """Request body for creating a new rule.

    Attributes:
        name:             Unique snake_case rule identifier.
        schedule:         Cron expression, e.g. ``*/5 * * * *``.
        description:      One sentence describing what the rule detects.

        Structured mode (Grafana model):
        datasource_id:    PocketBase ID of the saved datasource connection.
        collection_name:  Collection / table to monitor.
        condition_type:   One of new_record, threshold, no_data, change, count.
        condition_field:  Field name to evaluate.
        condition_op:     Operator — eq, ne, lt, gt, lte, gte, contains.
        condition_value:  Value to compare against.
        condition_extra:  Extra options e.g. window_minutes, count_limit.

        Legacy mode:
        rule_class:       Python class name in the rule registry.
        params:           Free-form parameter dict passed to the class.
    """

    name: str = Field(..., min_length=1, max_length=100)
    schedule: str = Field(..., min_length=1)
    description: str = ""

    # Structured condition fields
    datasource_id: str = ""
    collection_name: str = ""
    condition_type: str = ""
    condition_field: str = ""
    condition_op: str = "eq"
    condition_value: str = ""
    condition_extra: dict[str, Any] = {}

    # Legacy class-based fields
    rule_class: str = ""
    params: dict[str, Any] = {}


class RuleUpdate(BaseModel):
    """Request body for updating a rule's schedule, description, or condition.

    All fields are optional — only provided fields are updated.
    """

    schedule: str | None = None
    description: str | None = None
    collection_name: str | None = None
    condition_type: str | None = None
    condition_field: str | None = None
    condition_op: str | None = None
    condition_value: str | None = None
    condition_extra: dict[str, Any] | None = None


class RuleParamsUpdate(BaseModel):
    """Request body for updating a legacy rule's parameters.

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
        id:               Database primary key.
        name:             Unique rule name.
        rule_class:       Registry class name (empty for structured rules).
        schedule:         Cron expression.
        description:      Rule description.
        enabled:          Whether the rule is active.
        params_json:      Parameters dict (legacy rules only).
        datasource_id:    Datasource connection ID (structured rules).
        collection_name:  Collection being monitored (structured rules).
        condition_type:   Condition type key (structured rules).
        condition_field:  Field being evaluated (structured rules).
        condition_op:     Comparison operator (structured rules).
        condition_value:  Threshold / comparison value (structured rules).
        condition_extra:  Extra options dict (structured rules).
        created_at:       When the rule was registered.
        last_run_at:      Timestamp of last execution.
        last_status:      Status of last execution.
    """

    id: str
    name: str
    rule_class: str
    schedule: str
    description: str
    enabled: bool
    params_json: dict[str, Any]

    datasource_id: str = ""
    collection_name: str = ""
    condition_type: str = ""
    condition_field: str = ""
    condition_op: str = "eq"
    condition_value: str = ""
    condition_extra: dict[str, Any] = {}

    created_at: datetime
    last_run_at: datetime | None = None
    last_status: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("last_run_at", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        """Convert empty string from PocketBase to None."""
        if v == "" or v is None:
            return None
        return v

    @field_validator(
        "datasource_id", "collection_name", "condition_type",
        "condition_field", "condition_op", "condition_value",
        mode="before",
    )
    @classmethod
    def none_to_empty_str(cls, v: Any) -> Any:
        """Convert None from PocketBase to empty string for text fields."""
        return v if v is not None else ""

    @field_validator("condition_extra", "params_json", mode="before")
    @classmethod
    def none_to_empty_dict(cls, v: Any) -> Any:
        """Convert None from PocketBase to empty dict for json fields."""
        return v if isinstance(v, dict) else {}
