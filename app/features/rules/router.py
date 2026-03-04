"""
HTTP endpoints for rule management.

All routes are thin — they validate input, call the service layer,
and return a standard response. No business logic here.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.features.rules import service
from app.features.rules.schema import (
    RuleCreate,
    RuleOut,
    RuleParamsUpdate,
    RuleToggle,
    RuleUpdate,
)
from app.utils.response import success

router = APIRouter(prefix="/rules", tags=["Rules"])


@router.get("/", response_model=dict)
def list_rules(db: Session = Depends(get_db)):
    """List all registered rules.

    Returns:
        Standard success response containing a list of rule objects.
    """
    rules = [RuleOut.model_validate(r) for r in service.list_rules(db)]
    return success(data=rules, message="Rules fetched")


@router.post("/", response_model=dict, status_code=201)
def create_rule(payload: RuleCreate, db: Session = Depends(get_db)):
    """Create and schedule a new rule.

    Args:
        payload: Rule creation request body.

    Returns:
        Standard success response with the created rule.
    """
    rule = service.create_rule(db, payload)
    return success(data=RuleOut.model_validate(rule), message="Rule created")


@router.get("/{rule_id}", response_model=dict)
def get_rule(rule_id: int, db: Session = Depends(get_db)):
    """Fetch a single rule by id.

    Args:
        rule_id: Primary key of the rule.

    Returns:
        Standard success response with the rule object.
    """
    rule = service.get_rule(db, rule_id)
    return success(data=RuleOut.model_validate(rule))


@router.patch("/{rule_id}", response_model=dict)
def update_rule(
    rule_id: int, payload: RuleUpdate, db: Session = Depends(get_db)
):
    """Update a rule's schedule or description.

    Args:
        rule_id: Primary key of the rule to update.
        payload: Fields to overwrite.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.update_rule(db, rule_id, payload)
    return success(data=RuleOut.model_validate(rule), message="Rule updated")


@router.patch("/{rule_id}/params", response_model=dict)
def update_params(
    rule_id: int, payload: RuleParamsUpdate, db: Session = Depends(get_db)
):
    """Update user-editable rule parameters.

    Args:
        rule_id: Primary key of the rule.
        payload: New parameter values to merge.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.update_params(db, rule_id, payload)
    return success(data=RuleOut.model_validate(rule), message="Params updated")


@router.patch("/{rule_id}/toggle", response_model=dict)
def toggle_rule(
    rule_id: int, payload: RuleToggle, db: Session = Depends(get_db)
):
    """Enable or disable a rule.

    Args:
        rule_id: Primary key of the rule.
        payload: Toggle body with ``enabled`` boolean.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.toggle_rule(db, rule_id, payload.enabled)
    return success(data=RuleOut.model_validate(rule), message="Rule toggled")


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a rule and remove its scheduled job.

    Args:
        rule_id: Primary key of the rule to delete.

    Returns:
        No content (204).
    """
    service.delete_rule(db, rule_id)


@router.post("/{rule_id}/run", response_model=dict)
def run_now(rule_id: int, db: Session = Depends(get_db)):
    """Trigger a rule to execute immediately.

    Args:
        rule_id: Primary key of the rule to run.

    Returns:
        Standard success response confirming the trigger.
    """
    service.run_rule_now(db, rule_id)
    return success(message="Rule triggered")
