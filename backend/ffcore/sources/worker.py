"""Sync worker: `arq ffcore.sources.worker.SyncWorkerSettings` (queue `sync`, C10; K-16-0002 S1).

Runs the raw layer of data sources (the only process that talks to a source system) and, once a
minute, the tick (`scheduler.tick`: abandoned runs, due schedules). Silver and gold run on the
ingest worker (`source_layer_job`, registered there): conversion stays in its bounded process
pool and this worker loads no model.
"""

import uuid

from ffcore.core.config import get_settings
from ffcore.core.logging import configure_logging
from ffcore.knowledge.jobs import ArqQueue, get_vector_store
from ffcore.sources import engine, scheduler


async def startup(ctx) -> None:
    configure_logging(get_settings())


async def sync_raw_job(ctx, run_id: str) -> dict:
    await engine.wait_for_run(ctx, uuid.UUID(run_id))
    settings = get_settings()
    return await engine.run_raw(
        uuid.UUID(run_id),
        settings=settings,
        store=get_vector_store(settings),
        ingest_queue=ArqQueue(settings),
    )


async def tick_job(ctx) -> dict:
    return await scheduler.tick()


def _redis_settings():
    from arq.connections import RedisSettings

    url = get_settings().redis_url
    if url is None:
        raise RuntimeError("REDIS_URL is not set; the sync worker needs Redis")
    return RedisSettings.from_dsn(url.get_secret_value())


def _cron_jobs() -> list:
    from arq import cron

    return [cron(tick_job, second=15, unique=True)]


class SyncWorkerSettings:
    functions = [sync_raw_job]
    cron_jobs = _cron_jobs()
    on_startup = startup
    queue_name = get_settings().arq_queue_sync
    # One raw run plus the minute tick: the tick must not wait hours behind a first full sync.
    max_jobs = 2
    job_timeout = scheduler.JOB_TIMEOUT_S
    # `make smoke` reads `<queue>:health-check` (arq writes it at this interval, seconds).
    health_check_interval = 60
    redis_settings = _redis_settings()
