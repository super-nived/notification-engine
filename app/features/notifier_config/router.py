"""
HTTP endpoints for notifier config management.

Single responsibility: validate HTTP input, call the service layer,
return a standard response. No business logic here.
"""

from fastapi import APIRouter

from app.features.notifier_config import service
from app.features.notifier_config.schema import (
    NotifierConfigCreate,
    NotifierConfigOut,
    NotifierConfigUpdate,
)
from app.utils.response import success

router = APIRouter(prefix="/notifier-configs", tags=["Notifier Configs"])


@router.get("/rule/{rule_id}", response_model=dict)
def list_configs(rule_id: str):
    """List all notifier configs attached to a rule.

    Args:
        rule_id: PocketBase record ID of the parent rule.

    Returns:
        Standard success response containing a list of config objects.
    """
    configs = service.list_configs(rule_id)
    data = [NotifierConfigOut.model_validate(c) for c in configs]
    return success(data=data, message="Configs fetched")


@router.post("/", response_model=dict, status_code=201)
def create_config(payload: NotifierConfigCreate):
    """Attach a new notifier to a rule.

    Args:
        payload: Notifier config creation request body.

    Returns:
        Standard success response with the created config.
    """
    config = service.create_config(payload)
    return success(
        data=NotifierConfigOut.model_validate(config),
        message="Notifier config created",
    )


@router.get("/{config_id}", response_model=dict)
def get_config(config_id: str):
    """Fetch a single notifier config by id.

    Args:
        config_id: PocketBase record ID string.

    Returns:
        Standard success response with the config object.
    """
    config = service.get_config(config_id)
    return success(data=NotifierConfigOut.model_validate(config))


@router.patch("/{config_id}", response_model=dict)
def update_config(config_id: str, payload: NotifierConfigUpdate):
    """Update a notifier config's settings.

    Args:
        config_id: PocketBase record ID string.
        payload:   Fields to overwrite.

    Returns:
        Standard success response with the updated config.
    """
    config = service.update_config(config_id, payload)
    return success(
        data=NotifierConfigOut.model_validate(config),
        message="Config updated",
    )


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: str):
    """Delete a notifier config.

    Args:
        config_id: PocketBase record ID string.

    Returns:
        No content (204).
    """
    service.delete_config(config_id)
