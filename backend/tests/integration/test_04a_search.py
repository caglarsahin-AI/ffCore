"""04a slice 4: hybrid search, single threshold rule (K2), rerank floor (D5), kb_queries (C12)."""

import asyncio
import math
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import search
from ffcore.knowledge.embed import Embeddings, FakeEmbedder
from ffcore.knowledge.store import NewChunk, PgKnowledgeStore
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorRecord
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from ffcore.models.knowledge import KnowledgeBase
from tests.dummy import EMBED_DIM, SETTINGS_03A

SETTINGS = Settings(
    deploy_profile="llmaas",
    offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    fake_embed=True,
    **SETTINGS_03A,
)
EMBEDDER = FakeEmbedder("BAAI/bge-m3", EMBED_DIM)


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


def run(coro):
    return asyncio.run(coro)


def _axis(index: int) -> list[float]:
    vector = [0.0] * EMBED_DIM
    vector[index] = 1.0
    return vector


def _mix(a: int, b: int, weight_b: float) -> list[float]:
    vector = [0.0] * EMBED_DIM
    vector[a], vector[b] = 1.0, weight_b
    norm = math.sqrt(1 + weight_b * weight_b)
    return [x / norm for x in vector]


class AxisEmbedder:
    """Query → axis 0; lets a test place chunk vectors exactly (cosine = chosen value)."""

    model, dim = "BAAI/bge-m3", EMBED_DIM

    def encode(self, texts):
        return Embeddings([_axis(0) for _ in texts], [{} for _ in texts], [False for _ in texts])


class TableReranker:
    model = "BAAI/bge-reranker-v2-m3"

    def __init__(self, scores: dict[str, float]):
        self.scores = scores

    def score(self, query, texts):
        return [next((s for key, s in self.scores.items() if key in t), 0.0) for t in texts]


def make_kb(pg, project_id, *, rerank=True, min_score=None, top_k=5) -> uuid.UUID:
    kb_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO knowledge_bases (id, project_id, key, name, embed_model, embed_dim,"
        " chunk_size, chunk_overlap, hybrid, rerank, rerank_model, default_top_k,"
        " default_min_score, normalizer_config_id, created_by) VALUES (%s, %s, %s, 'KB',"
        " 'BAAI/bge-m3', %s, 400, 0, true, %s, 'BAAI/bge-reranker-v2-m3', %s, %s, 'format-v1',"
        " 'test')",
        (kb_id, project_id, f"kb-{kb_id.hex[:8]}", EMBED_DIM, rerank, top_k, min_score),
    )
    return kb_id


def index(kb_id, docs):
    """docs: [(filename, chunk_text, vector or None, updated_at_source)] → {filename: chunk_id}."""

    async def go():
        out, records = {}, []
        async with db.session_scope() as session:
            store = PgKnowledgeStore(session)
            kb = await session.get(KnowledgeBase, kb_id)
            for name, text, vector, updated in docs:
                document, _ = await store.register_upload(
                    kb,
                    filename=name,
                    sha256=name,
                    size=1,
                    raw_path=name,
                    acl_roles=[],
                    acl_users=[],
                    created_by="test",
                )
                document.status = "indexed"  # search reads indexed only (r1 MAJOR-3)
                document.updated_at_source = updated
                (chunk,) = await store.replace_chunks(
                    document,
                    [
                        NewChunk(
                            ordinal=0,
                            text=f"KB › {name}\n\n{text}",
                            breadcrumb=f"KB › {name}",
                            token_count=10,
                        )
                    ],
                    "BAAI/bge-m3",
                )
                vec = vector or EMBEDDER.encode([chunk.text]).dense[0]
                records.append(VectorRecord(chunk.id, kb_id, document.id, vec))
                out[name] = chunk.id
            await session.commit()
        await PgVectorStore().upsert(records)
        return out

    return run(go())


def do_search(kb_id, query, *, embedder=None, reranker=None, run_id=None, top_k=None):
    async def go():
        async with db.session_scope() as session:
            kb = await session.get(KnowledgeBase, kb_id)
            result = await search.search(
                session,
                kb,
                query,
                filters=VectorFilters(acl_roles=("analyst",)),
                top_k=top_k,
                hybrid=None,
                run_id=run_id,
                user_id="u-1",
                source="api",
                settings=SETTINGS,
                store=PgVectorStore(),
                embedder=embedder,
                reranker=reranker,
            )
            await session.commit()
            return result

    return run(go())


def query_row(pg, query_id):
    return pg.execute(
        "SELECT candidates, returned, threshold_mode, filtered_by_rerank_floor,"
        " filtered_by_min_score, run_id, normalizer_config_id, best_embed_score,"
        " best_rerank_score, user_id FROM kb_queries WHERE id = %s",
        (query_id,),
    ).fetchone()


