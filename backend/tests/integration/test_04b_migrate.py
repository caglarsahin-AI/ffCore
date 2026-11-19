"""04b-1 D1: `migrate-vectors` between pgvector and Qdrant (compose profile `qdrant`).

Acceptance 1 (brief 04, K-04B-0001): after a migration both sides hold the same number of
searchable chunks and the ACL is applied in the query on each side. Embeddings are never
recomputed; a legacy row without sparse weights gets its sparse weights only, counted
(K-04B-0002 S2 A). A target that does not match fails loud; `drop_target` starts it clean.
"""

import asyncio
import os
import uuid

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest, migrate
from ffcore.knowledge.embed import FakeEmbedder
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorQuery, VectorRecord
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from ffcore.knowledge.vectorstore.qdrant import QdrantStore
from tests.converters import convert_without_weights
from tests.dummy import EMBED_DIM, SETTINGS_03A

pytestmark = pytest.mark.vectorstore

PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür. "
)
SEARCHABLE = (
    "SELECT count(*) FROM chunks c JOIN documents d ON d.id = c.document_id"
    " WHERE c.kb_id = %s AND c.chunk_status IN ('ok', 'flagged') AND d.status = 'indexed'"
    " AND d.deleted_at IS NULL"
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        deploy_profile="airgap",
        offline=True,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        vector_backend="qdrant",
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        allowed_internal_hosts=["qdrant"],
        knowledge_storage_dir=str(tmp_path / "storage"),
        convert_timeout_seconds=120,
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


class CountingEmbedder(FakeEmbedder):
    def __init__(self):
        super().__init__("BAAI/bge-m3", EMBED_DIM)
        self.texts = 0

    def encode(self, texts):
        self.texts += len(texts)
        return super().encode(texts)


def run(coro):
    return asyncio.run(coro)


def make_kb(pg, project_id) -> uuid.UUID:
    kb_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " normalizer_config_id, created_by) VALUES (%s, %s, %s, 'Sözleşmeler', 'BAAI/bge-m3',"
        " %s, 400, 0, true, true, 'BAAI/bge-reranker-v2-m3', 5, 'format-v1', 'test')",
        (kb_id, project_id, f"kb-{kb_id.hex[:8]}", EMBED_DIM),
    )
    return kb_id


def markdown(name, *sections):
    # Each document its own text: identical bodies are duplicates (Kapı 1, duplicate_of).
    return "\n\n".join(f"## Madde {i} {name}\n\n{name} {PROSE * 6}" for i in sections).encode()


def ingest_docs(settings, kb_id, docs, store, embedder=None):
    """docs: [(filename, acl_roles)] → {filename: document_id}, indexed through `store`."""

    async def go():
        out = {}
        for name, roles in docs:
            async with db.session_scope() as session:
                document, _ = await ingest.register_upload(
                    session,
                    kb_id,
                    filename=name,
                    data=markdown(name, 1, 2),
                    acl_roles=list(roles),
                    acl_users=[],
                    created_by="test",
                    settings=settings,
                )
                await session.commit()
                out[name] = document.id
            report = await ingest.ingest_document(
                out[name],
                settings=settings,
                store=store,
                embed_client=ingest.LocalEmbedClient(settings, embedder),
                convert=convert_without_weights,
            )
            assert report.status == "indexed", report
        return out

    return run(go())


def migrate_kb(settings, kb_id, source, target, **kwargs):
    return run(
        migrate.migrate_vectors(
            source=source,
            target=target,
            kb_ids=[kb_id],
            settings=settings,
            embed_client=ingest.LocalEmbedClient(settings),
            **kwargs,
        )
    )


def searchable(pg, kb_id) -> int:
    return pg.execute(SEARCHABLE, (kb_id,)).fetchone()[0]


def query_vector(settings, text="bakım hizmeti rapor"):
    embedded = FakeEmbedder("BAAI/bge-m3", EMBED_DIM).encode([text])
    return VectorQuery(embedded.dense[0], embedded.sparse[0])


