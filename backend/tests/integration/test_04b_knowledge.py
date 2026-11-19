"""04b-1: sparse weights in Postgres (D1/S2), same bytes → unchanged (FOLLOWUP-157), targeted
reconversion presets (D2, pipeline step 10) and the filtered chunk list of a search (FOLLOWUP-86).
"""

import asyncio
import uuid

import pytest

from ffcore.core import db
from ffcore.core.config import Settings
from ffcore.knowledge import ingest, search
from ffcore.knowledge.vectorstore.base import VectorFilters
from ffcore.knowledge.vectorstore.pgvector import PgVectorStore
from ffcore.models.knowledge import KnowledgeBase
from tests.converters import convert_without_weights
from tests.dummy import EMBED_DIM, SETTINGS_03A
from tests.integration.test_04a_search import (
    AxisEmbedder,
    TableReranker,
    _axis,
    _mix,
    index,
)
from tests.integration.test_04a_search import make_kb as make_search_kb

PROSE = (
    "Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür. "
)


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        deploy_profile="llmaas",
        offline=False,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        fake_embed=True,
        knowledge_storage_dir=str(tmp_path / "storage"),
        convert_timeout_seconds=120,
        **SETTINGS_03A,
    )


@pytest.fixture(autouse=True)
def configured_db(database_url):
    db.configure(database_url, pooled=False)
    yield
    db.reset()


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


def markdown(*sections):
    return "\n\n".join(f"## Madde {i}\n\n{PROSE * 6}" for i in sections).encode()


def upload(settings, kb_id, filename, data: bytes):
    async def go():
        async with db.session_scope() as session:
            document, outcome = await ingest.register_upload(
                session,
                kb_id,
                filename=filename,
                data=data,
                acl_roles=["analyst"],
                acl_users=[],
                created_by="test",
                settings=settings,
            )
            await session.commit()
            return document.id, outcome, document.version

    return run(go())


def process(settings, document_id, convert=convert_without_weights):
    return run(
        ingest.ingest_document(
            document_id,
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings),
            convert=convert,
        )
    )


class SpyConverter:
    def __init__(self):
        self.seen: list[str] = []

    def __call__(self, path, filename, settings):
        self.seen.append(filename)
        return convert_without_weights(path, filename, settings)


# --- S2: sparse weights are stored beside the dense vector ---


