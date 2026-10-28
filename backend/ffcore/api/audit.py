"""Audit trail, read side (FOLLOWUP-48). Writing is 03b's `@audited`."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import AuditList

router = APIRouter(prefix="/audit", tags=["audit"], responses=ERROR_RESPONSES)

CSV_MAX_ROWS = 10_000


@router.get("", response_model=AuditList, summary="List audit events")
async def list_audit(
    project_id: UUID | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: Literal["success", "denied", "error"] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """With project_id: that project's admin. Without: superadmin."""
    raise not_implemented()


@router.get(
    ".csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
    summary="Export audit events as CSV",
)
async def export_audit_csv(
    project_id: UUID | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: Literal["success", "denied", "error"] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    """At most 10,000 rows; more is 400 `export_too_large` (narrow the filters)."""
    raise not_implemented()
