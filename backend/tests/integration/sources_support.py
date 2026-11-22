"""16 integration fixtures: a project with a knowledge base, the data source API with recording
queues, and `drain()` that runs what the sync and ingest workers would (raw on the sync queue,
silver/gold on the ingest queue) in this process, with the weightless converter and FAKE_EMBED.

The network folder is a real directory under a temporary FS_SOURCES_BASE (plan/16: "ağ klasörü
gerçek dizinle"); no source system is contacted.
"""

import asyncio
import os
import uuid
from pathlib import Path

import pytest

from ffcore.api.knowledge import queue_dependency
from ffcore.api.sources import ingest_queue_dependency, sync_queue_dependency
from ffcore.core import db
from ffcore.knowledge import ingest, jobs
from ffcore.sources import engine
from tests.converters import convert_without_weights

API = "/api/v1"
PROSE = (
    "Bu belge kurum içi süreçleri anlatır ve her adımın sorumlusunu açıkça belirtir. "
    "Başvurular yazılı yapılır, yanıt süresi on iş günüdür ve kayıt altına alınır. "
)


class RecordingQueue:
    def __init__(self):
        self.jobs: list[tuple] = []

    async def enqueue(self, function, *args):
        self.jobs.append((function, *args))
        return f"job-{len(self.jobs)}"


def document_text(title: str, marker: str = "") -> str:
    return f"# {title}\n\n" + (PROSE + f"{marker} ") * 6


@pytest.fixture
def src_world(app, app_settings, tmp_path, make_user, make_project, client_factory, database_url):
    from ffcore.core.config import get_settings

    base = tmp_path / "sources"
    (base / "paylasim").mkdir(parents=True)
    settings = app_settings.model_copy(
        update={
            "fake_embed": True,
            "knowledge_storage_dir": str(tmp_path / "storage"),
            "fs_sources_base": str(base),
        }
    )
    app.dependency_overrides[get_settings] = lambda: settings
    sync_queue, ingest_queue = RecordingQueue(), RecordingQueue()
    app.dependency_overrides[sync_queue_dependency] = lambda: sync_queue
    app.dependency_overrides[ingest_queue_dependency] = lambda: ingest_queue
    app.dependency_overrides[queue_dependency] = lambda: ingest_queue
    project = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    developer_id, developer = make_user(memberships={project: ("developer", "edit")})
    analyst_id, analyst = make_user(memberships={project: ("analyst", "edit")})
    w = {
        "settings": settings,
        "database_url": database_url,
        "base": base,
        "root": base / "paylasim",
        "sync_queue": sync_queue,
        "ingest_queue": ingest_queue,
        "project": str(project),
        "admin": client_factory(admin),
        "developer": client_factory(developer),
        "analyst": client_factory(analyst),
        "admin_id": str(admin_id),
        "analyst_id": str(analyst_id),
        "analyst_email": analyst,
    }
    kb = w["admin"].post(
        f"{API}/projects/{project}/knowledge-bases", json={"key": "kaynak-kb", "name": "Kaynak"}
    )
    assert kb.status_code == 201, kb.text
    w["kb"] = kb.json()["id"]
    yield w
    if settings.vector_backend == "qdrant":
        asyncio.run(jobs.get_vector_store(settings).drop_collection(uuid.UUID(w["kb"])))


def sources_url(w, suffix=""):
    return f"{API}/projects/{w['project']}/data-sources" + suffix


def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def age_tree(root: Path, seconds: int = 3600) -> None:
    """Moves every mtime back, so a later write is the only change a delta sees."""
    import time

    old = time.time() - seconds
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            os.utime(path, (old, old))


def create_fs_source(w, key="paylasim", root="paylasim", client="admin", **extra):
    body = {"key": key, "name": key, "kb_id": w["kb"], "kind": "fs", "config": {"root": root}}
    body.update(extra)
    response = w[client].post(sources_url(w), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def sync(w, source_id, layer="raw", mode="full", client="admin", **extra):
    response = w[client].post(
        sources_url(w, f"/{source_id}/sync"), json={"layer": layer, "mode": mode, **extra}
    )
    assert response.status_code == 202, response.text
    return response.json()


def drain(w, *, http=None) -> list[dict]:
    """Run every queued job like the workers would, until both queues are empty."""
    settings = w["settings"]
    store = jobs.get_vector_store(settings)
    results = []

    async def go():
        # The app fixture runs without a pool (several event loops); the workers' loop is one,
        # so it gets a pooled engine like a real worker (a new connection and name lookup per
        # session exhausted Docker's resolver over 1,000 items), disposed before returning.
        db.configure(w["database_url"], pooled=True)
        try:
            await work()
        finally:
            await db._engine.dispose()
            db.configure(w["database_url"], pooled=False)

    async def work():
        while w["sync_queue"].jobs or w["ingest_queue"].jobs:
            while w["sync_queue"].jobs:
                function, run_id = w["sync_queue"].jobs.pop(0)
                assert function == engine.SYNC_RAW_JOB
                results.append(
                    await engine.run_raw(
                        uuid.UUID(run_id),
                        settings=settings,
                        store=store,
                        ingest_queue=w["ingest_queue"],
                        http=http,
                    )
                )
            while w["ingest_queue"].jobs:
                function, *args = w["ingest_queue"].jobs.pop(0)
                if function == "ingest_document_job":
                    await ingest.ingest_document(
                        uuid.UUID(args[0]),
                        settings=settings,
                        store=store,
                        embed_client=ingest.LocalEmbedClient(settings),
                        convert=convert_without_weights,
                    )
                    continue
                assert function == engine.SOURCE_LAYER_JOB, function
                results.append(
                    await engine.run_layer(
                        uuid.UUID(args[0]),
                        settings=settings,
                        store=store,
                        embed_client=ingest.LocalEmbedClient(settings),
                        convert=convert_without_weights,
                    )
                )

    asyncio.run(go())
    return results


def runs(w, source_id):
    response = w["admin"].get(sources_url(w, f"/{source_id}/runs"))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def search(w, client, query):
    response = w[client].post(
        f"{API}/projects/{w['project']}/knowledge-bases/{w['kb']}/search", json={"query": query}
    )
    assert response.status_code == 200, response.text
    return response.json()["hits"]


def found(w, client, marker: str) -> bool:
    """The marker is in a hit's text for this caller (dense search always returns something;
    what matters is which documents the caller may see)."""
    return any(marker in hit["text"] for hit in search(w, client, marker))


def documents(pg, kb_id, *, live=True):
    query = "SELECT id, filename, version, status, deleted_at FROM documents WHERE kb_id = %s"
    if live:
        query += " AND deleted_at IS NULL"
    return pg.execute(query + " ORDER BY filename", (kb_id,)).fetchall()
