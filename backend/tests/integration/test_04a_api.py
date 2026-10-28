"""04a slice 6: the knowledge API end to end (real app, real database, fake models and queue).

Acceptance 3 (admin ACL hidden from analyst), 16 (C15), 18 (search on behalf of a user),
19 (mutations audited, read-only mode 403) and the 04a half of the GET parity rule.
"""

import asyncio
import re
import uuid

import pytest

from ffcore.api.knowledge import queue_dependency
from ffcore.core.auth import sign_on_behalf_of
from ffcore.knowledge import ingest
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from tests.dummy import EMBED_DIM, SERVICE_TOKEN
from tests.integration.conftest import audit_rows

API = "/api/v1"
PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Fesih bildirim süresi doksan gündür ve yazılı yapılır. "
)


class FakeQueue:
    def __init__(self):
        self.jobs = []

    async def enqueue(self, function, *args):
        self.jobs.append((function, *args))
        return f"job-{len(self.jobs)}"


@pytest.fixture
def queue(app):
    fake = FakeQueue()
    app.dependency_overrides[queue_dependency] = lambda: fake
    return fake


@pytest.fixture
def settings(app, app_settings, tmp_path, database_url):
    from ffcore.core.config import get_settings

    value = app_settings.model_copy(
        update={"fake_embed": True, "knowledge_storage_dir": str(tmp_path / "storage")}
    )
    app.dependency_overrides[get_settings] = lambda: value
    return value


@pytest.fixture
def world(make_user, make_project, client_factory, settings, queue):
    project = make_project()
    other = make_project()
    admin_id, admin = make_user(memberships={project: ("admin", "edit")})
    admin_read_id, admin_read = make_user(memberships={project: ("admin", "read")})
    analyst_id, analyst = make_user(memberships={project: ("analyst", "edit")})
    stranger_id, stranger = make_user(memberships={other: ("analyst", "edit")})
    return {
        "project": str(project),
        "other": str(other),
        "admin": client_factory(admin),
        "admin_read": client_factory(admin_read),
        "analyst": client_factory(analyst),
        "stranger": client_factory(stranger),
        "service": client_factory(),
        "analyst_id": analyst_id,
        "admin_id": admin_id,
    }


def kb_url(world, kb_id=""):
    base = f"{API}/projects/{world['project']}/knowledge-bases"
    return f"{base}/{kb_id}" if kb_id else base


def create_kb(world, key="sozlesme"):
    response = world["admin"].post(kb_url(world), json={"key": key, "name": "Sözleşmeler"})
    assert response.status_code == 201, response.text
    return response.json()


def upload(world, client, kb_id, name, text, **form):
    files = {"files": (name, text.encode(), "text/markdown")}
    return client.post(f"{kb_url(world, kb_id)}/documents", files=files, data=form)


def process_all(settings, queue):
    async def go():
        for function, *args in queue.jobs:
            if function == "ingest_document_job":
                await ingest.ingest_document(
                    uuid.UUID(args[0]),
                    settings=settings,
                    store=PgVectorStore(),
                    embed_client=ingest.LocalEmbedClient(settings),
                    convert=ingest.convert_inline,
                )
        queue.jobs.clear()

    asyncio.run(go())


def search(client, world, kb_id, query, **headers):
    return client.post(f"{kb_url(world, kb_id)}/search", json={"query": query}, headers=headers)


# --- KB CRUD and permissions ---


def test_04a_kb_create_permissions_and_audit(world, pg):
    kb = create_kb(world)
    assert kb["embed_dim"] == EMBED_DIM and kb["chunk_size"] == 400 and kb["chunk_overlap"] == 0
    assert kb["chunk_max_tokens"] == 600 and kb["chunk_strategy"] == "heading"
    analyst = world["analyst"].post(kb_url(world), json={"key": "kb-x", "name": "x"})
    admin_read = world["admin_read"].post(kb_url(world), json={"key": "kb-y", "name": "y"})
    assert (analyst.status_code, analyst.json()["error"]["code"]) == (403, "insufficient_role")
    assert (admin_read.status_code, admin_read.json()["error"]["code"]) == (
        403,
        "read_only_access",
    )
    assert len(audit_rows(pg, "create_knowledge_base", "success")) == 1


