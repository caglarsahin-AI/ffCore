"""One attempt of a run on the agent worker: start, resume or continue after a crash.

A run is one arq job (C10). The job is idempotent: a finished run is left alone; a run whose
worker died mid-way continues from its last checkpoint (`thread_id` = run id); a waiting run
continues only with a resume value. Status changes are written to `runs` as they happen, so
GET /runs/{id} always tells the truth, and the client's stream always ends with done, error,
approval_required or question.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from redis import exceptions as redis_errors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core import tracing
from ffcore.core.config import Settings
from ffcore.models.agents import AgentVersion
from ffcore.models.runs import Message, Run, RunEvent
from ffcore.runtime import checkpoints
from ffcore.runtime.contracts import FINISHED, WAITING, RunEventType, RunStatus, SseEvent
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.events import RunEventWriter, is_listened
from ffcore.runtime.graph import build_graph
from ffcore.runtime.state import RunContext, StopRun

log = logging.getLogger("ffcore.runtime")
CHECKPOINT_SCHEMA = "checkpoints"
LIMIT_MESSAGE = "The run stopped at a limit before it finished."
# The worker's own infrastructure going away (shutdown, Redis connection): the attempt stops,
# the run does not fail; it stays `running` and the next attempt continues from its checkpoint.
INFRASTRUCTURE_ERRORS = (redis_errors.ConnectionError, redis_errors.TimeoutError)


class AttemptAborted(Exception):
    """This attempt could not finish for reasons outside the run; the job is tried again."""


def checkpointer_dsn(database_url: str) -> str:
    """psycopg DSN with the checkpoints schema first on the search path (U1)."""
    plain = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    separator = "&" if "?" in plain else "?"
    return f"{plain}{separator}options=-csearch_path%3D{CHECKPOINT_SCHEMA}"


async def setup_checkpointer(database_url: str) -> None:
    """The saver's own idempotent setup, inside the schema Alembic 06a created (S12)."""
    async with AsyncPostgresSaver.from_conn_string(checkpointer_dsn(database_url)) as saver:
        await saver.setup()


@dataclass
class Attempt:
    """What the worker needs besides the run id; built once per worker process."""

    settings: Settings
    redis: Any
    session_factory: Callable[[], AsyncSession]
    # Builds the ports and system prompt parts for a run (adapters.build_context).
    context_factory: Callable[..., Any]


def _now() -> datetime:
    return datetime.now(UTC)


async def _boundary_factory(attempt: Attempt, session: AsyncSession, run: Run, deadline: float):
    async def boundary(step: str) -> None:
        cancelled, source_deleted = (
            await session.execute(
                select(Run.cancel_requested_at, Run.source_deleted_at)
                .where(Run.id == run.id)
                .execution_options(populate_existing=True)
            )
        ).one()
        if cancelled is not None:
            raise StopRun(RunStatus.cancelled, "cancelled", step=step)
        if source_deleted is not None:
            # A document this run showed was deleted: never go on with its text (FOLLOWUP-116).
            raise StopRun(
                RunStatus.failed,
                checkpoints.SOURCE_DELETED,
                checkpoints.SOURCE_DELETED_MESSAGE,
                step=step,
            )
        if not await is_listened(attempt.redis, run.id):
            # Nobody followed the run for RUN_ABANDON_GRACE_S (K-06a-0002 S8).
            raise StopRun(RunStatus.abandoned, "abandoned", step=step)
        if time.monotonic() > deadline:
            raise StopRun(
                RunStatus.failed, "limit_reached", LIMIT_MESSAGE, limit="run_timeout_s", step=step
            )

    return boundary


# A wait starts with the request and ends with its answer (K-07-0002 S6: waiting is not run time).
WAIT_STARTS = {RunEventType.approval_requested.value, RunEventType.question.value}
WAIT_ENDS = {RunEventType.approval_resolved.value, RunEventType.user_answer.value}


async def _waited_s(session: AsyncSession, run_id, now: datetime) -> float:
    """Seconds the run spent in waiting_approval / waiting_user, from its own events; a wait
    still open is the one this attempt resumes, it ends now."""
    rows = await session.execute(
        select(RunEvent.type, RunEvent.ts)
        .where(RunEvent.run_id == run_id, RunEvent.type.in_(WAIT_STARTS | WAIT_ENDS))
        .order_by(RunEvent.seq)
    )
    waited, since = 0.0, None
    for kind, ts in rows:
        if kind in WAIT_STARTS:
            since = ts
        elif since is not None:
            waited += (ts - since).total_seconds()
            since = None
    if since is not None:
        waited += (now - since).total_seconds()
    return waited


