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

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from redis.exceptions import RedisError
from sqlalchemy import select

from ffcore.api.agents_schemas import (
    SSE_DESCRIPTION,
    AgentKey,
    FeedbackOut,
    FeedbackRequest,
    ResumeRequest,
    RunCreate,
    RunEventList,
    RunEventOut,
    RunList,
    RunOut,
)
from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, invalid, not_found
from ffcore.core import db, tracing
from ffcore.core.audit import AuditEntry, audited, request_context, write_event
from ffcore.core.auth import Actor, RoleRequirement, authorize, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.guardrails.engine import masks_pii_at
from ffcore.guardrails.masking import (
    ContextReveal,
    RedisTokenStore,
    RevealUnavailable,
    count_placeholders,
    log_skipped_policy,
    log_skipped_url,
    log_unresolved,
)
from ffcore.guardrails.service import resolve_policy
from ffcore.guardrails.settings import get_guardrail_settings
from ffcore.models.agents import Agent, AgentVersion
from ffcore.models.identity import ProjectMember
from ffcore.models.knowledge import Document
from ffcore.models.runs import Conversation, Message, Run, RunEvent
from ffcore.runtime import events as run_events
from ffcore.runtime import resume
from ffcore.runtime.contracts import (
    FINISHED,
    Channel,
    RunEventType,
    RunStatus,
    SseEvent,
    TriggerType,
)
from ffcore.runtime.definition import DEFAULT_APPROVER, parse_definition
from ffcore.runtime.queue import RunQueue, get_run_queue

router = APIRouter(prefix="/projects/{project_id}", tags=["runs"], responses=ERROR_RESPONSES)
log = logging.getLogger("ffcore.runtime.feedback")

# Any project member, `user` included (review r1 MAJOR-1): the handler then applies the run
# rule, so a `user` acts on their own runs only. Matrix in tests/integration/test_06a_run_access.
Member = Annotated[Actor, Depends(require_role("user"))]
# Feedback is a platform mutation (F9): edit access; read-only gets 403.
MemberWriter = Annotated[Actor, Depends(require_role("user", write=True))]
OWN_RUN_ONLY = "user"


def not_run_user(message: str) -> ApiError:
    return ApiError(403, "permission_error", "not_run_user", message)


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


def run_out(run: Run, feedback: dict | None = None) -> RunOut:
    return RunOut.model_validate(run, from_attributes=True).model_copy(
        update={"feedback": feedback}
    )


async def _feedback_of(session, run_ids) -> dict:
    rows = await session.execute(
        select(Message.run_id, Message.feedback).where(
            Message.run_id.in_(list(run_ids)), Message.role == "assistant"
        )
    )
    return {run_id: feedback for run_id, feedback in rows}


async def _readable_run(session, request: Request, actor: Actor, project_id, run_id) -> Run:
    """Analysts and above read every run of the project; a `user` reads the runs that ran for
    them (`runs.user_id`, review r2 MAJOR-1). Another user's run is 404: its existence is not
    shown."""
    run = await _run(session, project_id, run_id)
    if _own_runs_only(request) and str(run.user_id) != actor.actor_id:
        raise not_found("run")
    return run


def _own_runs_only(request: Request) -> bool:
    return request.state.grant.role == OWN_RUN_ONLY


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


# A source whose document was deleted keeps its reference (document id and name, for the audit
# trail) but not its breadcrumb (FOLLOWUP-108). Stored events and the Redis stream are append-only,
# so the mask is applied when a sources event is read, on every path that hands one to a client:
# the events list, the replay from run_events and the live Redis stream (review r1 MAJOR-1).
DELETED_BREADCRUMB = "[deleted]"
# Stored `sources` payloads list sources under "selected", the live SSE data under "sources";
# both list the sources blocked at egress under "blocked" (107, r1 MAJOR-7).
_SOURCE_LISTS = ("selected", "sources", "blocked")


def masked_sources(payload: dict, alive: set[str]) -> dict:
    """The payload with the breadcrumb of every source outside `alive` (document ids) masked."""
    out = dict(payload)
    for key in _SOURCE_LISTS:
        if isinstance(payload.get(key), list):
            out[key] = [
                s if s.get("document_id") in alive else {**s, "breadcrumb": DELETED_BREADCRUMB}
                for s in payload[key]
            ]
    return out