def test_04a_kb_create_refuses_other_model_and_overlap(world):
    url = kb_url(world)
    dim = world["admin"].post(url, json={"key": "kb-a", "name": "a", "embed_dim": 768})
    model = world["admin"].post(url, json={"key": "kb-b", "name": "b", "embed_model": "x/e5"})
    overlap = world["admin"].post(url, json={"key": "kb-c", "name": "c", "chunk_overlap": 60})
    assert (dim.status_code, dim.json()["error"]["code"]) == (400, "embed_dim_mismatch")
    assert (model.status_code, model.json()["error"]["code"]) == (400, "embed_model_mismatch")
    assert (overlap.status_code, overlap.json()["error"]["code"]) == (
        422,
        "chunk_overlap_unsupported",
    )
    create_kb(world, "dup")
    again = world["admin"].post(url, json={"key": "dup", "name": "dup"})
    assert (again.status_code, again.json()["error"]["code"]) == (409, "knowledge_base_key_taken")


# --- upload, ACL, search ---


def test_04a_16_upload_default_acl_is_analyst_and_shown(world, queue):
    kb = create_kb(world)
    response = upload(world, world["analyst"], kb["id"], "a.md", PROSE * 10)
    assert response.status_code == 202, response.text
    (item,) = response.json()["data"]
    assert item["outcome"] == "created" and item["document"]["acl_roles"] == ["analyst"]
    assert queue.jobs == [("ingest_document_job", item["document"]["id"])]
    again = upload(world, world["analyst"], kb["id"], "a.md", PROSE * 10)
    assert again.json()["data"][0]["outcome"] == "unchanged" and len(queue.jobs) == 1


def test_04a_upload_acl_open_and_conflict(world):
    kb = create_kb(world)
    opened = upload(world, world["analyst"], kb["id"], "open.md", PROSE * 10, acl_open="true")
    assert opened.json()["data"][0]["document"]["acl_roles"] == []
    conflict = upload(
        world, world["analyst"], kb["id"], "x.md", PROSE, acl_open="true", acl_roles="admin"
    )
    assert (conflict.status_code, conflict.json()["error"]["code"]) == (422, "acl_conflict")


def test_04a_upload_read_only_403(world):
    kb = create_kb(world)
    response = upload(world, world["admin_read"], kb["id"], "a.md", PROSE)
    assert response.status_code == 403 and response.json()["error"]["code"] == "read_only_access"


def test_04a_3_admin_document_hidden_from_analyst(world, settings, queue):
    kb = create_kb(world)
    upload(
        world, world["admin"], kb["id"], "gizli.md", "# Gizli\n\n" + PROSE * 8, acl_roles="admin"
    )
    upload(world, world["admin"], kb["id"], "acik.md", "# Açık\n\n" + PROSE * 8, acl_open="true")
    process_all(settings, queue)
    analyst = search(world["analyst"], world, kb["id"], "fesih bildirim süresi").json()
    admin = search(world["admin"], world, kb["id"], "fesih bildirim süresi").json()
    assert {h["document_name"] for h in analyst["hits"]} == {"acik.md"}
    assert {h["document_name"] for h in admin["hits"]} == {"gizli.md", "acik.md"}


def test_04a_16_empty_acl_not_visible_to_another_project(world, settings, queue):
    kb = create_kb(world)
    upload(world, world["admin"], kb["id"], "acik.md", PROSE * 8, acl_open="true")
    process_all(settings, queue)
    response = search(world["stranger"], world, kb["id"], "fesih")
    assert response.status_code == 403


