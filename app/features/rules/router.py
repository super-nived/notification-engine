"""
HTTP endpoints for rule management.

Single responsibility: validate HTTP input, call the service layer,
return a standard response. No business logic here.
"""

from fastapi import APIRouter, HTTPException, UploadFile

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


@router.get("/classes", response_model=dict)
def list_rule_classes():
    """List all registered rule classes with their params schema.

    Returns:
        Standard success response containing a list of rule class objects,
        each with class_name, name, description, and params_schema.
    """
    classes = service.list_rule_classes()
    return success(data=classes, message="Rule classes fetched")


@router.get("/", response_model=dict)
def list_rules():
    """List all registered rules.

    Returns:
        Standard success response containing a list of rule objects.
    """
    rules = [RuleOut.model_validate(r) for r in service.list_rules()]
    return success(data=rules, message="Rules fetched")


@router.post("/", response_model=dict, status_code=201)
def create_rule(payload: RuleCreate):
    """Create and schedule a new rule.

    Args:
        payload: Rule creation request body.

    Returns:
        Standard success response with the created rule.
    """
    rule = service.create_rule(payload)
    return success(data=RuleOut.model_validate(rule), message="Rule created")


@router.get("/{rule_id}", response_model=dict)
def get_rule(rule_id: str):
    """Fetch a single rule by PocketBase record ID.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        Standard success response with the rule object.
    """
    rule = service.get_rule(rule_id)
    return success(data=RuleOut.model_validate(rule))


@router.patch("/{rule_id}", response_model=dict)
def update_rule(rule_id: str, payload: RuleUpdate):
    """Update a rule's schedule or description.

    Args:
        rule_id: PocketBase record ID string.
        payload: Fields to overwrite.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.update_rule(rule_id, payload)
    return success(data=RuleOut.model_validate(rule), message="Rule updated")


@router.patch("/{rule_id}/params", response_model=dict)
def update_params(rule_id: str, payload: RuleParamsUpdate):
    """Update user-editable rule parameters.

    Args:
        rule_id: PocketBase record ID string.
        payload: New parameter values to merge.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.update_params(rule_id, payload)
    return success(data=RuleOut.model_validate(rule), message="Params updated")


@router.patch("/{rule_id}/toggle", response_model=dict)
def toggle_rule(rule_id: str, payload: RuleToggle):
    """Enable or disable a rule.

    Args:
        rule_id: PocketBase record ID string.
        payload: Toggle body with ``enabled`` boolean.

    Returns:
        Standard success response with the updated rule.
    """
    rule = service.toggle_rule(rule_id, payload.enabled)
    return success(data=RuleOut.model_validate(rule), message="Rule toggled")


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str):
    """Delete a rule and remove its scheduled job.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        No content (204).
    """
    service.delete_rule(rule_id)


@router.post("/{rule_id}/run", response_model=dict)
def run_now(rule_id: str):
    """Trigger a rule to execute immediately.

    Args:
        rule_id: PocketBase record ID string.

    Returns:
        Standard success response confirming the trigger.
    """
    service.run_rule_now(rule_id)
    return success(message="Rule triggered")


@router.post("/upload-class", response_model=dict, status_code=201)
async def upload_rule_class(file: UploadFile):
    """Upload a Python file containing a new BaseRule subclass.

    The file is validated (syntax + BaseRule subclass check), saved to
    app/rule_definitions/, and registered in the rule registry
    immediately — no restart required.

    Args:
        file: Uploaded .py file.

    Returns:
        Standard success response with the registered class name.
    """
    if not file.filename.endswith(".py"):
        raise HTTPException(status_code=400, detail="Only .py files are accepted.")

    try:
        source_code = (await file.read()).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read uploaded file.")

    class_name = service.upload_rule_class(file.filename, source_code)
    return success(
        data={"class_name": class_name, "available_classes": list(service.RULE_REGISTRY.keys())},
        message=f"Rule class '{class_name}' uploaded and registered successfully.",
    )
