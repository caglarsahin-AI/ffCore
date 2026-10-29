"""Runs: start an agent, follow it as server-sent events, resume, cancel and read back (06a).

A run is one arq job on the agent worker (C10); the API never runs the graph. Events go to
Postgres (`run_events`, durable) and a Redis Stream (live, replay for late or reconnecting
clients; K-06a-0002 S2). Closing the stream never cancels a run: only POST .../cancel does
(K-06a-0002 S8); a running run with no subscriber for RUN_ABANDON_GRACE_S is `abandoned`.

Starting a run and answering its question are chat, open in read-only access mode like 11's
chat (brief 03 read-only exceptions). Approving is a platform mutation: resume with a decision
checks the definition's `approval.assign_to` role and `edit` access in the handler, because
the body decides which rule applies (write-flag scan exemption, with this reason).
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, update

from ffcore.api.agents_schemas import (
    SSE_DESCRIPTION,
    AgentKey,
    ResumeRequest,
    RunCreate,
    RunEventList,
    RunEventOut,
    RunList,
    RunOut,
)
from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, invalid, not_found
from ffcore.core import db
from ffcore.core.audit import AuditEntry, request_context, write_event
from ffcore.core.auth import Actor, RoleRequirement, authorize, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.runs import Conversation, Message, Run, RunEvent
from ffcore.runtime import events as run_events
from ffcore.runtime.contracts import (
    FINISHED,
    WAITING,
    Channel,
    RunEventType,
    RunStatus,
    SseEvent,
    TriggerType,
)
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.queue import RunQueue, get_run_queue

router = APIRouter(prefix="/projects/{project_id}", tags=["runs"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
LastEventId = Annotated[
    str | None,
    Header(alias="Last-Event-ID", description="Continue after this event id (reconnect)."),
]


def queue_dependency(settings: SettingsDep) -> RunQueue:
    return get_run_queue(settings)


QueueDep = Annotated[RunQueue, Depends(queue_dependency)]


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"


SSE_RESPONSE = {
    200: {
        "description": SSE_DESCRIPTION,
        "content": {"text/event-stream": {"schema": {"type": "string"}}},
    }
}


def _redis(settings: Settings):
    if settings.redis_url is None:
        raise ApiError(
            503, "api_error", "redis_unavailable", "The run event stream is not configured."
        )
    return aioredis.from_url(settings.redis_url.get_secret_value())


def run_out(run: Run) -> RunOut:
    return RunOut.model_validate(run, from_attributes=True)


async def _run(session, project_id: UUID, run_id: UUID) -> Run:
    run = await session.scalar(
        select(Run).where(Run.id == run_id, Run.project_id == project_id, Run.deleted_at.is_(None))
    )
    if run is None:
        raise not_found("run")
    return run


async def _audit(
    session, request: Request, actor: Actor, project_id, action: str, run_id, after=None
):
    request_id, ip = request_context(request)
    await write_event(
        session,
        AuditEntry(
            action=action,
            resource_type="run",
            outcome="success",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            project_id=str(project_id),
            resource_id=str(run_id),
            before=None,
            after=after,
            request_id=request_id,
            ip=ip,
        ),
    )


def _replay_rows(project_id: UUID, run_id: UUID):
    """Stored events as SSE, when the live stream has expired; ends with the run's outcome."""

    async def rows(after_seq: int) -> AsyncIterator[run_events.SseMessage]:
        async with db.session_scope() as session:
            stored = await session.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                .order_by(RunEvent.seq)
            )
            last_seq = after_seq
            for row in stored.all():
                last_seq = row.seq
                sse = run_events.REPLAY_SSE.get(RunEventType(row.type))
                if sse is None:
                    continue
                data = (
                    {"text": row.payload.get("text", "")} if sse is SseEvent.token else row.payload
                )
                yield run_events.SseMessage(f"{row.seq}-0", sse, data)
            run = await _run(session, project_id, run_id)
            if run.status == RunStatus.completed:
                yield run_events.SseMessage(
                    f"{last_seq}-1",
                    SseEvent.done,
                    {
                        "run_id": str(run.id),
                        "status": run.status,
                        "outcome_label": run.outcome_label,
                    },
                )

    return rows


