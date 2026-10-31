"""How long a run's LangGraph checkpoint lives (FOLLOWUP-116, K-116-0002).

The checkpoint carries the run's model conversation, and so the text of the chunks the model
read (in the user message and in search_documents results; every step is its own checkpoint
version). It is needed only while the run can still go on, so:

- a finished run's thread is deleted with LangGraph's own `adelete_thread`: by the runner when
  the run ends, and by the per-minute sweep for runs that ended elsewhere (cancel API, approval
  expiry) or whose deletion failed; `runs.checkpoint_deleted_at` makes this idempotent;
- deleting a document marks the live runs that showed it as a source (`runs.source_deleted_at`);
  such a run never continues with the deleted text: the runner stops it at its next step or
  resume, the sweep closes the waiting ones (waiting_user has no time limit), each `failed` with
  `source_deleted`, and their threads are deleted.

The text the run left in `run_events` (llm_call.request_messages, answer) is FOLLOWUP-119 (03c).
"""

import logging
import uuid
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy import exists, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.models.runs import Run, RunEvent
from ffcore.runtime.contracts import FINISHED, WAITING, RunEventType, RunStatus, SseEvent

log = logging.getLogger("ffcore.runtime")
SOURCE_DELETED = "source_deleted"
SOURCE_DELETED_MESSAGE = "A source document of this run was deleted; the run cannot go on."
# Runs a run can still continue from: the ones a source delete has to stop.
LIVE = (RunStatus.running, *WAITING)
# A finished run whose thread is still there after this long is reported on every sweep.
OVERDUE = timedelta(hours=24)
SWEEP_BATCH = 200


def _dsn(settings: Settings) -> str:
    from ffcore.runtime.runner import checkpointer_dsn

    return checkpointer_dsn(settings.database_url.get_secret_value())


async def latest_state(settings: Settings, run_id) -> dict[str, Any]:
    """The run's last checkpointed state (tests and diagnostics)."""
    from ffcore.runtime.graph import build_graph

    async with AsyncPostgresSaver.from_conn_string(_dsn(settings)) as saver:
        graph = build_graph().compile(checkpointer=saver)
        return (await graph.aget_state({"configurable": {"thread_id": str(run_id)}})).values


async def delete_thread(settings: Settings, run_id) -> None:
    """Every checkpoint, blob and write of the run (LangGraph; no-op when there are none)."""
    async with AsyncPostgresSaver.from_conn_string(_dsn(settings)) as saver:
        await saver.adelete_thread(str(run_id))


async def purge(session: AsyncSession, settings: Settings, run_id) -> bool:
    """Delete a finished run's thread and stamp it. A failure is logged and left for the sweep:
    the run stays finished, `checkpoint_deleted_at` stays NULL."""
    try:
        await delete_thread(settings, run_id)
    except Exception as exc:  # noqa: BLE001 - any store failure: the sweep tries again
        log.warning("checkpoint_purge_failed run_id=%s error=%s", run_id, type(exc).__name__)
        return False
    await session.execute(
        update(Run)
        .where(Run.id == uuid.UUID(str(run_id)), Run.checkpoint_deleted_at.is_(None))
        .values(checkpoint_deleted_at=func.now())
    )
    await session.commit()
    return True


def _shows_document(document_ids: list[str]):
    """A sources event of the run lists one of the documents (under `selected`, both the always
    retrieval and search_documents); jsonb containment, one test per document."""
    selected = RunEvent.payload["selected"]
    return exists(
        select(1).where(
            RunEvent.run_id == Run.id,
            RunEvent.type == RunEventType.sources.value,
            or_(*(selected.contains([{"document_id": i}]) for i in document_ids)),
        )
    )


