"""Ingest queue (C10 queue name `ingest`, one library: arq) and the vector store selection.

The API enqueues; the worker (`arq ffcore.knowledge.worker.WorkerSettings`) converts, gates,
chunks and asks the API for embeddings. The queue is a dependency so tests can record jobs.
"""

from typing import Protocol

from ffcore.core.config import Settings
from ffcore.knowledge.vectorstore.base import VectorStore

INGEST_QUEUE = "ingest"


class JobQueue(Protocol):
    async def enqueue(self, function: str, *args) -> str: ...


class ArqQueue:
    def __init__(self, settings: Settings):
        if settings.redis_url is None:
            raise RuntimeError("REDIS_URL is not set; the ingest queue needs Redis")
        self._dsn = settings.redis_url.get_secret_value()
        self._pool = None

    async def enqueue(self, function: str, *args) -> str:
        from arq import create_pool
        from arq.connections import RedisSettings

        if self._pool is None:
            self._pool = await create_pool(RedisSettings.from_dsn(self._dsn))
        job = await self._pool.enqueue_job(function, *args, _queue_name=INGEST_QUEUE)
        if job is None:
            raise RuntimeError(f"job {function} was not enqueued")
        return job.job_id


_queue: JobQueue | None = None


def get_queue(settings: Settings) -> JobQueue:
    global _queue
    if _queue is None:
        _queue = ArqQueue(settings)
    return _queue


def get_vector_store(settings: Settings) -> VectorStore:
    """VECTOR_BACKEND decides, nothing else (ARCH-10): no automatic choice, no fallback."""
    if settings.vector_backend == "qdrant":
        from ffcore.knowledge.vectorstore.qdrant import QdrantStore

        return QdrantStore(settings)
    from ffcore.knowledge.vectorstore.pgvector import PgVectorStore

    return PgVectorStore()
