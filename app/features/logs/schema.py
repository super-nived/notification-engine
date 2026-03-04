"""
Pydantic schemas for the logs feature.

Defines response models for execution log endpoints.
No logic, no DB calls — data shapes only.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_validator


class LogOut(BaseModel):
    """Response model for a single execution log entry.

    Attributes:
        id:           PocketBase record ID.
        rule_name:    Name of the rule that was executed.
        started_at:   When the execution began.
        finished_at:  When the execution completed.
        status:       Outcome string, e.g. ``ok``, ``error``, ``partial``.
        events_count: Number of events detected in this run.
        error:        Error message if the run failed, else ``None``.
    """

    id: str
    rule_name: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    status: str
    events_count: int = 0
    error: str | None = None

    model_config = {"from_attributes": True}

    @field_validator("started_at", "finished_at", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        """Convert empty string from PocketBase to None."""
        if v == "" or v is None:
            return None
        return v


class LogListParams(BaseModel):
    """Query parameters for listing logs.

    Attributes:
        page:  Page number (1-based).
        size:  Items per page.
    """

    page: int = 1
    size: int = 50