def _stream(
    settings: Settings, project_id: UUID, run_id: UUID, after: str | None
) -> EventStreamResponse:
    async def body() -> AsyncIterator[str]:
        client = _redis(settings)
        try:
            async for chunk in run_events.follow(
                client,
                run_id,
                after=after,
                keepalive_s=settings.sse_keepalive_s,
                grace_s=settings.run_abandon_grace_s,
                replay_rows=_replay_rows(project_id, run_id),
            ):
                yield chunk
        finally:
            await client.aclose()

    return EventStreamResponse(
        body(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


async def _queued_event(session, settings: Settings, run: Run) -> None:
    """The run's first event; its stream id is where the client's stream starts."""
    client = _redis(settings)
    try:
        writer = run_events.RunEventWriter(
            session, client, run.id, ttl_s=settings.run_event_stream_ttl_s
        )
        await writer.start()
        payload = {
            "run_id": str(run.id),
            "status": run.status,
            "conversation_id": str(run.conversation_id) if run.conversation_id else None,
        }
        await writer.record(RunEventType.queued, payload, sse=SseEvent.progress)
        await run_events.mark_listening(client, run.id, settings.run_abandon_grace_s)
    finally:
        await client.aclose()


@router.post("/agents/{agent_key}/runs", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def create_run(
    project_id: UUID,
    agent_key: AgentKey,
    body: RunCreate,
    request: Request,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
):
    """Queue a run of the published version (or, with channel=test, a given version) and
    stream its events. The run id is the first event (`progress` with `run_id`)."""
    if actor.actor_type != "user":
        raise invalid("run_user_missing", "A run is started by a user (or for one, on behalf).")
    agent = await session.scalar(
        select(Agent).where(
            Agent.project_id == project_id, Agent.key == agent_key, Agent.deleted_at.is_(None)
        )
    )
    if agent is None:
        raise not_found("agent")
    if body.version is not None:
        if body.channel != Channel.test:
            raise invalid("version_needs_test_channel", "A version is chosen only in channel=test.")
        version = await session.scalar(
            select(AgentVersion).where(
                AgentVersion.agent_id == agent.id, AgentVersion.version == body.version
            )
        )
        if version is None:
            raise not_found("version")
    else:
        if agent.current_version_id is None:
            raise ApiError(
                404, "not_found_error", "agent_not_published", "The agent is not published."
            )
        version = await session.get(AgentVersion, agent.current_version_id)
    definition = parse_definition(version.definition)
    unknown = sorted(set(body.variables) - {v.key for v in definition.variables})
    if unknown:
        raise invalid("variable_unknown", f"Unknown variables: {unknown}")

    user_id = UUID(actor.actor_id)
    if body.conversation_id is not None:
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.id == body.conversation_id,
                Conversation.project_id == project_id,
                Conversation.agent_id == agent.id,
                Conversation.user_id == user_id,
                Conversation.deleted_at.is_(None),
            )
        )
        if conversation is None:
            raise not_found("conversation")
    else:
        conversation = Conversation(
            project_id=project_id,
            agent_id=agent.id,
            user_id=user_id,
            title=body.input[:80],
            created_by=actor.actor_id,
        )
        session.add(conversation)
        await session.flush()
    run = Run(
        project_id=project_id,
        agent_id=agent.id,
        agent_version_id=version.id,
        conversation_id=conversation.id,
        user_id=user_id,
        channel=body.channel,
        trigger_type=TriggerType.chat,
        status=RunStatus.queued,
        input=body.input,
        variables=body.variables,
        created_by=actor.actor_id,
    )
    session.add(run)
    await session.flush()
    session.add(
        Message(conversation_id=conversation.id, run_id=run.id, role="user", content=body.input)
    )
    await _audit(
        session,
        request,
        actor,
        project_id,
        "start_run",
        run.id,
        after={"agent_id": str(agent.id), "version": version.version, "channel": body.channel},
    )
    await session.commit()
    await _queued_event(session, settings, run)
    await queue.enqueue(str(run.id))
    return _stream(settings, project_id, run.id, None)


@router.get("/runs", response_model=RunList)
async def list_runs(
    project_id: UUID,
    actor: Reader,
    session: SessionDep,
    agent_id: UUID | None = None,
    channel: Channel | None = None,
    status: RunStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Newest first."""
    query = select(Run).where(Run.project_id == project_id, Run.deleted_at.is_(None))
    if agent_id is not None:
        query = query.where(Run.agent_id == agent_id)
    if channel is not None:
        query = query.where(Run.channel == channel)
    if status is not None:
        query = query.where(Run.status == status)
    rows = await session.scalars(query.order_by(Run.queued_at.desc()).limit(limit))
    return RunList(items=[run_out(r) for r in rows.all()])


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(project_id: UUID, run_id: UUID, actor: Reader, session: SessionDep):
    return run_out(await _run(session, project_id, run_id))


@router.get("/runs/{run_id}/events", response_model=RunEventList)
async def list_run_events(
    project_id: UUID,
    run_id: UUID,
    actor: Reader,
    session: SessionDep,
    after_seq: Annotated[int, Query(ge=0)] = 0,
):
    """Every event of the run in order (from Postgres)."""
    await _run(session, project_id, run_id)
    rows = await session.scalars(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
        .order_by(RunEvent.seq)
    )
    return RunEventList(
        items=[
            RunEventOut(seq=r.seq, ts=r.ts, type=r.type, iteration=r.iteration, payload=r.payload)
            for r in rows.all()
        ]
    )


@router.get("/runs/{run_id}/stream", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def stream_run(
    project_id: UUID,
    run_id: UUID,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
    last_event_id: LastEventId = None,
):
    """(Re)attach to a run's events: replay, then live until the run stops or waits."""
    await _run(session, project_id, run_id)
    return _stream(settings, project_id, run_id, last_event_id)


async def _last_entry(settings: Settings, run_id) -> str | None:
    client = _redis(settings)
    try:
        last = await client.xrevrange(run_events.stream_key(run_id), count=1)
    finally:
        await client.aclose()
    if not last:
        return None
    entry_id = last[0][0]
    return entry_id.decode() if isinstance(entry_id, bytes) else entry_id


@router.post("/runs/{run_id}/resume", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def resume_run(
    project_id: UUID,
    run_id: UUID,
    body: ResumeRequest,
    request: Request,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
):
    """Continue a waiting run from its checkpoint: a decision for waiting_approval (role
    `approval.assign_to` with edit access), an answer for waiting_user (the run's user). Any
    other state is 409 `run_not_waiting`."""
    run = await _run(session, project_id, run_id)
    if run.status not in WAITING:
        raise conflict("run_not_waiting", f"The run is {run.status}, not waiting.")
    resume: dict[str, Any]
    if run.status == RunStatus.waiting_approval:
        if body.decision is None or body.answer is not None:
            raise invalid("decision_required", "This run waits for an approval decision.")
        version = await session.get(AgentVersion, run.agent_version_id)
        approval = parse_definition(version.definition).approval
        role = approval.assign_to if approval else "admin"
        await authorize(
            request, actor, str(project_id), RoleRequirement(role, write=True, scope="project")
        )
        resume = {"decision": body.decision, "comment": body.comment, "by": actor.actor_id}
        action = "resolve_approval"
    else:
        if body.answer is None or body.decision is not None:
            raise invalid("answer_required", "This run waits for the user's answer.")
        if actor.actor_id != str(run.user_id):
            raise ApiError(403, "permission_error", "not_run_user", "Only the run's user answers.")
        resume = {"answer": body.answer}
        action = "answer_run_question"
    # One resume per wait: the state change is the lock (a second click gets 409).
    changed = await session.execute(
        update(Run)
        .where(Run.id == run.id, Run.status == run.status)
        .values(status=RunStatus.queued)
    )
    if changed.rowcount != 1:
        raise conflict("run_not_waiting", "The run was resumed already.")
    await _audit(
        session,
        request,
        actor,
        project_id,
        action,
        run.id,
        after={"decision": body.decision} if body.decision else None,
    )
    await session.commit()
    after = await _last_entry(settings, run.id)
    client = _redis(settings)
    try:
        await run_events.mark_listening(client, run.id, settings.run_abandon_grace_s)
    finally:
        await client.aclose()
    await queue.enqueue(str(run.id), resume)
    return _stream(settings, project_id, run.id, after)


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    project_id: UUID,
    run_id: UUID,
    request: Request,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
):
    """Stop a run at its next step boundary: the run's user or a project admin."""
    run = await _run(session, project_id, run_id)
    if actor.actor_id != str(run.user_id):
        await authorize(
            request, actor, str(project_id), RoleRequirement("admin", write=True, scope="project")
        )
    if run.status in FINISHED:
        raise conflict("run_finished", f"The run is {run.status} already.")
    now = datetime.now(UTC)
    if run.status == RunStatus.running:
        run.cancel_requested_at = now
    else:
        # Queued or waiting: no worker holds it, the cancel is final right away.
        run.status, run.error_code, run.ended_at = RunStatus.cancelled, "cancelled", now
        run.cancel_requested_at = now
    await _audit(session, request, actor, project_id, "cancel_run", run.id)
    await session.commit()
    if run.status == RunStatus.cancelled:
        client = _redis(settings)
        try:
            writer = run_events.RunEventWriter(
                session, client, run.id, ttl_s=settings.run_event_stream_ttl_s
            )
            await writer.start()
            await writer.record(
                RunEventType.error,
                {"code": "cancelled", "status": RunStatus.cancelled, "message": None},
                sse=SseEvent.error,
            )
        finally:
            await client.aclose()
    await session.refresh(run)
    return run_out(run)
