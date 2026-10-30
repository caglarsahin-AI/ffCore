"""Approval queue (07): tool calls that wait for a person, with their decision trail.

Project members from analyst up read the queue in either access mode. Approve and reject need a
console session, `edit` access and a role at least the approval's `assigned_role`
(`services.approvals.denial`, also returned per item as `can_decide`). The decision and the run's
continuation (06a `runtime.resume.resume_run`) are one transaction.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.approvals_schemas import (
    ApprovalCount,
    ApprovalDecided,
    ApprovalList,
    ApprovalOut,
    ApprovalStatus,
    DecisionRequest,
)
from ffcore.api.common import ERROR_RESPONSES, SessionDep, not_found
from ffcore.api.runs import QueueDep, SettingsDep
from ffcore.core.audit import request_context
from ffcore.core.auth import Actor, require_role
from ffcore.models.approvals import Approval
from ffcore.runtime import resume
from ffcore.services import approvals

router = APIRouter(
    prefix="/projects/{project_id}/approvals", tags=["approvals"], responses=ERROR_RESPONSES
)

Viewer = Annotated[Actor, Depends(require_role("analyst"))]
# The least role that may decide anything; the approval's own assigned_role is checked after.
Decider = Annotated[Actor, Depends(require_role("analyst", write=True))]


def approval_out(row: Approval, actor: Actor, request: Request) -> ApprovalOut:
    grant = getattr(request.state, "grant", None)
    return ApprovalOut(
        id=row.id,
        project_id=row.project_id,
        run_id=row.run_id,
        tool_call_id=row.tool_call_id,
        action=row.action,
        tool_key=approvals.tool_key(row.action),
        arguments=row.arguments,
        reason_from_model=row.reason_from_model,
        status=row.status,
        assigned_role=row.assigned_role,
        requested_at=row.requested_at,
        expires_at=row.expires_at,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        resolution_note=row.resolution_note,
        can_decide=row.status == "pending"
        and approvals.may_decide(actor, grant, row.assigned_role),
    )


def _live(project_id: UUID):
    return (Approval.project_id == project_id, Approval.deleted_at.is_(None))


@router.get("", response_model=ApprovalList, summary="List the project's approvals")
async def list_approvals(
    project_id: UUID,
    actor: Viewer,
    session: SessionDep,
    request: Request,
    status: ApprovalStatus | None = None,
):
    query = select(Approval).where(*_live(project_id))
    if status is not None:
        query = query.where(Approval.status == status)
    rows = await session.scalars(query.order_by(Approval.requested_at.desc(), Approval.id))
    return ApprovalList(data=[approval_out(r, actor, request) for r in rows])


@router.get("/count", response_model=ApprovalCount, summary="Count approvals (console badge)")
async def count_approvals(
    project_id: UUID,
    actor: Viewer,
    session: SessionDep,
    status: ApprovalStatus = ApprovalStatus.pending,
):
    query = select(func.count()).select_from(Approval)
    count = await session.scalar(query.where(*_live(project_id), Approval.status == status))
    return ApprovalCount(status=status, count=count)


@router.get("/{approval_id}", response_model=ApprovalOut, summary="Get an approval")
async def get_approval(
    project_id: UUID, approval_id: UUID, actor: Viewer, session: SessionDep, request: Request
):
    query = select(Approval).where(Approval.id == approval_id, *_live(project_id))
    row = await session.scalar(query)
    if row is None:
        raise not_found("approval")
    return approval_out(row, actor, request)


async def _decide(
    decision, project_id, approval_id, body, actor, session, settings, queue, request
):
    request_id, ip = request_context(request)
    row = await approvals.decide(
        session,
        project_id=project_id,
        approval_id=approval_id,
        actor=actor,
        grant=getattr(request.state, "grant", None),
        decision=decision,
        note=body.note,
        now=datetime.now(UTC),
        request_id=request_id,
        ip=ip,
    )
    # Commits the decision and the run change together; a run that is not waiting any more
    # (cancelled) is 409 run_not_waiting and the approval stays pending for the sweep.
    after = await resume.resume_run(
        session,
        queue,
        settings,
        project_id=project_id,
        run_id=row.run_id,
        actor=actor,
        decision=decision,
        comment=body.note,
        request_id=request_id,
        ip=ip,
    )
    out = approval_out(row, actor, request)
    return ApprovalDecided(**out.model_dump(), stream_after=after)


@router.post(
    "/{approval_id}/approve", response_model=ApprovalDecided, summary="Approve and continue the run"
)
async def approve(
    project_id: UUID,
    approval_id: UUID,
    body: DecisionRequest,
    actor: Decider,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
    request: Request,
):
    return await _decide(
        "approved", project_id, approval_id, body, actor, session, settings, queue, request
    )


@router.post(
    "/{approval_id}/reject", response_model=ApprovalDecided, summary="Reject; the model is told"
)
async def reject(
    project_id: UUID,
    approval_id: UUID,
    body: DecisionRequest,
    actor: Decider,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
    request: Request,
):
    return await _decide(
        "rejected", project_id, approval_id, body, actor, session, settings, queue, request
    )
