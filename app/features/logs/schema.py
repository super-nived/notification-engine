"""
Pydantic schemas for the logs feature.

Defines response models for execution log endpoints.
No logic, no DB calls — data shapes only.
"""

from datetime import datetime

from pydantic import BaseModel


class LogOut(BaseModel):
    """Response model for a single execution log entry.

    Attributes:
        id:           Database primary key.
        rule_name:    Name of the rule that was executed.
        started_at:   When the execution began.
        finished_at:  When the execution completed.
        status:       Outcome string, e.g. ``ok``, ``error``, ``partial``.
        events_count: Number of events detected in this run.
        error:        Error message if the run failed, else ``None``.
    """

    id: int
    rule_name: str
    started_at: datetime
    finished_at: datetime | None
    status: str
    events_count: int
    error: str | None

    model_config = {"from_attributes": True}


class LogListParams(BaseModel):
    """Query parameters for listing logs.

    Attributes:
        page:  Page number (1-based).
        size:  Items per page.
    """

    page: int = 1
    size: int = 50