def _timing_fields(run: Run, timing: dict[str, int]) -> None:
    total = int((run.ended_at - run.started_at).total_seconds() * 1000)
    parts = {k: timing.get(k, 0) for k in ("model", "tool", "retrieval")}
    run.model_ms, run.tool_ms, run.retrieval_ms = parts["model"], parts["tool"], parts["retrieval"]
    run.unaccounted_ms = max(total - sum(parts.values()), 0)
    longest = {k: timing.get(f"{k}_max", 0) for k in parts}
    run.slowest_step = max(longest, key=longest.get) if any(longest.values()) else None


async def execute(attempt: Attempt, run_id: str, resume: dict[str, Any] | None = None) -> str:
    """Returns the run's status after this attempt."""
    settings = attempt.settings
    async with attempt.session_factory() as session:
        run = await session.get(Run, uuid.UUID(run_id))
        if run is None:
            raise LookupError(f"run {run_id} not found")
        if run.status in FINISHED:
            return run.status
        if run.status in WAITING and resume is None:
            # A job for a waiting run without a resume value is a duplicate: nothing to do.
            return run.status
        version = await session.get(AgentVersion, run.agent_version_id)
        definition = parse_definition(version.definition)
        events = RunEventWriter(
            session, attempt.redis, run.id, ttl_s=settings.run_event_stream_ttl_s
        )
        await events.start()
        if run.source_deleted_at is not None:
            # A resume (or a crashed attempt) of a run whose source was deleted: it ends before
            # the graph runs, so neither the model nor an approved tool sees the deleted text.
            return await _stop(
                session,
                run.id,
                events,
                {},
                StopRun(
                    RunStatus.failed,
                    checkpoints.SOURCE_DELETED,
                    checkpoints.SOURCE_DELETED_MESSAGE,
                ),
                settings,
            )
        if run.started_at is None:
            run.started_at = _now()
            run.queue_wait_ms = int((run.started_at - run.queued_at).total_seconds() * 1000)
        run.status = RunStatus.running
        await session.commit()

        timeout_s = definition.limits.run_timeout_s or settings.run_timeout_s
        now = _now()
        worked_s = (now - run.started_at).total_seconds() - await _waited_s(session, run.id, now)
        deadline = time.monotonic() + max(timeout_s - worked_s, 0)
        boundary = await _boundary_factory(attempt, session, run, deadline)
        try:
            ctx: RunContext = await attempt.context_factory(
                session=session, run=run, definition=definition, events=events, boundary=boundary
            )
        except Exception as exc:
            # Prompt, policy, tool layer or model set-up failed: a coded end, never stuck running.
            code = getattr(exc, "code", None) or "run_error"
            log.warning("run_setup_failed run_id=%s code=%s", run.id, code)
            return await _stop(
                session,
                run.id,
                events,
                {},
                StopRun(RunStatus.failed, code, getattr(exc, "message", None)),
                settings,
            )
        config = {"configurable": {"thread_id": str(run.id)}}
        with (
            tracing.run_attributes(
                str(run.id), ctx.user_id, str(run.project_id), tags=[run.channel, "agent"]
            ),
            tracing.span("agent-run", metadata={"run_id": str(run.id)}),
        ):
            client = tracing.get_client()
            if client is not None and run.langfuse_trace_id is None:
                # One trace per run (02); later attempts of the same run add to it.
                run.langfuse_trace_id = client.get_current_trace_id()
                await session.commit()
            return await _attempt_graph(
                session, run, events, ctx, config, settings, deadline, resume
            )


