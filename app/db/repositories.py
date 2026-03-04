"""
All internal database query functions.

No other module queries the database directly. Every read and write
operation on the internal SQLite database goes through a function
defined here. No business logic — only data access.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ExecutionLog, NotifierConfigModel, RuleModel

logger = logging.getLogger(__name__)


# ── RuleModel ────────────────────────────────────────────────────────────────


def get_all_rules(db: Session) -> list[RuleModel]:
    """Return all rules ordered by id ascending.

    Args:
        db: Active database session.

    Returns:
        List of ``RuleModel`` instances, may be empty.
    """
    return db.query(RuleModel).order_by(RuleModel.id).all()


def get_enabled_rules(db: Session) -> list[RuleModel]:
    """Return only rules where ``enabled`` is True.

    Args:
        db: Active database session.

    Returns:
        List of enabled ``RuleModel`` instances.
    """
    return db.query(RuleModel).filter(RuleModel.enabled.is_(True)).all()


def get_rule_by_id(db: Session, rule_id: int) -> RuleModel | None:
    """Fetch a single rule by primary key.

    Args:
        db:      Active database session.
        rule_id: Primary key of the rule to fetch.

    Returns:
        ``RuleModel`` instance if found, otherwise ``None``.
    """
    return db.query(RuleModel).filter(RuleModel.id == rule_id).first()


def get_rule_by_name(db: Session, name: str) -> RuleModel | None:
    """Fetch a single rule by its unique name.

    Args:
        db:   Active database session.
        name: Unique rule name to look up.

    Returns:
        ``RuleModel`` instance if found, otherwise ``None``.
    """
    return db.query(RuleModel).filter(RuleModel.name == name).first()


def create_rule(db: Session, rule: RuleModel) -> RuleModel:
    """Persist a new rule to the database.

    Args:
        db:   Active database session.
        rule: Unsaved ``RuleModel`` instance to insert.

    Returns:
        The saved ``RuleModel`` with its auto-generated ``id`` populated.
    """
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


def update_rule_last_run(
    db: Session,
    rule_name: str,
    status: str,
) -> None:
    """Update ``last_run_at`` and ``last_status`` after an execution.

    Args:
        db:        Active database session.
        rule_name: Name of the rule to update.
        status:    Execution status string (``ok`` / ``error`` / ``partial``).

    Returns:
        None
    """
    db.query(RuleModel).filter(RuleModel.name == rule_name).update(
        {
            RuleModel.last_run_at: datetime.now(timezone.utc),
            RuleModel.last_status: status,
        }
    )
    db.commit()


def delete_rule(db: Session, rule: RuleModel) -> None:
    """Delete a rule and its associated notifier configs from the database.

    Args:
        db:   Active database session.
        rule: ``RuleModel`` instance to delete.

    Returns:
        None
    """
    db.delete(rule)
    db.commit()


# ── NotifierConfigModel ──────────────────────────────────────────────────────


def get_notifiers_for_rule(
    db: Session, rule_id: int
) -> list[NotifierConfigModel]:
    """Return all notifier configs linked to a rule.

    Args:
        db:      Active database session.
        rule_id: Primary key of the parent rule.

    Returns:
        List of ``NotifierConfigModel`` instances, may be empty.
    """
    return (
        db.query(NotifierConfigModel)
        .filter(NotifierConfigModel.rule_id == rule_id)
        .all()
    )


def get_notifier_config_by_id(
    db: Session, config_id: int
) -> NotifierConfigModel | None:
    """Fetch a single notifier config by primary key.

    Args:
        db:        Active database session.
        config_id: Primary key to look up.

    Returns:
        ``NotifierConfigModel`` if found, otherwise ``None``.
    """
    return (
        db.query(NotifierConfigModel)
        .filter(NotifierConfigModel.id == config_id)
        .first()
    )


def create_notifier_config(
    db: Session, config: NotifierConfigModel
) -> NotifierConfigModel:
    """Persist a new notifier config to the database.

    Args:
        db:     Active database session.
        config: Unsaved ``NotifierConfigModel`` to insert.

    Returns:
        Saved ``NotifierConfigModel`` with ``id`` populated.
    """
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def delete_notifier_config(db: Session, config: NotifierConfigModel) -> None:
    """Remove a notifier config from the database.

    Args:
        db:     Active database session.
        config: ``NotifierConfigModel`` instance to delete.

    Returns:
        None
    """
    db.delete(config)
    db.commit()


# ── ExecutionLog ─────────────────────────────────────────────────────────────


def create_execution_log(db: Session, log: ExecutionLog) -> ExecutionLog:
    """Persist an execution log entry to the database.

    Args:
        db:  Active database session.
        log: Unsaved ``ExecutionLog`` instance to insert.

    Returns:
        Saved ``ExecutionLog`` with ``id`` populated.
    """
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_logs_for_rule(
    db: Session, rule_name: str, limit: int = 50
) -> list[ExecutionLog]:
    """Return the most recent execution logs for a rule.

    Args:
        db:        Active database session.
        rule_name: Name of the rule to filter by.
        limit:     Maximum number of records to return.

    Returns:
        List of ``ExecutionLog`` instances, newest first.
    """
    return (
        db.query(ExecutionLog)
        .filter(ExecutionLog.rule_name == rule_name)
        .order_by(ExecutionLog.started_at.desc())
        .limit(limit)
        .all()
    )


def get_all_logs(db: Session, limit: int = 100) -> list[ExecutionLog]:
    """Return the most recent execution logs across all rules.

    Args:
        db:    Active database session.
        limit: Maximum number of records to return.

    Returns:
        List of ``ExecutionLog`` instances, newest first.
    """
    return (
        db.query(ExecutionLog)
        .order_by(ExecutionLog.started_at.desc())
        .limit(limit)
        .all()
    )
