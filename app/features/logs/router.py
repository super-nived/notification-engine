"""
HTTP endpoints for execution log retrieval.

All routes are read-only — logs are written by the engine, not the API.
No business logic here.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.features.logs import service
from app.features.logs.schema import LogOut
from app.utils.response import success

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.get("/", response_model=dict)
def list_all_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List all execution logs across all rules, paginated.

    Args:
        page: Page number (1-based).
        size: Items per page (max 200).

    Returns:
        Standard success response with paginated log list.
    """
    result = service.list_all_logs(db, page, size)
    result["items"] = [LogOut.model_validate(l) for l in result["items"]]
    return success(data=result, message="Logs fetched")


@router.get("/rule/{rule_name}", response_model=dict)
def list_logs_for_rule(
    rule_name: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List execution logs for a specific rule by name, paginated.

    Args:
        rule_name: Unique name of the rule.
        page:      Page number (1-based).
        size:      Items per page (max 200).

    Returns:
        Standard success response with paginated log list.
    """
    result = service.list_logs_for_rule(db, rule_name, page, size)
    result["items"] = [LogOut.model_validate(l) for l in result["items"]]
    return success(data=result, message="Logs fetched")
