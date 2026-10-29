"""Approval queue rules (07) shared by the routes, the TTL job and the run hook.

The run side (opening an approval at the interrupt, closing an expired run, resuming after a
decision) is 06a's; it reaches these functions through the hook added in slice 6. Until then a
run is identified by its id only and closing it is a callable the caller passes in.
"""

import hashlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.audit import AuditEntry, write_event, write_event_detached
from ffcore.core.auth import ROLE_ORDER, Actor, Grant
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.models.approvals import APPROVER_ROLES, Approval

log = logging.getLogger("ffcore.approvals")

# Who resolved an approval that nobody decided (resolved_by of an expired row).
TTL_RESOLVER = "system:approval_ttl"
# Error code of a run closed because its approval expired.
EXPIRED_RUN_CODE = "approval_expired"

CloseRun = Callable[[uuid.UUID, str], Awaitable[None]]


def tool_key(action: str) -> str | None:
    """`<tool_key>__<action>` (C7) -> `<tool_key>`; None for a name without the separator."""
    key, sep, _ = action.partition("__")
    return key if sep and key else None


def denial(actor: Actor, grant: Grant | None, assigned_role: str) -> str | None:
    """Why this caller may not approve or reject, as an error code; None when it may.

    A decision needs a person in a console session (K-07-0002 B3): never a service account, an
    API key, or a user reached through X-On-Behalf-Of. Then `edit` access and a role at least
    `assigned_role` (brief 07: an analyst cannot decide an approval assigned to developer).
    """
    if actor.actor_type != "user" or actor.via_service:
        return "approval_requires_user_session"
    if grant is None:
        return "insufficient_role"
    if grant.access != "edit":
        return "read_only_access"
    if ROLE_ORDER.index(grant.role) < ROLE_ORDER.index(assigned_role):
        return "insufficient_role"
    return None


def may_decide(actor: Actor, grant: Grant | None, assigned_role: str) -> bool:
    return denial(actor, grant, assigned_role) is None


DENIAL_MESSAGES = {
    "approval_requires_user_session": "Approvals are given by a signed-in user, not on "
    "someone's behalf.",
    "read_only_access": "Your access mode is read-only.",
    "insufficient_role": "Your role does not allow deciding this approval.",
}


async def decide(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
    actor: Actor,
    grant: Grant | None,
    decision: str,
    note: str | None,
    now: datetime,
    request_id: str,
    ip: str | None = None,
) -> Approval:
    """Record an approve/reject on a pending approval, audited, in the caller's transaction.

    The caller resumes the run in the same transaction (06a `runtime.resume.resume_run`
    commits), so the approval and the run change together. Every refusal is coded and audited:
    403 per `denial`, 404 for another project's or an unknown approval, 409
    `approval_not_pending` once decided or expired, 409 `approval_expired` when the TTL passed
    before the job marked it. The status change is conditional: two clicks decide once.
    """
    if decision not in ("approved", "rejected"):
        raise ValueError(f"decision must be approved or rejected, got {decision!r}")
    row = await session.scalar(
        select(Approval).where(
            Approval.id == approval_id,
            Approval.project_id == project_id,
            Approval.deleted_at.is_(None),
        )
    )
    if row is None:
        raise ApiError(404, "not_found_error", "approval_not_found", "Approval not found.")
    code = denial(actor, grant, row.assigned_role)
    if code is not None:
        await write_event_detached(
            _entry(row, actor, "denied", f"approval.{decision}", request_id, ip, {"code": code})
        )
        raise ApiError(403, "permission_error", code, DENIAL_MESSAGES[code])
    if row.status != "pending":
        raise ApiError(
            409, "conflict_error", "approval_not_pending", f"The approval is {row.status}."
        )
    if row.expires_at <= now:
        raise ApiError(
            409, "conflict_error", "approval_expired", "The approval expired before a decision."
        )
    changed = await session.execute(
        update(Approval)
        .where(Approval.id == row.id, Approval.status == "pending")
        .values(
            status=decision,
            resolved_at=now,
            resolved_by=actor.actor_id,
            resolution_note=note,
            updated_at=now,
        )
    )
    if changed.rowcount != 1:
        raise ApiError(409, "conflict_error", "approval_not_pending", "The approval was decided.")
    await session.refresh(row)
    await write_event(
        session,
        _entry(
            row,
            actor,
            "success",
            f"approval.{decision}",
            request_id,
            ip,
            {
                "run_id": str(row.run_id),
                "action": row.action,
                "arguments": row.arguments,
                "assigned_role": row.assigned_role,
                "note": note,
            },
        ),
    )
    return row


