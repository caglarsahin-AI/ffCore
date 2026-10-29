"""Review 04a r1 MAJOR-1 and MAJOR-7 (K-04a-0017): ACL changes reach the vector store, the
document ACL guards metadata (GET, list, counts) and audit payloads carry only safe fields."""

import asyncio
import json
import os
import uuid

import pytest

from ffcore.api.knowledge import queue_dependency
from ffcore.knowledge import ingest, jobs

API = "/api/v1"
PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Fesih bildirim süresi doksan gündür ve yazılı yapılır. "
)
SECRET_TEXT = "gizli-madde-7f3a fesih bildirim süresi"
# Synthetic person data in a file name (DECISION-24 pool style, never a real person).
PERSONAL_NAME = "Ayse_Kaplanoglu_10000000146_dilekce.md"


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, function, *args):
        self.jobs.append((function, *args))
        return f"job-{len(self.jobs)}"


def _settings(app_settings, tmp_path, backend):
    extra = {"fake_embed": True, "knowledge_storage_dir": str(tmp_path / "storage")}
    if backend == "qdrant":
        extra.update(
            vector_backend="qdrant",
            qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
            allowed_internal_hosts=["qdrant"],
        )
    return app_settings.model_copy(update=extra)


@pytest.fixture(params=["pgvector", pytest.param("qdrant", marks=pytest.mark.vectorstore)])
def backend(request):
    return request.param


@pytest.fixture
def world(app, app_settings, tmp_path, make_user, make_project, client_factory, backend):
    from ffcore.core.config import get_settings

    settings = _settings(app_settings, tmp_path, backend)
    app.dependency_overrides[get_settings] = lambda: settings
    queue = FakeQueue()
    app.dependency_overrides[queue_dependency] = lambda: queue
    project, other = make_project(), make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    analyst_id, analyst = make_user(memberships={project: ("analyst", "edit")})
    _, peer = make_user(memberships={project: ("analyst", "edit")})
    _, stranger = make_user(memberships={other: ("admin", "edit")})
    w = {
        "settings": settings,
        "queue": queue,
        "project": str(project),
        "admin": client_factory(admin),
        "analyst": client_factory(analyst),
        "peer": client_factory(peer),
        "stranger": client_factory(stranger),
        "analyst_id": str(analyst_id),
        "admin_id": str(admin_id),
    }
    kb = w["admin"].post(kb_url(w), json={"key": "gizli-kb", "name": "Gizli"}).json()
    w["kb"] = kb["id"]
    yield w
    if backend == "qdrant":
        asyncio.run(jobs.get_vector_store(settings).drop_collection(uuid.UUID(kb["id"])))


def kb_url(w, suffix=""):
    return f"{API}/projects/{w['project']}/knowledge-bases" + suffix


def upload(w, client, name, text, **form):
    files = {"files": (name, text.encode(), "text/markdown")}
    return client.post(kb_url(w, f"/{w['kb']}/documents"), files=files, data=form)


def drain(w):
    async def go():
        for function, *args in w["queue"].jobs:
            assert function == "ingest_document_job"
            await ingest.ingest_document(
                uuid.UUID(args[0]),
                settings=w["settings"],
                store=jobs.get_vector_store(w["settings"]),
                embed_client=ingest.LocalEmbedClient(w["settings"]),
                convert=ingest.convert_inline,
            )
        w["queue"].jobs.clear()

    asyncio.run(go())


def search(w, client, query="gizli-madde-7f3a fesih"):
    response = client.post(kb_url(w, f"/{w['kb']}/search"), json={"query": query})
    assert response.status_code == 200, response.text
    return response.json()


def candidates(pg, query_id):
    (rows,) = pg.execute("SELECT candidates FROM kb_queries WHERE id = %s", (query_id,)).fetchone()
    return rows


