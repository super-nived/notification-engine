"""
HTTP endpoints for notifier config management.

All routes are thin — they validate input, call the service layer,
and return a standard response. No business logic here.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.features.notifier_config import service
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigOut,
    NotifierConfigUpdate,
)
from app.utils.response import success

router = APIRouter(prefix="/notifier-configs", tags=["Notifier Configs"])


@router.get("/rule/{rule_id}", response_model=dict)
def list_configs(rule_id: int, db: Session = Depends(get_db)):
    """List all notifier configs attached to a rule.

    Args:
        rule_id: Primary key of the parent rule.

    Returns:
        Standard success response containing a list of config objects.
    """
    configs = service.list_configs(db, rule_id)
    data = [NotifierConfigOut.model_validate(c) for c in configs]
    return success(data=data, message="Configs fetched")


@router.post("/", response_model=dict, status_code=201)
def create_config(
    payload: NotifierConfigCreate, db: Session = Depends(get_db)
):
    """Attach a new notifier to a rule.

    Args:
        payload: Notifier config creation request body.

    Returns:
        Standard success response with the created config.
    """
    config = service.create_config(db, payload)
    return success(
        data=NotifierConfigOut.model_validate(config),
        message="Notifier config created",
    )


@router.get("/{config_id}", response_model=dict)
def get_config(config_id: int, db: Session = Depends(get_db)):
    """Fetch a single notifier config by id.

    Args:
        config_id: Primary key of the notifier config.

    Returns:
        Standard success response with the config object.
    """
    config = service.get_config(db, config_id)
    return success(data=NotifierConfigOut.model_validate(config))


@router.patch("/{config_id}", response_model=dict)
def update_config(
    config_id: int,
    payload: NotifierConfigUpdate,
    db: Session = Depends(get_db),
):
    """Update a notifier config's settings.

    Args:
        config_id: Primary key of the config to update.
        payload:   Fields to overwrite.

    Returns:
        Standard success response with the updated config.
    """
    config = service.update_config(db, config_id, payload)
    return success(
        data=NotifierConfigOut.model_validate(config),
        message="Config updated",
    )


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: int, db: Session = Depends(get_db)):
    """Delete a notifier config.

    Args:
        config_id: Primary key of the config to delete.

    Returns:
        No content (204).
    """
    service.delete_config(db, config_id)