async def mark_document_runs(session: AsyncSession, document_ids: Iterable[str]) -> int:
    """In the document delete's transaction: mark the live runs that showed these documents."""
    ids = [str(i) for i in document_ids]
    if not ids:
        return 0
    result = await session.execute(
        update(Run)
        .where(Run.status.in_(LIVE), Run.source_deleted_at.is_(None), _shows_document(ids))
        .values(source_deleted_at=func.now())
        .execution_options(synchronize_session=False)
    )
    if result.rowcount:
        log.info("runs_marked_source_deleted count=%s", result.rowcount)
    return result.rowcount


async def _close_waiting(session: AsyncSession, settings: Settings, redis, run_id) -> bool:
    """A waiting run whose source was deleted: failed / source_deleted with the client's error
    (the same shape as 07's approval expiry). Only a run still waiting is changed."""
    from ffcore.runtime.events import RunEventWriter

    closed = await session.scalar(
        update(Run)
        .where(Run.id == run_id, Run.status.in_(WAITING), Run.source_deleted_at.is_not(None))
        .values(status=RunStatus.failed, error_code=SOURCE_DELETED, ended_at=func.now())
        .returning(Run.id)
    )
    if closed is None:
        await session.rollback()
        return False
    writer = RunEventWriter(session, redis, run_id, ttl_s=settings.run_event_stream_ttl_s)
    await writer.start()
    await writer.record(
        RunEventType.error,
        {"code": SOURCE_DELETED, "status": RunStatus.failed, "message": SOURCE_DELETED_MESSAGE},
        sse=SseEvent.error,
    )
    return True


async def sweep(settings: Settings, *, now: datetime | None = None) -> dict[str, list[str]]:
    """The per-minute job (background agent worker): close waiting runs with a deleted source,
    then delete the threads of finished runs not stamped yet. Returns the run ids it handled."""
    from ffcore.core import db
    from ffcore.runtime import events as run_events

    now = now or datetime.now(UTC)
    done: dict[str, list[str]] = {"source_deleted": [], "purged": []}
    redis = run_events.redis_client(settings)
    try:
        async with db.session_scope() as session:
            waiting = await session.scalars(
                select(Run.id)
                .where(Run.status.in_(WAITING), Run.source_deleted_at.is_not(None))
                # Oldest mark first: a run that keeps failing cannot starve the rest of a batch.
                .order_by(Run.source_deleted_at)
                .limit(SWEEP_BATCH)
            )
            for run_id in waiting.all():
                try:
                    closed = await _close_waiting(session, settings, redis, run_id)
                except Exception as exc:  # noqa: BLE001 - one run's failure (Redis) is its own
                    # The status change is rolled back: the run stays waiting for the next tick.
                    await session.rollback()
                    log.warning(
                        "source_deleted_close_failed run_id=%s error=%s",
                        run_id,
                        type(exc).__name__,
                    )
                    continue
                if closed:
                    done["source_deleted"].append(str(run_id))
                    if await purge(session, settings, run_id):
                        done["purged"].append(str(run_id))
    finally:
        await redis.aclose()
    async with db.session_scope() as session:
        pending = await session.execute(
            select(Run.id, Run.ended_at)
            .where(
                Run.status.in_(FINISHED),
                Run.checkpoint_deleted_at.is_(None),
                or_(Run.ended_at.is_(None), Run.ended_at <= now),
            )
            .order_by(Run.ended_at)
            .limit(SWEEP_BATCH)
        )
        for run_id, ended_at in pending.all():
            if await purge(session, settings, run_id):
                done["purged"].append(str(run_id))
            elif ended_at is not None and now - ended_at > OVERDUE:
                log.error("checkpoint_purge_overdue run_id=%s ended_at=%s", run_id, ended_at)
                # FOLLOWUP-123: visible as an alert too (once per run).
                from ffcore.services import alerts

                await alerts.emit(
                    settings,
                    "checkpoint_purge_overdue",
                    {"run_id": str(run_id), "ended_at": ended_at.isoformat()},
                    dedupe_key=str(run_id),
                )
    return done