def test_04b_1_pgvector_to_qdrant_counts_equal_and_acl_in_query(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    docs = ingest_docs(
        settings,
        kb_id,
        [("admin.md", ("admin",)), ("analyst.md", ("analyst",)), ("open.md", ())],
        PgVectorStore(),
    )
    qdrant = QdrantStore(settings)
    try:
        report = migrate_kb(settings, kb_id, PgVectorStore(), qdrant)
        (kb,) = report.kbs
        assert report.ok
        assert kb.source_count == kb.target_count == searchable(pg, kb_id) > 0
        assert kb.written == kb.source_count and kb.sparse_computed == 0
        assert run(qdrant.count(kb_id)) == kb.source_count
        hits = run(
            qdrant.search(kb_id, query_vector(settings), VectorFilters(acl_roles=("analyst",)), 50)
        )
        found = {h.document_id for h in hits}
        assert found == {docs["analyst.md"], docs["open.md"]}
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04b_1_qdrant_to_pgvector_fills_missing_vectors(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    qdrant = QdrantStore(settings)
    try:
        docs = ingest_docs(
            settings, kb_id, [("admin.md", ("admin",)), ("analyst.md", ("analyst",))], qdrant
        )
        # A pgvector side that lost its vectors (the Qdrant installation never needed them).
        pg.execute("UPDATE chunks SET embedding = NULL WHERE document_id = %s", (docs["admin.md"],))
        missing = pg.execute(
            "SELECT count(*) FROM chunks WHERE kb_id = %s AND embedding IS NULL", (kb_id,)
        ).fetchone()[0]
        report = migrate_kb(settings, kb_id, qdrant, PgVectorStore())
        (kb,) = report.kbs
        assert report.ok
        assert kb.source_count == kb.target_count == searchable(pg, kb_id)
        assert kb.written == missing > 0
        assert run(PgVectorStore().count(kb_id)) == kb.source_count
        hits = run(
            PgVectorStore().search(
                kb_id, query_vector(settings), VectorFilters(acl_roles=("analyst",)), 50
            )
        )
        assert {h.document_id for h in hits} == {docs["analyst.md"]}
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04b_1_legacy_rows_get_sparse_only_and_dry_run_writes_nothing(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    ingest_docs(settings, kb_id, [("a.md", ("analyst",))], PgVectorStore())
    pg.execute("UPDATE chunks SET sparse = NULL WHERE kb_id = %s", (kb_id,))
    before = pg.execute(
        "SELECT id, embedding::text FROM chunks WHERE kb_id = %s ORDER BY id", (kb_id,)
    ).fetchall()
    qdrant = QdrantStore(settings)
    try:
        dry = migrate_kb(settings, kb_id, PgVectorStore(), qdrant, dry_run=True)
        (kb,) = dry.kbs
        assert kb.sparse_missing == len(before) and kb.written == 0 and kb.sparse_computed == 0
        assert run(qdrant.count(kb_id)) == 0
        assert (
            pg.execute(
                "SELECT count(*) FROM chunks WHERE kb_id = %s AND sparse IS NOT NULL", (kb_id,)
            ).fetchone()[0]
            == 0
        )

        report = migrate_kb(settings, kb_id, PgVectorStore(), qdrant)
        (kb,) = report.kbs
        assert report.ok and kb.sparse_computed == len(before) and kb.sparse_missing == 0
        after = pg.execute(
            "SELECT id, embedding::text FROM chunks WHERE kb_id = %s ORDER BY id", (kb_id,)
        ).fetchall()
        assert after == before  # dense never recomputed
        assert (
            pg.execute(
                "SELECT count(*) FROM chunks WHERE kb_id = %s AND sparse IS NULL", (kb_id,)
            ).fetchone()[0]
            == 0
        )
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04b_1_target_with_foreign_points_fails_loud_until_dropped(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    docs = ingest_docs(settings, kb_id, [("a.md", ("analyst",))], PgVectorStore())
    qdrant = QdrantStore(settings)
    try:
        run(qdrant.ensure_collection(kb_id, EMBED_DIM))
        stray = VectorRecord(uuid.uuid4(), kb_id, docs["a.md"], [1.0] + [0.0] * (EMBED_DIM - 1))
        run(qdrant.upsert([stray]))
        report = migrate_kb(settings, kb_id, PgVectorStore(), qdrant)
        (kb,) = report.kbs
        assert not report.ok and kb.target_count == kb.source_count + 1
        assert any("drop-target" in line for line in report.lines())

        report = migrate_kb(settings, kb_id, PgVectorStore(), qdrant, drop_target=True)
        assert report.ok and report.kbs[0].target_count == report.kbs[0].source_count
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04b_1_qdrant_reuse_does_not_reembed(pg, make_project, settings):
    """S2 A: sparse weights travel with a reused vector, so a Qdrant gold reindex reuses too."""
    kb_id = make_kb(pg, make_project())
    qdrant = QdrantStore(settings)
    embedder = CountingEmbedder()
    try:
        ingest_docs(settings, kb_id, [("a.md", ("analyst",))], qdrant, embedder)
        first = embedder.texts
        assert first > 0
        report = run(
            ingest.reindex_gold(
                kb_id,
                full=True,
                settings=settings,
                store=qdrant,
                embed_client=ingest.LocalEmbedClient(settings, embedder),
            )
        )
        assert embedder.texts == first and report.embedded == 0 and report.reused > 0
        assert run(qdrant.count(kb_id)) == searchable(pg, kb_id)
    finally:
        run(qdrant.drop_collection(kb_id))
