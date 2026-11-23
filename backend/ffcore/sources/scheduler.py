"""The `sync` queue (C10) and the sync worker's minute tick, importable without a worker.

`tick` fails runs left `running` past the job timeout (`run_abandoned`: the worker died; the
source can sync again, never silently) and starts a raw run for every active source whose
schedule slot passed (`schedule.due`): a delta, or a full run when the source's last completed
full run is FULL_SYNC_EVERY_DAYS old (R-16-0013 MINOR-1: a permission narrowed at the source
and a deletion only a full run sees reach the index without anyone starting one; D4 applies).
A source with an active run keeps it (the partial unique index); the slot is taken by that run.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from ffcore.core import db
from ffcore.core.config import Settings, get_settings
from ffcore.models.sources import DataSource, SyncRun
from ffcore.sources import engine, schedule
from ffcore.sources.base import SourceError

log = logging.getLogger("ffcore.sources.scheduler")

# A first full sync of a large space takes hours (plan/16); the job may run this long.
JOB_TIMEOUT_S = 12 * 3600
ABANDON_AFTER = timedelta(seconds=JOB_TIMEOUT_S + 3600)
SCHEDULE_ACTOR = "system:schedule"


def scheduled_mode(last_full: datetime | None, now: datetime, every_days: int) -> str:
    """`full` when `every_days` > 0 and no full run completed in the last `every_days` days."""
    if every_days <= 0:
        return "delta"
    if last_full is None or now - last_full >= timedelta(days=every_days):
        return "full"
    return "delta"


class SyncQueue:
    """The `sync` queue for raw runs; the API and the tick enqueue here."""

    def __init__(self, settings: Settings):
        if settings.redis_url is None:
            raise RuntimeError("REDIS_URL is not set; the sync queue needs Redis")
        self._dsn = settings.redis_url.get_secret_value()
        self._queue_name = settings.arq_queue_sync
        self._pool = None

    async def enqueue(self, function: str, *args) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self._dsn))
        job = await self._pool.enqueue_job(function, *args, _queue_name=self._queue_name)
        if job is None:
            raise RuntimeError(f"job {function} was not enqueued")
        return job.job_id


_sync_queue: SyncQueue | None = None


def get_sync_queue(settings: Settings) -> SyncQueue:
    global _sync_queue
    if _sync_queue is None:
        _sync_queue = SyncQueue(settings)
    return _sync_queue


async def tick(
    *, now: datetime | None = None, settings: Settings | None = None, sync_queue=None
) -> dict:
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    started: list[str] = []
    abandoned = 0
    async with db.session_scope() as session:
        stale = (
            await session.scalars(
                select(SyncRun).where(
                    SyncRun.status == "running", SyncRun.started_at < now - ABANDON_AFTER
                )
            )
        ).all()
        for run in stale:
            run.status, run.error, run.ended_at = "failed", "run_abandoned", now
            abandoned += 1
        await session.commit()
        last_started = dict(
            (
                await session.execute(
                    select(SyncRun.data_source_id, func.max(SyncRun.started_at)).group_by(
                        SyncRun.data_source_id
                    )
                )
            ).all()
        )
        last_full = dict(
            (
                await session.execute(
                    select(SyncRun.data_source_id, func.max(SyncRun.ended_at))
                    .where(
                        SyncRun.layer == "raw",
                        SyncRun.mode == "full",
                        SyncRun.status == "completed",
                    )
                    .group_by(SyncRun.data_source_id)
                )
            ).all()
        )
        sources = (
            await session.scalars(
                select(DataSource).where(
                    DataSource.status == "active", DataSource.deleted_at.is_(None)
                )
            )
        ).all()
        runs = []
        for source in sources:
            try:
                plan = schedule.Schedule.model_validate(source.schedule or {"kind": "manual"})
            except ValueError:
                log.error("source_schedule_invalid source=%s", source.id)
                continue
            if not schedule.due(plan, last_started.get(source.id), now):
                continue
            try:
                runs.append(
                    await engine.create_run(
                        session,
                        source,
                        layer="raw",
                        mode=scheduled_mode(
                            last_full.get(source.id), now, settings.full_sync_every_days
                        ),
                        trigger="schedule",
                        requested_by=SCHEDULE_ACTOR,
                    )
                )
            except SourceError:
                continue  # a run is active; the slot is taken by it
        await session.commit()
    queue = sync_queue or get_sync_queue(settings)
    for run in runs:
        try:
            await queue.enqueue(engine.SYNC_RAW_JOB, str(run.id))
            started.append(str(run.id))
        except Exception:
            log.exception("source_schedule_enqueue_failed run=%s", run.id)
            await engine.fail_queued(run.id, "enqueue_failed")
    if abandoned or started:
        log.info("source_tick abandoned=%d started=%d", abandoned, len(started))
    return {"abandoned": abandoned, "started": started}
