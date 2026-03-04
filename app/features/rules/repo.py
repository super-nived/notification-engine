"""
Data access functions for the rules feature.

Thin wrappers that delegate to ``app.db.repositories``. No business
logic — only query composition that is specific to the rules feature.
"""

import json

from sqlalchemy.orm import Session

from app.db import repositories as base_repo
from app.db.models import RuleModel
from app.features.rules.schema import RuleCreate, RuleParamsUpdate, RuleUpdate


def get_all(db: Session) -> list[RuleModel]:
    """Return all rules ordered by id.

    Args:
        db: Active database session.

    Returns:
        List of ``RuleModel`` instances.
    """
    return base_repo.get_all_rules(db)


def get_by_id(db: Session, rule_id: int) -> RuleModel | None:
    """Fetch a rule by primary key.

    Args:
        db:      Active database session.
        rule_id: Rule primary key.

    Returns:
        ``RuleModel`` if found, else ``None``.
    """
    return base_repo.get_rule_by_id(db, rule_id)


def create(db: Session, payload: RuleCreate) -> RuleModel:
    """Insert a new rule into the database.

    Args:
        db:      Active database session.
        payload: Validated ``RuleCreate`` request body.

    Returns:
        Saved ``RuleModel`` with auto-generated ``id``.
    """
    rule = RuleModel(
        name=payload.name,
        rule_class=payload.rule_class,
        schedule=payload.schedule,
        description=payload.description,
        enabled=True,
        params_json=json.dumps(payload.params),
    )
    return base_repo.create_rule(db, rule)


def update(db: Session, rule: RuleModel, payload: RuleUpdate) -> RuleModel:
    """Apply a partial update to a rule's schedule or description.

    Args:
        db:      Active database session.
        rule:    Existing ``RuleModel`` to update.
        payload: ``RuleUpdate`` with optional fields to overwrite.

    Returns:
        Updated and committed ``RuleModel``.
    """
    if payload.schedule is not None:
        rule.schedule = payload.schedule
    if payload.description is not None:
        rule.description = payload.description
    db.commit()
    db.refresh(rule)
    return rule


def update_params(
    db: Session, rule: RuleModel, payload: RuleParamsUpdate
) -> RuleModel:
    """Merge new parameters into a rule's existing params JSON.

    Args:
        db:      Active database session.
        rule:    Existing ``RuleModel`` to update.
        payload: ``RuleParamsUpdate`` with new parameter values.

    Returns:
        Updated and committed ``RuleModel``.
    """
    existing = json.loads(rule.params_json or "{}")
    existing.update(payload.params)
    rule.params_json = json.dumps(existing)
    db.commit()
    db.refresh(rule)
    return rule


def toggle(db: Session, rule: RuleModel, enabled: bool) -> RuleModel:
    """Enable or disable a rule.

    Args:
        db:      Active database session.
        rule:    ``RuleModel`` to toggle.
        enabled: New enabled state.

    Returns:
        Updated and committed ``RuleModel``.
    """
    rule.enabled = enabled
    db.commit()
    db.refresh(rule)
    return rule


def delete(db: Session, rule: RuleModel) -> None:
    """Delete a rule from the database.

    Args:
        db:   Active database session.
        rule: ``RuleModel`` to delete.

    Returns:
        None
    """
    base_repo.delete_rule(db, rule)
