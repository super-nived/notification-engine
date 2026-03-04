"""
SQLAlchemy ORM model definitions for the internal database.

This file contains table definitions ONLY. No queries, no business
logic, no imports from feature modules.

Tables:
- ``RuleModel``          — registered rules and their configuration.
- ``NotifierConfigModel``— notifiers attached to a rule.
- ``ExecutionLog``       — history of every rule execution.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.engine import Base


class RuleModel(Base):
    """Stores a registered rule and its live configuration.

    Attributes:
        id:          Auto-incrementing primary key.
        name:        Unique rule identifier, snake_case.
        rule_class:  Python class name used to look up in the registry.
        schedule:    Cron expression, e.g. ``* * * * *``.
        description: Human-readable description of what the rule detects.
        enabled:     Whether the scheduler should run this rule.
        params_json: JSON string of user-editable rule parameters.
        created_at:  When the rule was first registered.
        last_run_at: Timestamp of the most recent execution.
        last_status: Status string of the most recent execution.
        notifiers:   Related ``NotifierConfigModel`` records.
    """

    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rule_class: Mapped[str] = mapped_column(String(200), nullable=False)
    schedule: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    params_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    notifiers: Mapped[list["NotifierConfigModel"]] = relationship(
        "NotifierConfigModel",
        back_populates="rule",
        cascade="all, delete-orphan",
    )


class NotifierConfigModel(Base):
    """Stores a notifier attached to a specific rule.

    Attributes:
        id:           Auto-incrementing primary key.
        rule_id:      Foreign key to ``RuleModel``.
        notifier_type: Registry key, e.g. ``log``, ``email``, ``webhook``.
        config_json:  JSON string of notifier-specific settings.
        rule:         Back-reference to the parent ``RuleModel``.
    """

    __tablename__ = "notifier_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rules.id"), nullable=False
    )
    notifier_type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")

    rule: Mapped["RuleModel"] = relationship("RuleModel", back_populates="notifiers")


class ExecutionLog(Base):
    """Records the result of every rule execution.

    Attributes:
        id:           Auto-incrementing primary key.
        rule_name:    Name of the rule that was executed.
        started_at:   When the execution began.
        finished_at:  When the execution completed.
        status:       One of ``ok``, ``error``, or ``partial``.
        events_count: Number of alert events produced.
        error:        Error message if status is not ``ok``.
    """

    __tablename__ = "execution_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_name: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    events_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