async def mask_deleted_sources(session, payloads: list[dict]) -> list[dict]:
    """`sources` payloads, masked against the documents that are not deleted (one query)."""
    ids = {
        str(s["document_id"])
        for payload in payloads
        for key in _SOURCE_LISTS
        for s in payload.get(key) or []
        if s.get("document_id")
    }
    valid = []
    for value in ids:
        try:
            valid.append(UUID(value))
        except ValueError:
            continue  # not a document id: never alive, so masked
    alive: set[str] = set()
    if valid:
        found = await session.scalars(
            select(Document.id).where(Document.id.in_(valid), Document.deleted_at.is_(None))
        )
        alive = {str(i) for i in found.all()}
    return [masked_sources(payload, alive) for payload in payloads]


async def _stored_payloads(session, rows: list[RunEvent]) -> dict[int, dict]:
    sources = [r for r in rows if r.type == RunEventType.sources and r.payload]
    masked = await mask_deleted_sources(session, [r.payload for r in sources])
    out = {r.seq: r.payload for r in rows}
    out.update({r.seq: payload for r, payload in zip(sources, masked, strict=True)})
    return out


async def _mask_live_event(event: str, data: dict) -> dict:
    """The live stream's hook: a sources event read from Redis gets the same mask."""
    if event != SseEvent.sources:
        return data
    async with db.session_scope() as session:
        return (await mask_deleted_sources(session, [data]))[0]


def is_run_owner(run: Run, actor_id: str | None) -> bool:
    """C17 S8 (K-08T1-0002): placeholders are turned back into their values only for the run's
    own user; every other reader (another analyst, an admin, an approver) sees the placeholders,
    as stored. A run started by a key without a user has no console owner."""
    return run.user_id is not None and actor_id is not None and str(run.user_id) == actor_id


async def policy_allows_reveal(session, run: Run) -> bool:
    """False when the run's guardrail policy enforces a `pii` rule on the output: the answer was
    checked with placeholders in it, and its values must not come back after that check."""
    version = await session.get(AgentVersion, run.agent_version_id)
    key = parse_definition(version.definition).guardrail_policy_key
    policy = await resolve_policy(session, run.project_id, key)
    return not masks_pii_at(policy, ("output.pre", "output.stream.delta"))


async def exit_mode(session, run: Run, actor_id: str | None) -> str:
    """`reveal` (owner, policy allows), `policy` (owner, kept by the output pii rule: logged,
    K-08T1-0004) or `keep` (any other reader: placeholders as stored)."""
    if not is_run_owner(run, actor_id):
        return "keep"
    return "reveal" if await policy_allows_reveal(session, run) else "policy"


def skip_counter(run_id: UUID) -> Callable[..., Awaitable[dict]]:
    """The exit hook of an owner whose placeholders the policy keeps: data unchanged, the
    placeholders counted in `detokenize_skipped_policy`."""
    scope = str(run_id)

    async def count(data: dict, event: str | None = None) -> dict:
        log_skipped_policy(scope, count_placeholders(data))
        return data

    return count


def exit_hook(
    redis, run_id: UUID, mode: str, *, after: str | None = None
) -> Callable[..., Awaitable[dict]] | None:
    if mode == "reveal":
        return detokenizer(redis, run_id, after=after)
    return skip_counter(run_id) if mode == "policy" else None