def test_04a_18_search_on_behalf_of_user(world, settings, queue, app_settings):
    kb = create_kb(world)
    upload(world, world["admin"], kb["id"], "gizli.md", PROSE * 8, acl_roles="admin")
    upload(world, world["admin"], kb["id"], "analist.md", PROSE * 8 + " analist")
    process_all(settings, queue)
    token = sign_on_behalf_of(
        user_id=str(world["analyst_id"]),
        project_id=world["project"],
        audience=app_settings.obo_audience,
        settings=app_settings,
    )
    response = search(
        world["service"],
        world,
        kb["id"],
        "fesih bildirim",
        Authorization=f"Bearer {SERVICE_TOKEN}",
        **{"X-On-Behalf-Of": token},
    )
    assert response.status_code == 200, response.text
    assert {h["document_name"] for h in response.json()["hits"]} == {"analist.md"}


def test_04a_15_run_id_header_reaches_kb_queries(world, settings, queue, pg):
    kb = create_kb(world)
    upload(world, world["analyst"], kb["id"], "a.md", PROSE * 8)
    process_all(settings, queue)
    run_id = str(uuid.uuid4())
    response = search(world["analyst"], world, kb["id"], "fesih", **{"X-Run-Id": run_id})
    row = pg.execute(
        "SELECT run_id::text, source FROM kb_queries WHERE id = %s", (response.json()["query_id"],)
    ).fetchone()
    assert row == (run_id, "api")
    playground = world["analyst"].post(
        f"{kb_url(world, kb['id'])}/test-query", json={"query": "fesih"}
    )
    (source,) = pg.execute(
        "SELECT source FROM kb_queries WHERE id = %s", (playground.json()["query_id"],)
    ).fetchone()
    assert source == "playground"


def test_04a_search_open_in_read_only_mode(world, settings, queue):
    kb = create_kb(world)
    upload(world, world["analyst"], kb["id"], "a.md", PROSE * 8)
    process_all(settings, queue)
    response = search(world["admin_read"], world, kb["id"], "fesih")
    assert response.status_code == 200 and response.json()["hits"]


def test_04a_delete_document_leaves_search(world, settings, queue, pg):
    kb = create_kb(world)
    item = upload(world, world["analyst"], kb["id"], "a.md", PROSE * 8).json()["data"][0]
    process_all(settings, queue)
    doc_url = f"{kb_url(world, kb['id'])}/documents/{item['document']['id']}"
    assert world["analyst"].delete(doc_url).status_code == 204
    assert search(world["analyst"], world, kb["id"], "fesih").json()["hits"] == []
    assert world["analyst"].get(doc_url).status_code == 404
    assert len(audit_rows(pg, "delete_document", "success")) == 1


def test_04a_reindex_enqueues_job(world, queue, pg):
    kb = create_kb(world)
    response = world["analyst"].post(
        f"{kb_url(world, kb['id'])}/reindex", json={"layer": "gold", "full": True}
    )
    assert response.status_code == 202 and response.json()["documents"] == 0
    assert queue.jobs == [("reindex_job", kb["id"], "gold", True)]
    assert len(audit_rows(pg, "reindex_knowledge_base", "success")) == 1


def test_04a_read_mode_get_parity(world, settings, queue, app):
    """03a acceptance 2 for the 04a GET routes: read mode sees exactly what edit mode sees."""
    kb = create_kb(world)
    item = upload(world, world["admin"], kb["id"], "a.md", PROSE * 8).json()["data"][0]
    process_all(settings, queue)
    ids = {
        "project_id": world["project"],
        "kb_id": kb["id"],
        "document_id": item["document"]["id"],
    }
    checked = 0
    for path, ops in app.openapi()["paths"].items():
        if "get" not in ops or "knowledge-bases" not in path:
            continue
        url = re.sub(r"\{(\w+)\}", lambda m: ids[m.group(1)], path)
        edit, read = world["admin"].get(url), world["admin_read"].get(url)
        assert edit.status_code == 200, (url, edit.text)
        assert (read.status_code, read.content) == (edit.status_code, edit.content), url
        checked += 1
    assert checked == 4
