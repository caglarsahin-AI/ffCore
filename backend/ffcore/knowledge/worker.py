"""Ingest worker: `arq ffcore.knowledge.worker.WorkerSettings` (queue `ingest`, C10).

Converts in its bounded process pool, gates and chunks, and asks the API for embeddings
(`POST /internal/embed`): this process never loads the embedding model (C10). A job for a
document row the API has not committed yet is retried a few times, then fails loudly.
"""

import logging
import uuid

from ffcore.core import db
from ffcore.core.config import get_settings
from ffcore.core.logging import configure_logging
from ffcore.knowledge import ingest
from ffcore.knowledge.jobs import get_vector_store
from ffcore.models.knowledge import Document

MAX_ROW_WAIT_TRIES = 5
log = logging.getLogger("ffcore.knowledge.worker")


async def startup(ctx) -> None:
    """Model weights before the first job (review r1 MAJOR-6): the tokenizer is needed by every
    document, so without it the worker does not start; a missing Docling or PaddleOCR weight is
    logged with its name and path, and the files that need it fail with `model_missing`."""
    from ffcore.knowledge.models import hf_path, missing

    settings = get_settings()
    configure_logging(settings)  # 02 r1: the same scrubbed logging as the API process
    if not settings.fake_embed:
        hf_path(settings.embed_model)
    for gap in missing(settings.embed_model, settings.rerank_model):
        log.error("model_missing name=%s path=%s (run `make models`)", gap.name, gap.path)


async def ingest_document_job(ctx, document_id: str) -> dict:
    from arq import Retry

    settings = get_settings()
    async with db.session_scope() as session:
        exists = await session.get(Document, uuid.UUID(document_id))
    if exists is None:
        if ctx.get("job_try", 1) < MAX_ROW_WAIT_TRIES:
            raise Retry(defer=2)
        raise LookupError(f"document {document_id} not found after {MAX_ROW_WAIT_TRIES} tries")
    report = await ingest.ingest_document(
        uuid.UUID(document_id),
        settings=settings,
        store=get_vector_store(settings),
        embed_client=ingest.HttpEmbedClient(settings),
    )
    return {"status": report.status, "reused": report.reused, "embedded": report.embedded}


async def reindex_job(ctx, kb_id: str, layer: str, full: bool) -> dict:
    settings = get_settings()
    store = get_vector_store(settings)
    client = ingest.HttpEmbedClient(settings)
    if layer == "gold":
        report = await ingest.reindex_gold(
            uuid.UUID(kb_id), full=full, settings=settings, store=store, embed_client=client
        )
    else:
        report = await ingest.reindex_silver(
            uuid.UUID(kb_id), full=full, settings=settings, store=store, embed_client=client
        )
    return {"documents": report.documents, "reused": report.reused, "embedded": report.embedded}


def _redis_settings():
    from arq.connections import RedisSettings

    url = get_settings().redis_url
    if url is None:
        raise RuntimeError("REDIS_URL is not set; the ingest worker needs Redis")
    return RedisSettings.from_dsn(url.get_secret_value())


class WorkerSettings:
    functions = [ingest_document_job, reindex_job]
    on_startup = startup
    queue_name = get_settings().arq_queue_ingest
    # One document at a time per worker: conversion already runs in its own process pool.
    max_jobs = 1
    job_timeout = 3600
    redis_settings = _redis_settings()