def detokenizer(redis, run_id: UUID, *, after: str | None = None) -> Callable[..., Awaitable[dict]]:
    """The exit reversal of one reader's run events (C17): every string, within the run's token
    scope. A placeholder the scope cannot resolve (never issued, mapping expired after
    PII_TOKEN_TTL_S) stays and is logged with its count (S9); one inside a URL stays and is
    logged (r1 MAJOR-3); live `token` entries share a context, so a URL split over entries is
    seen. A Redis failure is `RevealUnavailable`: the stream ends with an error event (r1
    MINOR-11), never silently. A reader that starts `after` an entry rebuilds the URL line state
    from the token entries up to it; when it cannot, its first line keeps its placeholders (r3
    MINOR-r3-1, KARARLAR ek (d))."""
    reveal = ContextReveal(
        RedisTokenStore(redis, get_guardrail_settings().pii_token_ttl_s), str(run_id)
    )
    scope = str(run_id)
    primed = after in (None, "0-0")

    async def prime() -> None:
        try:
            texts = await run_events.token_texts(redis, run_id, after)
        except (RedisError, OSError):
            texts = None
        if texts is None:
            reveal.fail_closed()
            return
        for text in texts:
            reveal.prime(text)

    async def hook(data: dict, event: str | None = None) -> dict:
        nonlocal primed
        if not primed:
            primed = True
            await prime()
        before = (reveal.unresolved, reveal.skipped_url)
        try:
            out = await reveal.data(data, stream_text=event == SseEvent.token)
        except (RedisError, OSError) as exc:
            raise RevealUnavailable(str(type(exc).__name__)) from None
        log_unresolved(scope, reveal.unresolved - before[0])
        log_skipped_url(scope, reveal.skipped_url - before[1])
        return out

    return hook


def live_transform(reveal: Callable[..., Awaitable[dict]] | None):
    """The live stream's read-time hook: deleted sources masked, then (owner only) reversal."""

    async def transform(event: str, data: dict) -> dict:
        data = await _mask_live_event(event, data)
        return await reveal(data, event) if reveal is not None else data

    return transform


def _replay_rows(
    project_id: UUID, run_id: UUID, reveal: Callable[[dict], Awaitable[dict]] | None = None
):
    """Stored events as SSE, when the live stream has expired; ends with the run's outcome.
    The stored text stays tokenized; `reveal` (the owner's reader) reverses what is sent."""

    async def rows(after_seq: int) -> AsyncIterator[run_events.SseMessage]:
        async with db.session_scope() as session:
            stored = await session.scalars(
                select(RunEvent)
                .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
                .order_by(RunEvent.seq)
            )
            last_seq = after_seq
            rows_all = stored.all()
            payloads = await _stored_payloads(session, rows_all)
            for row in rows_all:
                last_seq = row.seq
                sse = run_events.REPLAY_SSE.get(RunEventType(row.type))
                if sse is None:
                    continue
                data = (
                    {"text": row.payload.get("text", "")}
                    if sse is SseEvent.token
                    else payloads[row.seq]
                )
                if reveal is not None:
                    data = await reveal(data, sse)
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


def _finished(run_id: UUID):
    """Whether the run has ended in Postgres (FOLLOWUP-104: its last events may be stored only)."""

    async def check() -> bool:
        async with db.session_scope() as session:
            status = await session.scalar(select(Run.status).where(Run.id == run_id))
        return status in FINISHED

    return check


def _stream(
    settings: Settings, project_id: UUID, run_id: UUID, after: str | None, *, mode: str
) -> EventStreamResponse:
    async def body() -> AsyncIterator[str]:
        client = run_events.redis_client(settings)
        reveal_data = exit_hook(client, run_id, mode, after=after)
        try:
            async for chunk in run_events.follow(
                client,
                run_id,
                after=after,
                keepalive_s=settings.sse_keepalive_s,
                grace_s=settings.run_abandon_grace_s,
                replay_rows=_replay_rows(project_id, run_id, reveal_data),
                finished=_finished(run_id),
                transform=live_transform(reveal_data),
            ):
                yield chunk
        finally:
            await client.aclose()

    return EventStreamResponse(
        body(), headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


async def _queued_event(session, settings: Settings, run: Run) -> None:
    """The run's first event; its stream id is where the client's stream starts."""
    client = run_events.redis_client(settings)
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
    actor: Member,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
):
    """Queue a run of the published version (or, with channel=test, a given version) and
    stream its events. The run id is the first event (`progress` with `run_id`)."""
    if actor.actor_type != "user":
        raise invalid("run_user_missing", "A run is started by a user (or for one, on behalf).")
    if body.channel == Channel.test:
        # The console's test panel is for agent builders; chat is open to every member.
        await authorize(
            request,
            actor,
            str(project_id),
            RoleRequirement("analyst", write=False, scope="project"),
        )
    if request.state.grant.is_superadmin:
        # The worker searches and calls tools on behalf of this user, where only project
        # membership counts (03a, K-03a-0007): refused here, not halfway through the run.
        member = await session.scalar(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == UUID(actor.actor_id),
            )
        )
        if member is None:
            raise ApiError(
                403,
                "permission_error",
                "run_needs_membership",
                "Runs act on behalf of a project member; add yourself to the project first.",
            )
    agent = await session.scalar(
        select(Agent).where(
            Agent.project_id == project_id, Agent.key == agent_key, Agent.deleted_at.is_(None)
        )
    )
    if agent is None:
        raise not_found("agent")
    if agent.kind == "external":
        # Review r1 MAJOR-2: an external agent's call is not a run (K-06b2-0002 S1); it is
        # reached through the facade only, whatever version rows may exist under its key.
        raise ApiError(
            422,
            "invalid_request_error",
            "external_agent_not_runnable",
            "An external agent is not run here; call it through /v1/chat/completions.",
        )
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
    return _stream(
        settings,
        project_id,
        run.id,
        None,
        mode=await exit_mode(session, run, actor.actor_id),
    )