def _entry(row, actor, outcome, action, request_id, ip, after) -> AuditEntry:
    return AuditEntry(
        action=action,
        resource_type="approval",
        outcome=outcome,
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        project_id=str(row.project_id),
        resource_id=str(row.id),
        before={"status": "pending"} if outcome == "success" else None,
        after=after,
        request_id=request_id,
        ip=ip,
    )


def args_hash(arguments: dict) -> str:
    """SHA-256 of the canonical JSON (sorted keys, no spaces): the same call hashes the same."""
    canonical = json.dumps(arguments, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Opened:
    """`reused`: an approved twin in the same run answered; nobody is asked (approval_reused)."""

    approval: Approval
    reused: bool


async def open_for_interrupt(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    tool_call_id: str,
    action: str,
    arguments: dict,
    assign_to: str,
    created_by: str,
    now: datetime,
    settings: Settings,
    reason_from_model: str | None = None,
) -> Opened:
    """The approval for one interrupted tool call. `arguments` are the masked ones (06a writes
    them through the guardrail before the interrupt); raw values never come here.

    Idempotent per (run_id, tool_call_id): a resumed graph that interrupts again gets the same
    row. The same action with the same arguments approved earlier in this run is not asked
    again (brief 07 step 6); the caller records `approval_reused` on the run, never silently.
    """
    if assign_to not in APPROVER_ROLES:
        raise ValueError(f"assign_to must be one of {APPROVER_ROLES}, got {assign_to!r}")
    existing = await session.scalar(
        select(Approval).where(Approval.run_id == run_id, Approval.tool_call_id == tool_call_id)
    )
    if existing is not None:
        return Opened(existing, reused=False)
    digest = args_hash(arguments)
    twin = await session.scalar(
        select(Approval)
        .where(
            Approval.run_id == run_id,
            Approval.action == action,
            Approval.args_hash == digest,
            Approval.status == "approved",
        )
        .order_by(Approval.resolved_at.desc())
        .limit(1)
    )
    if twin is not None:
        return Opened(twin, reused=True)
    row = Approval(
        project_id=project_id,
        run_id=run_id,
        tool_call_id=tool_call_id,
        action=action,
        arguments=arguments,
        args_hash=digest,
        reason_from_model=reason_from_model,
        assigned_role=assign_to,
        requested_at=now,
        expires_at=now + timedelta(minutes=settings.approval_ttl_min),
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return Opened(row, reused=False)


async def expire_due(
    session: AsyncSession, *, now: datetime, close_run: CloseRun
) -> list[Approval]:
    """Mark pending approvals past `expires_at` as expired and close their runs.

    The update is conditional on `status = 'pending'`, so a decision that lands first wins and
    two job runs in the same tick expire a row once (U1: arq cron is unique per tick anyway).
    Each closed run gets EXPIRED_RUN_CODE; a failure to close one is logged and re-raised after
    the others, never swallowed.
    """
    rows = list(
        await session.scalars(
            update(Approval)
            .where(Approval.status == "pending", Approval.expires_at <= now)
            .values(status="expired", resolved_at=now, resolved_by=TTL_RESOLVER, updated_at=now)
            .returning(Approval)
        )
    )
    await session.commit()
    failures: list[Exception] = []
    for row in rows:
        log.warning(
            "approval_expired approval_id=%s run_id=%s project_id=%s",
            row.id,
            row.run_id,
            row.project_id,
        )
        try:
            await close_run(row.run_id, EXPIRED_RUN_CODE)
        except Exception as exc:  # each run is tried; the job still fails loud below
            log.error("approval_expired_run_not_closed run_id=%s error=%s", row.run_id, exc)
            failures.append(exc)
    if failures:
        raise RuntimeError(f"{len(failures)} expired approval run(s) could not be closed")
    return rows


async def report_pending_age(
    session: AsyncSession, *, now: datetime, settings: Settings
) -> list[Approval]:
    """Pending approvals older than APPROVAL_ALERT_AGE_MIN, each logged once as
    `approval_pending_age` (brief R6.2; `age_reported_at` marks it). The 03c alert system takes
    these over when it exists; until then the log line is the signal, nothing is dropped."""
    limit = now - timedelta(minutes=settings.approval_alert_age_min)
    rows = list(
        await session.scalars(
            update(Approval)
            .where(
                Approval.status == "pending",
                Approval.requested_at <= limit,
                Approval.age_reported_at.is_(None),
            )
            .values(age_reported_at=now)
            .returning(Approval)
        )
    )
    await session.commit()
    for row in sorted(rows, key=lambda r: r.requested_at):
        age_min = int((now - row.requested_at).total_seconds() // 60)
        log.warning(
            "approval_pending_age approval_id=%s project_id=%s age_min=%s assigned_role=%s",
            row.id,
            row.project_id,
            age_min,
            row.assigned_role,
        )
    return rows
