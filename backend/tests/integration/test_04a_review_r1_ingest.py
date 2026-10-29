"""Review 04a r1 MAJOR-2 (no self-lock when a gate rejects a new version) and MAJOR-3
(`indexed` only after the vector publication succeeded) against the real database."""

import asyncio
import uuid

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest
from ffcore.knowledge.vectorstore.base import VectorStoreError
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from tests.converters import convert_without_weights
from tests.dummy import EMBED_DIM, SETTINGS_03A

PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür. "
)
BOUND_S = 30  # the reviewer's run hung; any gate rejection must finish well within this


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        knowledge_storage_dir=str(tmp_path / "storage"),
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
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


def upload(settings, kb_id, name, text):
    async def go():
        async with db.session_scope() as session:
            document, _ = await ingest.register_upload(
                session,
                kb_id,
                filename=name,
                data=text.encode(),
                acl_roles=["analyst"],
                acl_users=[],
                created_by="test",
                settings=settings,
            )
            await session.commit()
            return document.id

    return asyncio.run(go())


def process(settings, document_id, store=None):
    async def go():
        return await asyncio.wait_for(
            ingest.ingest_document(
                document_id,
                settings=settings,
                store=store or PgVectorStore(),
                embed_client=ingest.LocalEmbedClient(settings),
                convert=convert_without_weights,
            ),
            BOUND_S,
        )

    return asyncio.run(go())


def row(pg, document_id):
    return pg.execute(
        "SELECT status, error, (SELECT count(*) FROM chunks c WHERE c.document_id = d.id),"
        " (SELECT count(*) FROM chunks c WHERE c.document_id = d.id AND c.embedding IS NULL)"
        " FROM documents d WHERE id = %s",
        (document_id,),
    ).fetchone()


def lock_waiters(pg) -> int:
    (count,) = pg.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"
        " AND wait_event_type = 'Lock'"
    ).fetchone()
    return count


@pytest.mark.parametrize(
    "replacement",
    [
        "kısa",  # too_short
        "\n".join(f"- [Alt sayfa {i}](https://wiki.example.test/p/{i})" for i in range(40)),
    ],
)
def test_04a_r1_2_gate_rejected_new_version_does_not_self_lock(
    pg, make_project, settings, replacement
):
    kb_id = make_kb(pg, make_project())
    doc_id = upload(settings, kb_id, "a.md", "# A\n\n" + PROSE * 8)
    assert process(settings, doc_id).status == "indexed"
    assert row(pg, doc_id)[2] > 0
    upload(settings, kb_id, "a.md", replacement)
    report = process(settings, doc_id)  # wait_for: a self-lock fails this test, not hangs it
    assert report.status == "skipped"
    status, _, chunks, _ = row(pg, doc_id)
    assert status == "skipped" and chunks == 0
    assert lock_waiters(pg) == 0


class FailingStore(PgVectorStore):
    def __init__(self, step: str):
        super().__init__()
        self.step = step
        if step == "delete":
            self.name = "qdrant"  # the delete-before-upsert step runs for Qdrant only

    async def ensure_collection(self, kb_id, dim):
        if self.step == "ensure":
            raise VectorStoreError("vector_store_unavailable", "injected")
        return await super().ensure_collection(kb_id, dim)

    async def delete_by_document(self, document_id):
        if self.step == "delete":
            raise VectorStoreError("vector_store_unavailable", "injected")
        return await super().delete_by_document(document_id)

    async def upsert(self, chunks):
        if self.step == "upsert":
            raise VectorStoreError("vector_store_unavailable", "injected")
        return await super().upsert(chunks)


@pytest.mark.parametrize("step", ["ensure", "delete", "upsert"])
def test_04a_r1_3_failed_publication_is_never_indexed(pg, make_project, settings, step):
    kb_id = make_kb(pg, make_project())
    doc_id = upload(settings, kb_id, "a.md", "# A\n\n" + PROSE * 8)
    report = process(settings, doc_id, FailingStore(step))
    status, error, _, _ = row(pg, doc_id)
    assert report.status == "failed" and status == "failed"
    assert error.startswith("vector_store_unavailable")

    async def found():
        from ffcore.knowledge.vectorstore.base import VectorFilters, VectorQuery

        hits = await PgVectorStore().search(
            kb_id,
            VectorQuery([1.0 / EMBED_DIM**0.5] * EMBED_DIM, exact=True),
            VectorFilters(acl_roles=("analyst",)),
            10,
        )
        return hits

    assert asyncio.run(found()) == []  # a failed document is not searchable
    # Retry with a working store: one consistent index and the right status.
    assert process(settings, doc_id).status == "indexed"
    status, error, chunks, missing = row(pg, doc_id)
    assert status == "indexed" and error is None and chunks > 0 and missing == 0


def test_04a_r1_4_unchunkable_document_fails_with_a_code(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    heading = "# " + " ".join(["Başlık"] * 400)  # the heading joins the breadcrumb
    doc_id = upload(settings, kb_id, "uzun.md", heading + "\n\n" + PROSE * 8)
    assert process(settings, doc_id).status == "failed"
    status, error, chunks, _ = row(pg, doc_id)
    assert status == "failed" and error.startswith("chunk_breadcrumb_too_long") and chunks == 0
