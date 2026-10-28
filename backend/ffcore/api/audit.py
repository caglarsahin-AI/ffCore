"""Audit trail, read side (FOLLOWUP-48). Writing is 03b's `@audited`; stored values are already
masked at write time, so nothing here unmasks or re-masks."""

import csv
import io
import json
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import Select, func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep
from ffcore.api.schemas import AuditEventOut, AuditList
from ffcore.core.auth import Actor, RoleRequirement, authorize, require_superadmin, resolve_actor
from ffcore.core.errors import ApiError
from ffcore.models.audit import AuditEvent

router = APIRouter(prefix="/audit", tags=["audit"], responses=ERROR_RESPONSES)

CSV_MAX_ROWS = 10_000
CSV_COLUMNS = (
    "id",
    "ts",
    "actor_type",
    "actor_id",
    "project_id",
    "action",
    "resource_type",
    "resource_id",
    "outcome",
    "before",
    "after",
    "request_id",
    "ip",
)
_PROJECT_ADMIN = RoleRequirement("admin", write=False, scope="project")
_SUPERADMIN = require_superadmin()


async def audit_reader(request: Request, actor: Annotated[Actor, Depends(resolve_actor)]) -> Actor:
    """With ?project_id: that project's admin (either access mode). Without: superadmin."""
    project_id = request.query_params.get("project_id")
    need = _PROJECT_ADMIN if project_id else _SUPERADMIN
    return await authorize(request, actor, project_id, need)


Reader = Annotated[Actor, Depends(audit_reader)]


def _filtered(project_id, actor_id, action, resource_type, outcome, since, until) -> Select:
    query = select(AuditEvent)
    for column, value in (
        (AuditEvent.project_id, project_id),
        (AuditEvent.actor_id, actor_id),
        (AuditEvent.action, action),
        (AuditEvent.resource_type, resource_type),
        (AuditEvent.outcome, outcome),
    ):
        if value is not None:
            query = query.where(column == value)
    if since is not None:
        query = query.where(AuditEvent.ts >= since)
    if until is not None:
        query = query.where(AuditEvent.ts < until)
    return query


def _out(event: AuditEvent) -> AuditEventOut:
    data = {c: getattr(event, c) for c in CSV_COLUMNS}
    data["ip"] = str(event.ip) if event.ip is not None else None
    return AuditEventOut(**data)


@router.get("", response_model=AuditList, summary="List audit events")
async def list_audit(
    actor: Reader,
    session: SessionDep,
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
    query = _filtered(project_id, actor_id, action, resource_type, outcome, since, until)
    rows = await session.scalars(
        query.order_by(AuditEvent.ts.desc(), AuditEvent.id).limit(limit).offset(offset)
    )
    return AuditList(data=[_out(e) for e in rows], limit=limit, offset=offset)


def _cell(value) -> str:
    if value is None:
        return ""
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, dict | list) else str(value)
    # Spreadsheet formula injection: a leading =, +, - or @ is neutralised.
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get(
    ".csv",
    response_class=PlainTextResponse,
    responses={200: {"content": {"text/csv": {}}}},
    summary="Export audit events as CSV",
)
async def export_audit_csv(
    actor: Reader,
    session: SessionDep,
    project_id: UUID | None = None,
    actor_id: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: Literal["success", "denied", "error"] | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    """At most 10,000 rows; more is 400 `export_too_large` (narrow the filters)."""
    query = _filtered(project_id, actor_id, action, resource_type, outcome, since, until)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    if total > CSV_MAX_ROWS:
        raise ApiError(
            400,
            "invalid_request_error",
            "export_too_large",
            f"{total} events match; the export is limited to {CSV_MAX_ROWS}. Narrow the filters.",
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for event in await session.scalars(query.order_by(AuditEvent.ts, AuditEvent.id)):
        row = _out(event).model_dump(mode="json")
        writer.writerow(_cell(row[c]) for c in CSV_COLUMNS)
    return PlainTextResponse(buffer.getvalue(), media_type="text/csv")