def test_04b_1_ingest_writes_sparse_beside_dense(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    doc_id, _, _ = upload(settings, kb_id, "a.md", markdown(1, 2))
    assert process(settings, doc_id).status == "indexed"
    rows = pg.execute(
        "SELECT embedding IS NOT NULL, sparse FROM chunks WHERE document_id = %s"
        " AND chunk_status <> 'skipped'",
        (doc_id,),
    ).fetchall()
    assert rows and all(dense for dense, _ in rows)
    for _, sparse in rows:
        assert sparse and all(int(k) >= 0 and v > 0 for k, v in sparse.items())


# --- FOLLOWUP-157: identical bytes are not a new version ---


def test_04b_157_same_bytes_unchanged_keeps_version(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    first, outcome1, v1 = upload(settings, kb_id, "a.md", markdown(1))
    same, outcome2, v2 = upload(settings, kb_id, "a.md", markdown(1))
    changed, outcome3, v3 = upload(settings, kb_id, "a.md", markdown(1, 2))
    assert first == same == changed
    assert (outcome1, outcome2, outcome3) == ("created", "unchanged", "new_version")
    assert (v1, v2, v3) == (1, 1, 2)


# --- D2: targeted reconversion presets (pipeline step 10) ---


def _prepare_preset_kb(pg, make_project, settings):
    kb_id = make_kb(pg, make_project())
    good, _, _ = upload(settings, kb_id, "iyi.md", markdown(1))
    bad, _, _ = upload(settings, kb_id, "bozuk.txt", b"ok\n\x81\x8d bozuk\n" + b"x" * 100)
    slow, _, _ = upload(settings, kb_id, "yavas.md", markdown(2))
    web, _, _ = upload(settings, kb_id, "sayfa.md", markdown(3))
    for doc in (good, bad, slow, web):
        process(settings, doc)
    pg.execute("UPDATE documents SET status = 'timeout' WHERE id = %s", (slow,))
    pg.execute("UPDATE documents SET convert_engine = 'mhtml+html_text' WHERE id = %s", (web,))
    return kb_id, {"good": good, "bad": bad, "slow": slow, "web": web}


@pytest.mark.parametrize(
    "preset,expected",
    [
        ("encoding", ["bozuk.txt"]),
        ("timeout", ["yavas.md"]),
        ("mhtml", ["sayfa.md"]),
        ("engine:mhtml+html_text", ["sayfa.md"]),
    ],
)
def test_04b_6_preset_reconverts_only_targets(pg, make_project, settings, preset, expected):
    kb_id, _ = _prepare_preset_kb(pg, make_project, settings)
    spy = SpyConverter()
    report = run(
        ingest.reindex_silver(
            kb_id,
            full=False,
            settings=settings,
            store=PgVectorStore(),
            embed_client=ingest.LocalEmbedClient(settings),
            convert=spy,
            preset=preset,
        )
    )
    assert spy.seen == expected
    assert report.documents == len(expected)


def test_04b_6_preset_count_matches_the_reconverted_set(pg, make_project, settings):
    kb_id, _ = _prepare_preset_kb(pg, make_project, settings)
    assert run(ingest.preset_document_count(kb_id, "encoding")) == 1
    assert run(ingest.preset_document_count(kb_id, "engine:nothing-like-this")) == 0


@pytest.mark.parametrize("preset", ["", "ENCODING", "engine:", "engine:a b", "audio", "x"])
def test_04b_6_unknown_preset_is_refused(preset):
    with pytest.raises(ingest.ReindexRefused) as caught:
        ingest.parse_preset(preset)
    assert caught.value.code == "preset_unknown"


# --- FOLLOWUP-86: the search names what it filtered and counts truncated rerank pairs ---


def _do_search(kb_id, reranker):
    async def go():
        async with db.session_scope() as session:
            kb = await session.get(KnowledgeBase, kb_id)
            result = await search.search(
                session,
                kb,
                "soru",
                filters=VectorFilters(),
                top_k=None,
                hybrid=False,
                run_id=None,
                user_id="u-1",
                source="api",
                settings=SETTINGS,
                store=PgVectorStore(),
                embedder=AxisEmbedder(),
                reranker=reranker,
            )
            await session.commit()
            return result

    return run(go())


SETTINGS = Settings(
    deploy_profile="llmaas",
    offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    fake_embed=True,
    **SETTINGS_03A,
)


class TruncatingReranker(TableReranker):
    def score_with_truncation(self, query, texts):
        scores = self.score(query, texts)
        return scores, ["uzun" in t for t in texts]


def test_04b_86_search_lists_rerank_floor_filtered_chunks(pg, make_project):
    kb_id = make_search_kb(pg, make_project())
    ids = index(
        kb_id,
        [("noise.pdf", "gurultu", _axis(0), None), ("good.pdf", "iyi uzun", _axis(0), None)],
    )
    result = _do_search(kb_id, TruncatingReranker({"gurultu": 0.05, "iyi": 0.7}))
    assert [h.chunk_id for h in result.hits] == [ids["good.pdf"]]
    (dropped,) = result.filtered
    assert dropped.chunk_id == ids["noise.pdf"] and dropped.reason == "below_rerank_floor"
    assert dropped.document_name == "noise.pdf"
    assert dropped.rerank_score == pytest.approx(0.05)
    assert result.rerank_truncated == 1


def test_04b_86_search_lists_min_score_filtered_chunks(pg, make_project):
    kb_id = make_search_kb(pg, make_project(), rerank=False, min_score=0.5)
    ids = index(
        kb_id,
        [("far.pdf", "uzak", _mix(0, 1, 3.0), None), ("near.pdf", "yakin", _axis(0), None)],
    )
    result = _do_search(kb_id, None)
    assert [h.chunk_id for h in result.hits] == [ids["near.pdf"]]
    (dropped,) = result.filtered
    assert (dropped.chunk_id, dropped.reason) == (ids["far.pdf"], "below_min_score")
    assert dropped.embed_score < 0.5 and dropped.rerank_score is None
    assert result.rerank_truncated == 0
