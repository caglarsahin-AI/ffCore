"""04a slice 5: QdrantStore against a real Qdrant (compose profile `qdrant`, RUN_QDRANT_TESTS=1).

R3.5 (K-04a-0002 S3): the same vectors and filters give the same top 5 in both drivers in exact
mode, and at least 4 of 5 in approximate mode; ACL is applied in the Qdrant query too.
"""

import asyncio
import math
import os
import random
import uuid

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge.store import NewChunk, PgKnowledgeStore
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorQuery, VectorRecord
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from ffcore.knowledge.vectorstore.qdrant import QdrantStore
from ffcore.models.knowledge import KnowledgeBase
from tests.dummy import EMBED_DIM, SETTINGS_03A

pytestmark = pytest.mark.vectorstore


def settings() -> Settings:
    return Settings(
        deploy_profile="airgap",
        offline=True,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        vector_backend="qdrant",
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        allowed_internal_hosts=["qdrant"],
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


def run(coro):
    return asyncio.run(coro)


def random_unit(rng: random.Random) -> list[float]:
    vector = [rng.gauss(0, 1) for _ in range(EMBED_DIM)]
    norm = math.sqrt(sum(x * x for x in vector))
    return [x / norm for x in vector]


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


def index_both(kb_id, docs):
    """docs: [(acl_roles, vector)] → records written to Postgres+pgvector and to Qdrant."""

    async def go():
        records = []
        async with db.session_scope() as session:
            store = PgKnowledgeStore(session)
            kb = await session.get(KnowledgeBase, kb_id)
            for i, (roles, vector) in enumerate(docs):
                document, _ = await store.register_upload(
                    kb,
                    filename=f"d{i}.pdf",
                    sha256=str(i),
                    size=1,
                    raw_path="r",
                    acl_roles=list(roles),
                    acl_users=[],
                    created_by="test",
                )
                (chunk,) = await store.replace_chunks(
                    document,
                    [
                        NewChunk(
                            ordinal=0,
                            text=f"KB › d{i}\n\nmetin {i}",
                            breadcrumb="KB",
                            token_count=3,
                        )
                    ],
                    "BAAI/bge-m3",
                )
                records.append(
                    VectorRecord(chunk.id, kb_id, document.id, vector, acl_roles=tuple(roles))
                )
            await session.commit()
        qdrant = QdrantStore(settings())
        await qdrant.ensure_collection(kb_id, EMBED_DIM)
        await qdrant.upsert(records)
        await PgVectorStore().upsert(records)
        return records

    return run(go())


def test_04a_6_pgvector_qdrant_top5_parity(pg, make_project):
    rng = random.Random(42)
    kb_id = make_kb(pg, make_project())
    index_both(kb_id, [((), random_unit(rng)) for _ in range(60)])
    qdrant, pgvector = QdrantStore(settings()), PgVectorStore()
    try:
        for _ in range(5):
            query = random_unit(rng)
            exact_q = run(qdrant.search(kb_id, VectorQuery(query, exact=True), VectorFilters(), 5))
            exact_p = run(
                pgvector.search(kb_id, VectorQuery(query, exact=True), VectorFilters(), 5)
            )
            assert [h.chunk_id for h in exact_q] == [h.chunk_id for h in exact_p]
            approx_q = run(qdrant.search(kb_id, VectorQuery(query), VectorFilters(), 5))
            approx_p = run(pgvector.search(kb_id, VectorQuery(query), VectorFilters(), 5))
            assert len({h.chunk_id for h in approx_q} & {h.chunk_id for h in approx_p}) >= 4
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04a_3_qdrant_acl_in_query(pg, make_project):
    rng = random.Random(7)
    kb_id = make_kb(pg, make_project())
    shared = random_unit(rng)
    records = index_both(kb_id, [(("admin",), shared), (("analyst",), shared), ((), shared)])
    qdrant = QdrantStore(settings())
    try:
        analyst = run(
            qdrant.search(kb_id, VectorQuery(shared), VectorFilters(acl_roles=("analyst",)), 10)
        )
        assert {h.chunk_id for h in analyst} == {records[1].chunk_id, records[2].chunk_id}
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04a_qdrant_delete_by_document_and_hybrid_query(pg, make_project):
    rng = random.Random(3)
    kb_id = make_kb(pg, make_project())
    vector = random_unit(rng)
    records = index_both(kb_id, [((), vector), ((), random_unit(rng))])
    qdrant = QdrantStore(settings())
    try:
        hybrid = run(qdrant.search(kb_id, VectorQuery(vector, {11: 0.5}), VectorFilters(), 5))
        assert hybrid and hybrid[0].chunk_id == records[0].chunk_id
        run(qdrant.delete_by_document(records[0].document_id))
        left = run(qdrant.search(kb_id, VectorQuery(vector), VectorFilters(), 5))
        assert records[0].chunk_id not in {h.chunk_id for h in left}
    finally:
        run(qdrant.drop_collection(kb_id))


def test_04a_qdrant_unreachable_is_an_error_not_a_fallback():
    from ffcore.knowledge.vectorstore.base import VectorStoreError

    broken = settings().model_copy(update={"qdrant_url": "http://qdrant-missing:6333"})
    with pytest.raises(VectorStoreError) as err:
        run(QdrantStore(broken).search(uuid.uuid4(), VectorQuery([1.0]), VectorFilters(), 1))
    assert err.value.code == "vector_store_unavailable"