def test_04a_13_single_threshold_rule_reranker_on(pg, make_project):
    kb_id = make_kb(pg, make_project(), rerank=True, min_score=0.5)
    ids = index(
        kb_id,
        [("low.pdf", "uzak aday", _mix(1, 0, 0.2), None), ("near.pdf", "yakin", _axis(0), None)],
    )
    reranker = TableReranker({"uzak aday": 0.9, "yakin": 0.8})
    result = do_search(kb_id, "soru", embedder=AxisEmbedder(), reranker=reranker)
    hit = {h.chunk_id: h for h in result.hits}
    # Embedding score of low.pdf is ~0.2, under default_min_score 0.5, yet it is returned: with
    # the reranker on, min_score is not applied (K2).
    assert ids["low.pdf"] in hit and hit[ids["low.pdf"]].embed_score < 0.3
    assert result.threshold_mode == "rerank_floor" and result.filtered_by_min_score == 0


def test_04a_13_single_threshold_rule_reranker_off(pg, make_project):
    kb_id = make_kb(pg, make_project(), rerank=False, min_score=0.5)
    ids = index(
        kb_id,
        [("low.pdf", "uzak aday", _mix(1, 0, 0.2), None), ("near.pdf", "yakin", _axis(0), None)],
    )
    result = do_search(kb_id, "soru", embedder=AxisEmbedder())
    returned = {h.chunk_id for h in result.hits}
    assert returned == {ids["near.pdf"]}
    assert result.threshold_mode == "min_score" and result.filtered_by_min_score == 1
    assert all(h.rerank_score is None for h in result.hits)


def test_04a_11b_rerank_floor_drops_and_counts(pg, make_project):
    kb_id = make_kb(pg, make_project())
    ids = index(
        kb_id, [("noise.pdf", "gurultu", _axis(0), None), ("good.pdf", "iyi", _axis(0), None)]
    )
    reranker = TableReranker({"gurultu": 0.05, "iyi": 0.7})
    result = do_search(kb_id, "soru", embedder=AxisEmbedder(), reranker=reranker)
    assert [h.chunk_id for h in result.hits] == [ids["good.pdf"]]
    assert result.filtered_by_rerank_floor == 1
    row = query_row(pg, result.query_id)
    assert row[3] == 1  # kb_queries.filtered_by_rerank_floor
    noise = next(c for c in row[0] if c["chunk_id"] == str(ids["noise.pdf"]))
    assert noise["rerank_score"] == pytest.approx(0.05) and noise["below_rerank_floor"] is True


def test_04a_rerank_floor_all_below_gives_empty_result(pg, make_project):
    kb_id = make_kb(pg, make_project())
    index(kb_id, [("noise.pdf", "gurultu", _axis(0), None)])
    result = do_search(kb_id, "soru", embedder=AxisEmbedder(), reranker=TableReranker({}))
    assert result.hits == [] and result.filtered_by_rerank_floor == 1


def test_04a_15_kb_queries_candidates_and_run_id(pg, make_project):
    kb_id = make_kb(pg, make_project())
    index(kb_id, [(f"d{i}.pdf", f"bakım sözleşmesi madde {i}", None, None) for i in range(35)])
    run_id = uuid.uuid4()
    result = do_search(kb_id, "bakım sözleşmesi", run_id=run_id)
    candidates, returned, mode, *_rest = query_row(pg, result.query_id)
    assert len(candidates) == SETTINGS.retrieval_candidates == 30
    assert {"chunk_id", "document_id", "embed_score", "rerank_score", "rrf_rank"} <= set(
        candidates[0]
    )
    row = query_row(pg, result.query_id)
    assert row[5] == run_id and row[6] == "format-v1" and row[9] == "u-1"
    assert returned == len(result.hits) <= 5


def test_04a_lexical_leg_finds_exact_term(pg, make_project):
    kb_id = make_kb(pg, make_project(), rerank=False)
    # The dense vector points away from the query; only the BM25 leg can bring this chunk in.
    ids = index(kb_id, [("term.pdf", "mücbir sebep hükümleri", _axis(7), None)])
    result = do_search(kb_id, "mücbir sebep", embedder=AxisEmbedder())
    row = query_row(pg, result.query_id)
    assert str(ids["term.pdf"]) in {c["chunk_id"] for c in row[0]}


def test_04a_hits_ordered_newest_source_first_with_age(pg, make_project):
    kb_id = make_kb(pg, make_project())
    now = datetime.now(UTC)
    ids = index(
        kb_id,
        [
            ("old.pdf", "fesih süresi", None, now - timedelta(days=400)),
            ("new.pdf", "fesih süresi", None, now - timedelta(days=3)),
        ],
    )
    result = do_search(kb_id, "fesih süresi")
    assert [h.chunk_id for h in result.hits] == [ids["new.pdf"], ids["old.pdf"]]
    assert result.hits[0].age_days == 3 and result.hits[1].age_days == 400


def test_04a_query_goes_through_the_silver_normalizer(pg, make_project):
    kb_id = make_kb(pg, make_project())
    index(kb_id, [("a.pdf", "fesih süresi", None, None)])
    result = do_search(kb_id, "fesih&nbsp;&nbsp;<b>süresi</b>")
    row = query_row(pg, result.query_id)
    stored = pg.execute("SELECT query FROM kb_queries WHERE id = %s", (result.query_id,))
    assert stored.fetchone()[0] == "fesih süresi" and row[6] == "format-v1"
