"""
HTTP endpoints for execution log retrieval.

Single responsibility: validate HTTP input, call the service layer,
return a standard response. All routes are read-only — logs are
written by the engine, not the API.
"""

from fastapi import APIRouter, Query

from app.features.logs import service
from app.features.logs.schema import LogOut
from app.utils.response import success

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/", response_model=dict)
def list_all_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """List all execution logs across all rules, paginated.

    Args:
        page: Page number (1-based).
        size: Items per page (max 200).

    Returns:
        Standard success response with paginated log list.
    """
    result = service.list_all_logs(page, size)
    result["items"] = [LogOut.model_validate(log) for log in result["items"]]
    return success(data=result, message="Logs fetched")


@router.get("/rule/{rule_name}", response_model=dict)
def list_logs_for_rule(
    rule_name: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """List execution logs for a specific rule by name, paginated.

    Args:
        rule_name: Unique name of the rule.
        page:      Page number (1-based).
        size:      Items per page (max 200).

    Returns:
        Standard success response with paginated log list.
    """
    result = service.list_logs_for_rule(rule_name, page, size)
    result["items"] = [LogOut.model_validate(log) for log in result["items"]]
    return success(data=result, message="Logs fetched")
