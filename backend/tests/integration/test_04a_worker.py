"""04a slice 6: the arq ingest queue against the compose Redis (queue `ingest`, C10)."""

import asyncio
import os
import uuid

import pytest
from arq.connections import RedisSettings, create_pool
from arq.jobs import Job, JobStatus
from arq.worker import Worker

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest, jobs, worker
from tests.dummy import EMBED_DIM, SETTINGS_03A

PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Fesih bildirim süresi doksan gündür. "
)
EML = (
    "Subject: Bakim raporu\nFrom: bakim@example.test\nDate: Tue, 1 Oct 2024 10:00:00 +0300\n"
    "Content-Type: text/plain; charset=utf-8\n\n" + PROSE * 8
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    if not os.environ.get("REDIS_URL"):
        pytest.fail("REDIS_URL is not set; run in the tools container with redis up")
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        redis_url=os.environ["REDIS_URL"],
        # Its own queue: a live compose worker on `ingest` never takes these jobs (K-04a-0012).
        arq_queue_ingest=f"ingest-test-{uuid.uuid4().hex[:8]}",
        knowledge_storage_dir=str(tmp_path / "storage"),
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def wired(database_url, settings, monkeypatch):
    db.configure(database_url, pooled=False)
    # The worker reads process settings and embeds through the API; here both are local.
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(ingest, "HttpEmbedClient", lambda s: ingest.LocalEmbedClient(s))
    monkeypatch.setattr(jobs, "_queue", None)
    yield
    db.reset()


def make_kb(pg, project_id) -> uuid.UUID:
    kb_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, %s, 'KB', 'BAAI/bge-m3', %s,"
        " 400, 0, true, true, 'BAAI/bge-reranker-v2-m3', 5, 'format-v1', 'test')",
        (kb_id, project_id, f"kb-{kb_id.hex[:8]}", EMBED_DIM),
    )
    return kb_id


async def _drain(settings: Settings) -> None:
    redis = RedisSettings.from_dsn(settings.redis_url.get_secret_value())
    runner = Worker(
        functions=worker.WorkerSettings.functions,
        queue_name=settings.arq_queue_ingest,
        redis_settings=redis,
        burst=True,
        poll_delay=0.2,
        handle_signals=False,
    )
    try:
        await runner.async_run()
    finally:
        await runner.close()


def test_04a_upload_job_runs_in_worker(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())

    async def go():
        async with db.session_scope() as session:
            document, _ = await ingest.register_upload(
                session,
                kb_id,
                # E-mail converts with the standard library: the worker's real path (bounded
                # converter process) without model weights (DRIFT-85).
                filename="a.eml",
                data=EML.encode(),
                acl_roles=["analyst"],
                acl_users=[],
                created_by="test",
                settings=settings,
            )
            await session.commit()
        job_id = await jobs.get_queue(settings).enqueue("ingest_document_job", str(document.id))
        await _drain(settings)
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url.get_secret_value()))
        result = await Job(job_id, pool, _queue_name=settings.arq_queue_ingest).result(timeout=5)
        await pool.aclose()
        return document.id, result

    document_id, result = asyncio.run(go())
    assert result["status"] == "indexed" and result["embedded"] > 0
    (status,) = pg.execute("SELECT status FROM documents WHERE id = %s", (document_id,)).fetchone()
    assert status == "indexed"


def test_04a_job_for_missing_row_retries_then_fails_loud(settings):
    async def go():
        missing = str(uuid.uuid4())
        job_id = await jobs.get_queue(settings).enqueue("ingest_document_job", missing)
        await _drain(settings)
        pool = await create_pool(RedisSettings.from_dsn(settings.redis_url.get_secret_value()))
        job = Job(job_id, pool, _queue_name=settings.arq_queue_ingest)
        info = await job.result_info()
        status = await job.status()
        await pool.aclose()
        return info, status

    info, status = asyncio.run(go())
    assert status == JobStatus.complete
    assert info.success is False and isinstance(info.result, LookupError)
    assert info.job_try == worker.MAX_ROW_WAIT_TRIES