def test_04a_r1_1_role_narrowing_with_same_bytes_closes_access(world, pg):
    body = "# Gizli\n\n" + (PROSE + SECRET_TEXT + " ") * 6
    first = upload(world, world["admin"], "gizli.md", body, acl_roles="analyst")
    doc_id = first.json()["data"][0]["document"]["id"]
    drain(world)
    assert search(world, world["analyst"])["hits"]

    narrowed = upload(world, world["admin"], "gizli.md", body, acl_roles="admin")
    assert narrowed.status_code == 202, narrowed.text
    assert narrowed.json()["data"][0]["outcome"] == "unchanged"
    drain(world)

    result = search(world, world["analyst"])
    assert result["hits"] == []
    assert all(c["document_id"] != doc_id for c in candidates(pg, result["query_id"]))
    assert SECRET_TEXT not in json.dumps(result)
    assert search(world, world["admin"])["hits"]  # still found by those allowed


def test_04a_r1_1_user_narrowing_with_same_bytes_closes_access(world, pg):
    body = "# Kişisel\n\n" + (PROSE + SECRET_TEXT + " ") * 6
    upload(world, world["admin"], "kisi.md", body, acl_users=world["analyst_id"])
    drain(world)
    assert search(world, world["analyst"])["hits"]
    upload(world, world["admin"], "kisi.md", body, acl_users=world["admin_id"])
    drain(world)
    result = search(world, world["analyst"])
    assert result["hits"] == [] and candidates(pg, result["query_id"]) == []


def test_04a_r1_7_document_metadata_follows_its_acl(world):
    hidden = upload(world, world["admin"], "yonetim.md", PROSE * 8, acl_roles="admin")
    open_ = upload(world, world["admin"], "acik.md", PROSE * 8 + " açık", acl_open="true")
    drain(world)
    hidden_id = hidden.json()["data"][0]["document"]["id"]
    open_id = open_.json()["data"][0]["document"]["id"]
    docs = kb_url(world, f"/{world['kb']}/documents")

    assert world["analyst"].get(f"{docs}/{hidden_id}").status_code == 404
    assert world["analyst"].get(f"{docs}/{open_id}").status_code == 200
    listed = {d["id"] for d in world["analyst"].get(docs).json()["data"]}
    assert listed == {open_id}
    analyst_kb = world["analyst"].get(kb_url(world, f"/{world['kb']}")).json()
    admin_kb = world["admin"].get(kb_url(world, f"/{world['kb']}")).json()
    assert analyst_kb["document_count"] == 1 and admin_kb["document_count"] == 2
    assert analyst_kb["chunk_count"] < admin_kb["chunk_count"]
    in_list = next(
        k for k in world["analyst"].get(kb_url(world)).json()["data"] if k["id"] == world["kb"]
    )
    assert in_list["document_count"] == 1
    # Hidden document: the analyst cannot delete it either (404, nothing leaks).
    assert world["analyst"].delete(f"{docs}/{hidden_id}").status_code == 404
    assert world["stranger"].get(f"{docs}/{open_id}").status_code == 403


def test_04a_r1_7_audit_carries_no_file_names_or_free_text(world, pg):
    response = upload(world, world["admin"], PERSONAL_NAME, PROSE * 8, acl_roles="admin")
    doc_id = response.json()["data"][0]["document"]["id"]
    world["admin"].post(kb_url(world, f"/{world['kb']}/reindex"), json={"layer": "gold"})
    world["admin"].delete(kb_url(world, f"/{world['kb']}/documents/{doc_id}"))
    rows = pg.execute(
        "SELECT action, before::text, after::text FROM audit_events"
        " WHERE action IN ('upload_documents', 'reindex_knowledge_base', 'delete_document')"
        " AND project_id = %s",
        (world["project"],),
    ).fetchall()
    assert {r[0] for r in rows} == {"upload_documents", "reindex_knowledge_base", "delete_document"}
    for action, before, after in rows:
        for payload in (before, after):
            text = payload or ""
            assert "Kaplanoglu" not in text and "10000000146" not in text, (action, text)
    upload_after = json.loads(next(r[2] for r in rows if r[0] == "upload_documents"))
    item = upload_after["data"][0]
    assert item["document"]["id"] == doc_id and item["outcome"] == "created"
    assert item["document"]["sha256"] and item["document"]["version"] == 1
