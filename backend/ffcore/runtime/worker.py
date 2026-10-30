"""Agent workers (arq, C10): `llm-interactive` (chat, test panel) and `llm-background` (exams,
batch work). Same code; the queue decides the slot class. Two compose services run them
(K-06a-0002 S9): arq listens to one queue per process.

    arq ffcore.runtime.worker.InteractiveWorker
    arq ffcore.runtime.worker.BackgroundWorker

A job is one run attempt (`run_agent`). When a worker dies, arq hands the job to the next worker
after its timeout and the run continues from its checkpoint (runner.execute is idempotent).
"""

import logging

from ffcore.core import db, tracing
from ffcore.core.config import get_settings
from ffcore.core.logging import configure_logging
from ffcore.core.prompts import PromptStore
from ffcore.runtime import adapters
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.runner import Attempt, AttemptAborted, execute, fail_after_retries
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings

log = logging.getLogger("ffcore.runtime.worker")
# Longest run (cpu 900 s) plus the time to write its end; past it arq retries the job.
JOB_MARGIN_S = 120
MAX_TRIES = 3


def _redis_settings():
    from arq.connections import RedisSettings

    url = get_settings().redis_url
    if url is None:
        raise RuntimeError("REDIS_URL is not set; the agent worker needs Redis")
    return RedisSettings.from_dsn(url.get_secret_value())


def _startup_for(job_class: JobClass):
    async def startup(ctx) -> None:
        settings = get_settings()
        configure_logging(settings)
        if settings.database_url is None:
            raise RuntimeError("DATABASE_URL is not set; the agent worker needs Postgres")
        db.configure(settings.database_url.get_secret_value())
        tracing.init_tracing(settings)
        redis = ctx["redis"]
        window = BackgroundWindow.parse(
            settings.background_window,
            weekends_all_day=settings.background_window_weekends,
            zone=settings.background_window_tz,
        )
        slots = LlmSlots(redis, SlotSettings(slots=settings.llm_slots), window)
        prompts = PromptStore(tracing.get_client())
        ctx["attempt"] = Attempt(
            settings,
            redis,
            db.session_scope,
            adapters.context_factory(settings, redis, slots, prompts, job_class=job_class),
        )
        log.info("agent_worker_started class=%s slots=%s", job_class.value, settings.llm_slots)

    return startup


async def shutdown(ctx) -> None:
    tracing.shutdown_tracing()


async def run_agent(ctx, run_id: str, resume: dict | None = None) -> str:
    """One attempt. A shutdown cancels it (arq queues it again); an infrastructure error retries
    it shortly; after MAX_TRIES the run ends with worker_retries_exhausted."""
    from arq import Retry

    try:
        return await execute(ctx["attempt"], run_id, resume)
    except AttemptAborted as exc:
        if ctx.get("job_try", 1) >= MAX_TRIES:
            await fail_after_retries(ctx["attempt"], run_id, str(exc))
            return "failed"
        raise Retry(defer=2) from exc


def _settings_class(name: str, queue: str, job_class: JobClass) -> type:
    settings = get_settings()
    return type(
        name,
        (),
        {
            "functions": [run_agent],
            "on_startup": _startup_for(job_class),
            "on_shutdown": shutdown,
            "queue_name": queue,
            # A worker takes runs one by one only where the model is one lane; the slot pool
            # is the real limit, so a worker may hold more runs waiting at the slot.
            "max_jobs": max(settings.llm_slots * 2, 2),
            "job_timeout": settings.run_timeout_s + JOB_MARGIN_S,
            "max_tries": MAX_TRIES,
            "redis_settings": _redis_settings(),
        },
    )


def __getattr__(name: str):
    # Built on first use so importing this module never needs Redis or settings.
    if name == "InteractiveWorker":
        return _settings_class(name, get_settings().arq_queue_interactive, JobClass.interactive)
    if name == "BackgroundWorker":
        return _settings_class(name, get_settings().arq_queue_background, JobClass.background)
    raise AttributeError(name)
