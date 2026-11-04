"""Resume a waiting run: one function for POST .../runs/{id}/resume and 07's approval endpoints.

The caller checks the role (06a: the definition's `approval.assign_to` with edit access; 07:
the approval's assigned role). This function applies the rules both share:
- A decision comes only from a signed-in user (console session): the service account acting on
  behalf of a user, and API keys, get 403 `approval_requires_user_session` (K-07-0002 S2).
- An answer comes only from the run's own user (403 `not_run_user`).
- One resume per wait: the status change is the lock, a second one is 409 `run_not_waiting`.
- Audited in the same transaction; the worker continues the run from its checkpoint.
"""

import uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.auth import Actor
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.models.runs import Run
from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import WAITING, RunStatus
from ffcore.runtime.queue import RunQueue


# The runtime does not import the API package (it imports the runtime): same bodies as
# api.common's helpers.
def _conflict(code: str, message: str) -> ApiError:
    return ApiError(409, "conflict_error", code, message)


def _invalid(code: str, message: str) -> ApiError:
    return ApiError(422, "invalid_request_error", code, message)


def needs_user_session(actor: Actor) -> bool:
    return actor.actor_type != "user" or actor.via_service


async def resume_run(
    session: AsyncSession,
    queue: RunQueue,
    settings: Settings,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    actor: Actor,
    decision: str | None = None,
    answer: str | None = None,
    comment: str | None = None,
    request_id: str | None = None,
    ip: str | None = None,
) -> str | None:
    """Queue the run's next attempt with the decision or the answer. Returns the last event id
    of the live stream, so the caller can follow from there (None: nothing streamed yet)."""
    run = await session.scalar(
        select(Run).where(Run.id == run_id, Run.project_id == project_id, Run.deleted_at.is_(None))
    )
    if run is None:
        raise ApiError(404, "not_found_error", "run_not_found", "Run not found.")
    if run.status not in WAITING:
        raise _conflict("run_not_waiting", f"The run is {run.status}, not waiting.")
    resume: dict[str, Any]
    if run.status == RunStatus.waiting_approval:
        if decision is None or answer is not None:
            raise _invalid("decision_required", "This run waits for an approval decision.")
        if needs_user_session(actor):
            raise ApiError(
                403,
                "permission_error",
                "approval_requires_user_session",
                "Approvals are given by a signed-in user, not on someone's behalf.",
            )
        resume = {"decision": decision, "comment": comment, "by": actor.actor_id}
        action = "resolve_approval"
    else:
        if answer is None or decision is not None:
            raise _invalid("answer_required", "This run waits for the user's answer.")
        if actor.actor_id != str(run.user_id):
            raise ApiError(403, "permission_error", "not_run_user", "Only the run's user answers.")
        resume = {"answer": answer}
        action = "answer_run_question"
    changed = await session.execute(
        update(Run)
        .where(Run.id == run.id, Run.status == run.status)
        .values(status=RunStatus.queued)
    )
    if changed.rowcount != 1:
        raise _conflict("run_not_waiting", "The run was resumed already.")
    await write_event(
        session,
        AuditEntry(
            action=action,
            resource_type="run",
            outcome="success",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            project_id=str(project_id),
            resource_id=str(run.id),
            after={"decision": decision} if decision else None,
            request_id=request_id or uuid.uuid4().hex,
            ip=ip,
        ),
    )
    await session.commit()
    after = await _last_entry(settings, run.id)
    if run.channel == "test":
        # 09 r1 MINOR-6: an exam item run goes on in the background class it started in.
        from ffcore.evaluation.runner import is_exam_run
        from ffcore.runtime.queue import get_background_queue

        if await is_exam_run(session, run.id):
            queue = get_background_queue(settings)
    await queue.enqueue(str(run.id), resume)
    return after


async def _last_entry(settings: Settings, run_id) -> str | None:
    """The stream's last id, and the run marked as listened (the resumed attempt checks it)."""
    client = run_events.redis_client(settings)
    try:
        await run_events.mark_listening(client, run_id, settings.run_abandon_grace_s)
        last = await client.xrevrange(run_events.stream_key(run_id), count=1)
    finally:
        await client.aclose()
    if not last:
        return None
    entry_id = last[0][0]
    return entry_id.decode() if isinstance(entry_id, bytes) else entry_id