async def _attempt_graph(session, run, events, ctx, config, settings, deadline, resume) -> str:
    interrupted: dict[str, Any] | None = None
    async with AsyncPostgresSaver.from_conn_string(
        checkpointer_dsn(settings.database_url.get_secret_value())
    ) as saver:
        graph = build_graph().compile(checkpointer=saver)
        snapshot = await graph.aget_state(config)
        if resume is not None:
            graph_input: Any = Command(resume=resume)
        elif snapshot.next:
            graph_input = None  # the worker stopped mid-way: continue from the checkpoint
            # Said to the client: tokens of the interrupted step come again from its start.
            await events.record(
                RunEventType.progress,
                {"attempt": "resumed_after_worker_stop", "step": snapshot.next[0]},
                sse=SseEvent.progress,
            )
        else:
            graph_input = {"question": run.input}
        stop: StopRun | None = None
        try:
            async with asyncio.timeout(max(deadline - time.monotonic(), 0.001)):
                async for update in graph.astream(
                    graph_input, config, stream_mode="updates", context=ctx
                ):
                    if "__interrupt__" in update:
                        interrupted = update["__interrupt__"][0].value
        except TimeoutError:
            stop = StopRun(RunStatus.failed, "limit_reached", LIMIT_MESSAGE, limit="run_timeout_s")
        except StopRun as raised:
            stop = raised
        except INFRASTRUCTURE_ERRORS as exc:
            log.warning("run_attempt_aborted run_id=%s error=%s", run.id, type(exc).__name__)
            raise AttemptAborted(type(exc).__name__) from exc
        except Exception as exc:
            code = getattr(exc, "code", None) or "run_error"
            log.exception("run_failed run_id=%s code=%s", run.id, code)
            stop = StopRun(RunStatus.failed, code, getattr(exc, "message", None))
        # The last checkpoint: what the run had done when it stopped or finished.
        final = (await graph.aget_state(config)).values
    if stop is not None:
        return await _stop(session, run.id, events, final, stop, settings)

    if interrupted is not None:
        run.status = (
            RunStatus.waiting_approval
            if interrupted.get("kind") == "approval"
            else RunStatus.waiting_user
        )
        await session.commit()
        return run.status
    await _complete(session, run, events, final, settings)
    return run.status


async def fail_after_retries(attempt: Attempt, run_id: str, reason: str) -> None:
    """The last attempt was aborted too: the run ends with a coded error, never stuck running."""
    async with attempt.session_factory() as session:
        run = await session.get(Run, uuid.UUID(run_id))
        if run is None or run.status in FINISHED:
            return
        events = RunEventWriter(
            session, attempt.redis, run.id, ttl_s=attempt.settings.run_event_stream_ttl_s
        )
        await events.start()
        await _stop(
            session,
            run.id,
            events,
            {},
            StopRun(RunStatus.failed, "worker_retries_exhausted", None, detail=reason),
            attempt.settings,
        )


async def _complete(
    session: AsyncSession, run: Run, events: RunEventWriter, final: dict, settings: Settings
) -> None:
    run.status = RunStatus.completed
    run.output = final.get("answer")
    run.outcome_label = final.get("outcome")
    run.confidence = final.get("confidence")
    usage = final.get("usage") or {}
    run.tokens_in, run.tokens_out = usage.get("prompt_tokens"), usage.get("completion_tokens")
    run.ended_at = _now()
    _timing_fields(run, final.get("timing") or {})
    if run.conversation_id is not None:
        session.add(
            Message(
                conversation_id=run.conversation_id,
                run_id=run.id,
                role="assistant",
                content=run.output or "",
                sources=[
                    {k: v for k, v in s.items() if k != "text"} for s in final.get("sources") or []
                ],
            )
        )
    await session.commit()
    await events.live(
        SseEvent.done,
        {
            "run_id": str(run.id),
            "status": run.status,
            "outcome_label": run.outcome_label,
            "confidence": run.confidence,
        },
    )
    # The run is over: its checkpoint (and the chunk text in it) goes (FOLLOWUP-116).
    await checkpoints.purge(session, settings, run.id)


async def _stop(
    session: AsyncSession,
    run_id: uuid.UUID,
    events: RunEventWriter,
    final: dict,
    stop: StopRun,
    settings: Settings,
) -> str:
    # The id is taken before: after the rollback every loaded object is expired.
    await session.rollback()
    run = await session.get(Run, run_id, populate_existing=True)
    run.status = stop.status
    run.error_code = stop.code
    partial = stop.extra.get("partial")
    if partial:
        run.output, run.partial = partial, True
    reference = stop.extra.get("reference_id")
    if reference:
        run.reference_id = uuid.UUID(str(reference))
    run.ended_at = _now()
    if run.started_at is not None:
        _timing_fields(run, final.get("timing") or {})
    await session.commit()
    payload = {
        "code": stop.code,
        "status": stop.status,
        "message": stop.message,
        "reference_id": str(run.reference_id) if run.reference_id else None,
        **{k: v for k, v in stop.extra.items() if k in ("limit", "step", "detail")},
    }
    await events.record(RunEventType.error, payload, sse=SseEvent.error)
    await checkpoints.purge(session, settings, run_id)
    return stop.status
