"""
Data access functions for the notifier_config feature.

Thin wrappers that delegate to ``app.db.repositories``. No business
logic — only query composition specific to notifier configs.
"""

import json

from sqlalchemy.orm import Session

from app.db import repositories as base_repo
from app.db.models import NotifierConfigModel
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigUpdate,
)


def get_all_for_rule(db: Session, rule_id: int) -> list[NotifierConfigModel]:
    """Return all notifier configs attached to a rule.

    Args:
        db:      Active database session.
        rule_id: Primary key of the parent rule.

    Returns:
        List of ``NotifierConfigModel`` instances.
    """
    return base_repo.get_notifiers_for_rule(db, rule_id)


def get_by_id(db: Session, config_id: int) -> NotifierConfigModel | None:
    """Fetch a single notifier config by primary key.

    Args:
        db:        Active database session.
        config_id: Primary key of the notifier config.

    Returns:
        ``NotifierConfigModel`` if found, else ``None``.
    """
    return base_repo.get_notifier_config_by_id(db, config_id)


def create(
    db: Session, payload: NotifierConfigCreate
) -> NotifierConfigModel:
    """Insert a new notifier config into the database.

    Args:
        db:      Active database session.
        payload: Validated ``NotifierConfigCreate`` request body.

    Returns:
        Saved ``NotifierConfigModel`` with auto-generated ``id``.
    """
    config = NotifierConfigModel(
        rule_id=payload.rule_id,
        notifier_type=payload.notifier_type,
        config_json=json.dumps(payload.config_json),
    )
    return base_repo.create_notifier_config(db, config)


def update(
    db: Session,
    config: NotifierConfigModel,
    payload: NotifierConfigUpdate,
) -> NotifierConfigModel:
    """Apply a partial update to a notifier config's settings.

    Args:
        db:      Active database session.
        config:  Existing ``NotifierConfigModel`` to update.
        payload: ``NotifierConfigUpdate`` with optional fields.

    Returns:
        Updated and committed ``NotifierConfigModel``.
    """
    if payload.config_json is not None:
        config.config_json = json.dumps(payload.config_json)
    db.commit()
    db.refresh(config)
    return config


def delete(db: Session, config: NotifierConfigModel) -> None:
    """Delete a notifier config from the database.

    Args:
        db:     Active database session.
        config: ``NotifierConfigModel`` to delete.

    Returns:
        None
    """
    base_repo.delete_notifier_config(db, config)