@router.get("/runs", response_model=RunList)
async def list_runs(
    project_id: UUID,
    request: Request,
    actor: Member,
    session: SessionDep,
    agent_id: UUID | None = None,
    channel: Channel | None = None,
    status: RunStatus | None = None,
    feedback: Annotated[
        Literal["pending", "given"] | None,
        Query(description="pending: completed runs without expert feedback (F9); given: with."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Newest first. A `user` sees the runs that ran for them only."""
    query = select(Run).where(Run.project_id == project_id, Run.deleted_at.is_(None))
    if _own_runs_only(request):
        query = query.where(Run.user_id == UUID(actor.actor_id))
    if feedback is not None:
        reviewed = select(Message.run_id).where(
            Message.role == "assistant", Message.feedback.is_not(None), Message.run_id.is_not(None)
        )
        query = query.where(Run.status == RunStatus.completed)
        query = query.where(
            Run.id.not_in(reviewed) if feedback == "pending" else Run.id.in_(reviewed)
        )
    if agent_id is not None:
        query = query.where(Run.agent_id == agent_id)
    if channel is not None:
        query = query.where(Run.channel == channel)
    if status is not None:
        query = query.where(Run.status == status)
    runs = (await session.scalars(query.order_by(Run.queued_at.desc()).limit(limit))).all()
    feedbacks = await _feedback_of(session, [r.id for r in runs])
    return RunList(items=[run_out(r, feedbacks.get(r.id)) for r in runs])


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(
    project_id: UUID, run_id: UUID, request: Request, actor: Member, session: SessionDep
):
    run = await _readable_run(session, request, actor, project_id, run_id)
    return run_out(run, (await _feedback_of(session, [run.id])).get(run.id))


def _send_score(run: Run, body: FeedbackRequest) -> bool:
    """A categorical Langfuse score on the run's trace (02 client). Delivery is the SDK's,
    asynchronous; its failure is the 02 log line `trace_delivery_failed`. Never fails the
    request: the feedback is stored first."""
    client = tracing.get_client()
    if client is None or run.langfuse_trace_id is None:
        reason = "tracing_off" if client is None else "run_has_no_trace"
        log.warning("trace_delivery_failed kind=score run_id=%s reason=%s", run.id, reason)
        return False
    try:
        client.create_score(
            name="expert_feedback",
            value=body.vote,
            trace_id=run.langfuse_trace_id,
            data_type="CATEGORICAL",
            comment=body.note,
        )
    except Exception as exc:  # noqa: BLE001 - the stored feedback stands either way
        log.error("trace_delivery_failed kind=score run_id=%s error=%s", run.id, type(exc).__name__)
        return False
    return True


@router.post("/runs/{run_id}/feedback", response_model=FeedbackOut)
@audited("give_feedback", "run")
async def give_feedback(
    project_id: UUID,
    run_id: UUID,
    body: FeedbackRequest,
    request: Request,
    actor: MemberWriter,
    session: SessionDep,
):
    """Expert review of a completed run's answer (F9): vote and note go to the answer message
    and to Langfuse as a score. A new vote replaces the previous one (the audit keeps both).
    Edit access; a `user` member rates only their own runs, analysts and above any run."""
    run = await _run(session, project_id, run_id)
    if request.state.grant.role == OWN_RUN_ONLY and actor.actor_id != str(run.user_id):
        raise not_run_user("A user rates only their own runs.")
    if run.status != RunStatus.completed:
        raise conflict("run_not_completed", f"The run is {run.status}; only answers are rated.")
    message = await session.scalar(
        select(Message).where(Message.run_id == run.id, Message.role == "assistant")
    )
    if message is None:
        raise conflict("run_not_completed", "The run has no answer to rate.")
    at = datetime.now(UTC)
    message.feedback = {
        "vote": body.vote,
        "note": body.note,
        "by": actor.actor_id,
        "at": at.isoformat(),
    }
    await session.flush()
    return FeedbackOut(
        run_id=run.id,
        vote=body.vote,
        note=body.note,
        by=actor.actor_id,
        at=at,
        score_sent=_send_score(run, body),
    )


@router.get("/runs/{run_id}/events", response_model=RunEventList)
async def list_run_events(
    project_id: UUID,
    run_id: UUID,
    request: Request,
    actor: Member,
    session: SessionDep,
    after_seq: Annotated[int, Query(ge=0)] = 0,
):
    """Every event of the run in order (from Postgres)."""
    await _readable_run(session, request, actor, project_id, run_id)
    rows = await session.scalars(
        select(RunEvent)
        .where(RunEvent.run_id == run_id, RunEvent.seq > after_seq)
        .order_by(RunEvent.seq)
    )
    events = rows.all()
    payloads = await _stored_payloads(session, events)
    return RunEventList(
        items=[
            RunEventOut(
                seq=r.seq, ts=r.ts, type=r.type, iteration=r.iteration, payload=payloads[r.seq]
            )
            for r in events
        ]
    )


@router.get("/runs/{run_id}/stream", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def stream_run(
    project_id: UUID,
    run_id: UUID,
    request: Request,
    actor: Member,
    session: SessionDep,
    settings: SettingsDep,
    last_event_id: LastEventId = None,
):
    """(Re)attach to a run's events: replay, then live until the run stops or waits."""
    run = await _readable_run(session, request, actor, project_id, run_id)
    return _stream(
        settings,
        project_id,
        run_id,
        last_event_id,
        mode=await exit_mode(session, run, actor.actor_id),
    )


@router.post("/runs/{run_id}/resume", response_class=EventStreamResponse, responses=SSE_RESPONSE)
async def resume_run(
    project_id: UUID,
    run_id: UUID,
    body: ResumeRequest,
    request: Request,
    actor: Member,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
):
    """Continue a waiting run from its checkpoint: a decision for waiting_approval (role
    `approval.assign_to` with edit access, signed-in user only), an answer for waiting_user (the
    run's user). Any other state is 409 `run_not_waiting`. Rules shared with 07: runtime.resume."""
    run = await _run(session, project_id, run_id)
    if run.status == RunStatus.waiting_approval and body.decision is not None:
        version = await session.get(AgentVersion, run.agent_version_id)
        approval = parse_definition(version.definition).approval
        role = approval.assign_to if approval else DEFAULT_APPROVER
        await authorize(
            request, actor, str(project_id), RoleRequirement(role, write=True, scope="project")
        )
    request_id, ip = request_context(request)
    after = await resume.resume_run(
        session,
        queue,
        settings,
        project_id=project_id,
        run_id=run.id,
        actor=actor,
        decision=body.decision,
        answer=body.answer,
        comment=body.comment,
        request_id=request_id,
        ip=ip,
    )
    # The approver sees the placeholders unless the run is their own (S8).
    return _stream(
        settings,
        project_id,
        run.id,
        after,
        mode=await exit_mode(session, run, actor.actor_id),
    )


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    project_id: UUID,
    run_id: UUID,
    request: Request,
    actor: Member,
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
        client = run_events.redis_client(settings)
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
