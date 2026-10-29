"""Run queue (C10): the API enqueues one `run_agent` job per attempt; a dependency so tests can
record jobs instead of needing a worker."""

from typing import Any, Protocol

from ffcore.core.config import Settings


class RunQueue(Protocol):
    async def enqueue(self, run_id: str, resume: dict[str, Any] | None = None) -> str: ...


class ArqRunQueue:
    def __init__(self, settings: Settings) -> None:
        if settings.redis_url is None:
            raise RuntimeError("REDIS_URL is not set; the run queue needs Redis")
        self._dsn = settings.redis_url.get_secret_value()
        self._queue_name = settings.arq_queue_interactive
        self._pool = None

    async def enqueue(self, run_id: str, resume: dict[str, Any] | None = None) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self._dsn))
        # A resumed attempt is a new job: arq keeps finished job ids for a while.
        job = await self._pool.enqueue_job(
            "run_agent", run_id, resume, _queue_name=self._queue_name
        )
        if job is None:
            raise RuntimeError(f"run {run_id} was not enqueued")
        return job.job_id


_queue: RunQueue | None = None


def get_run_queue(settings: Settings) -> RunQueue:
    global _queue
    if _queue is None:
        _queue = ArqRunQueue(settings)
    return _queue
