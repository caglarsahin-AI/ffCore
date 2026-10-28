"""Hybrid search: normalize → embed → vector leg + lexical leg → RRF → rerank → floor (brief 04).

- The query passes the same normalizer configuration as silver (K1) and is logged with its id.
- Vector leg from the selected driver (C5); lexical leg per driver: Qdrant fuses bge-m3 sparse
  inside Qdrant, pgvector adds Postgres BM25 (`chunks.tsv`, turkish) here. Legs are fused with
  reciprocal rank fusion, k = 60 (PayCore retrieve.py), into RETRIEVAL_CANDIDATES (30).
- Single threshold rule (K2): reranker on → only the rerank floor RERANK_MIN_SCORE applies,
  the embedding score never pre-filters; reranker off → only `default_min_score` applies.
- Recency is shown, not scored (D5): hits are returned newest source first with their age.
- Every search writes one `kb_queries` row with the candidates and both scores (C12); what the
  floor or min_score removed is counted there, never dropped silently.
ACL and KB filters are in every query (C15), never applied after retrieval.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.config import Settings
from ffcore.knowledge.embed import Embedder, get_embedder
from ffcore.knowledge.normalize import NORMALIZER_CONFIG_ID, normalize_query
from ffcore.knowledge.rerank import Reranker, get_reranker
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorQuery, VectorStore
from ffcore.knowledge.vectorstore.pgvector import _literal
from ffcore.models.knowledge import SEARCHABLE_CHUNK_STATUSES, TSV_CONFIG, KbQuery, KnowledgeBase

RRF_K = 60
log = logging.getLogger("ffcore.knowledge.search")


@dataclass
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: str
    page: int | None
    section_path: str | None
    breadcrumb: str
    text: str
    chunk_status: str
    updated_at_source: datetime | None
    age_days: int | None
    embed_score: float | None
    rerank_score: float | None


@dataclass
class SearchResult:
    query_id: uuid.UUID
    hits: list[Hit]
    threshold_mode: str
    filtered_by_rerank_floor: int
    filtered_by_min_score: int
    normalizer_config_id: str
    latency_ms: int
    candidates: list[dict] = field(default_factory=list)


def _acl_sql(filters: VectorFilters, params: dict) -> str:
    acl = ["(cardinality(d.acl_roles) = 0 AND cardinality(d.acl_users) = 0)"]
    if filters.acl_roles:
        acl.append("d.acl_roles && CAST(:acl_roles AS text[])")
        params["acl_roles"] = list(filters.acl_roles)
    if filters.acl_users:
        acl.append("d.acl_users && CAST(:acl_users AS uuid[])")
        params["acl_users"] = list(filters.acl_users)
    return "(" + " OR ".join(acl) + ")"


async def _lexical(
    session: AsyncSession, kb_id: uuid.UUID, query: str, filters: VectorFilters, limit: int
) -> list[uuid.UUID]:
    """BM25-style leg: any query lexeme matches (OR), ranked by ts_rank_cd."""
    params: dict = {"kb_id": kb_id, "q": query, "limit": limit}
    clauses = [
        "c.kb_id = :kb_id",
        "c.chunk_status IN :searchable",
        "d.deleted_at IS NULL",
        _acl_sql(filters, params),
        "c.tsv @@ tsq.q",
    ]
    binds = [bindparam("searchable", expanding=True)]
    params["searchable"] = list(SEARCHABLE_CHUNK_STATUSES)
    if filters.document_ids:
        clauses.append("c.document_id IN :document_ids")
        binds.append(bindparam("document_ids", expanding=True))
        params["document_ids"] = list(filters.document_ids)
    for index, (key, value) in enumerate(filters.metadata):
        clauses.append(f"d.metadata ->> :mk{index} = :mv{index}")
        params[f"mk{index}"], params[f"mv{index}"] = key, str(value)
    statement = text(
        "WITH tsq AS (SELECT to_tsquery(:cfg, array_to_string("
        "tsvector_to_array(to_tsvector(:cfg, :q)), ' | ')) AS q) "
        "SELECT c.id FROM chunks c JOIN documents d ON d.id = c.document_id, tsq "
        f"WHERE {' AND '.join(clauses)} "
        "ORDER BY ts_rank_cd(c.tsv, tsq.q) DESC, c.id LIMIT :limit"
    ).bindparams(*binds)
    params["cfg"] = TSV_CONFIG
    lexemes = await session.scalar(
        text("SELECT cardinality(tsvector_to_array(to_tsvector(:cfg, :q)))"),
        {"cfg": TSV_CONFIG, "q": query},
    )
    if not lexemes:
        return []
    return list((await session.scalars(statement, params)).all())


def _rrf(legs: list[list[uuid.UUID]], limit: int) -> list[tuple[uuid.UUID, int]]:
    scores: dict[uuid.UUID, float] = {}
    for leg in legs:
        for rank, chunk_id in enumerate(leg, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + rank)
    ordered = sorted(scores, key=lambda c: (-scores[c], str(c)))[:limit]
    return [(chunk_id, rank) for rank, chunk_id in enumerate(ordered, start=1)]


async def _details(
    session: AsyncSession, ids: list[uuid.UUID], dense: list[float]
) -> dict[uuid.UUID, dict]:
    if not ids:
        return {}
    rows = await session.execute(
        text(
            "SELECT c.id, c.document_id, d.filename, c.page, c.section_path, c.breadcrumb,"
            " c.text, c.chunk_status, d.updated_at_source,"
            " CASE WHEN c.embedding IS NULL THEN NULL"
            " ELSE 1 - (c.embedding <=> CAST(:vec AS vector)) END AS embed_score"
            " FROM chunks c JOIN documents d ON d.id = c.document_id WHERE c.id IN :ids"
        ).bindparams(bindparam("ids", expanding=True)),
        {"ids": ids, "vec": _literal(dense)},
    )
    return {row.id: row._asdict() for row in rows}


async def search(
    session: AsyncSession,
    kb: KnowledgeBase,
    query: str,
    *,
    filters: VectorFilters,
    top_k: int | None,
    hybrid: bool | None,
    run_id: uuid.UUID | None,
    user_id: str | None,
    source: str,
    settings: Settings,
    store: VectorStore,
    embedder: Embedder | None = None,
    reranker: Reranker | None = None,
) -> SearchResult:
    started = time.monotonic()
    normalized = normalize_query(query)
    top_k = top_k or kb.default_top_k
    hybrid = kb.hybrid if hybrid is None else hybrid
    limit = settings.retrieval_candidates
    embedder = embedder or get_embedder(settings)
    embeddings = await asyncio.to_thread(embedder.encode, [normalized])
    dense, sparse = embeddings.dense[0], embeddings.sparse[0]

    # Qdrant fuses its sparse leg itself (C5); pgvector's lexical leg is Postgres BM25.
    sparse_query = sparse if (hybrid and store.name == "qdrant") else None
    vector_hits = await store.search(kb.id, VectorQuery(dense, sparse_query), filters, limit)
    legs = [[hit.chunk_id for hit in vector_hits]]
    if hybrid and store.name == "pgvector":
        legs.append(await _lexical(session, kb.id, normalized, filters, limit))
    fused = _rrf(legs, limit)
    details = await _details(session, [chunk_id for chunk_id, _ in fused], dense)

    candidates = []
    for chunk_id, rank in fused:
        row = details[chunk_id]
        candidates.append(
            {
                "chunk_id": str(chunk_id),
                "document_id": str(row["document_id"]),
                "rrf_rank": rank,
                "embed_score": row["embed_score"],
                "rerank_score": None,
                "below_rerank_floor": False,
                "below_min_score": False,
            }
        )

    filtered_floor = filtered_min = 0
    if kb.rerank:
        threshold_mode = "rerank_floor"
        reranker = reranker or get_reranker(settings)
        texts = [details[chunk_id]["text"] for chunk_id, _ in fused]
        scoring = getattr(reranker, "score_with_truncation", None)
        if scoring is not None:
            scores, cut = await asyncio.to_thread(scoring, normalized, texts)
        else:
            scores = await asyncio.to_thread(reranker.score, normalized, texts)
            cut = [False] * len(scores)
        for candidate, score, truncated in zip(candidates, scores, cut, strict=True):
            candidate["rerank_score"] = score
            candidate["below_rerank_floor"] = score < settings.rerank_min_score
            # Recorded with the candidate (C12), never cut silently (A-04a-0020).
            candidate["rerank_truncated"] = truncated
        if any(cut):
            log.warning("rerank_truncated kb=%s pairs=%d", kb.id, sum(cut))
        kept = [c for c in candidates if not c["below_rerank_floor"]]
        filtered_floor = len(candidates) - len(kept)
        kept.sort(key=lambda c: -c["rerank_score"])
    else:
        threshold_mode = "min_score"
        floor = kb.default_min_score
        for candidate in candidates:
            score = candidate["embed_score"]
            candidate["below_min_score"] = floor is not None and (score is None or score < floor)
        kept = [c for c in candidates if not c["below_min_score"]]
        filtered_min = len(candidates) - len(kept)
    kept = kept[:top_k]

    now = datetime.now(UTC)
    hits = []
    for candidate in kept:
        row = details[uuid.UUID(candidate["chunk_id"])]
        updated = row["updated_at_source"]
        hits.append(
            Hit(
                chunk_id=row["id"],
                document_id=row["document_id"],
                document_name=row["filename"],
                page=row["page"],
                section_path=row["section_path"],
                breadcrumb=row["breadcrumb"],
                text=row["text"],
                chunk_status=row["chunk_status"],
                updated_at_source=updated,
                age_days=(now - updated).days if updated else None,
                embed_score=row["embed_score"],
                rerank_score=candidate["rerank_score"],
            )
        )
    # Newest source first; undated last (recency is shown, the reranker chose the set).
    hits.sort(
        key=lambda h: (h.updated_at_source is None, -(h.updated_at_source or now).timestamp())
    )

    latency_ms = int((time.monotonic() - started) * 1000)
    embed_scores = [c["embed_score"] for c in candidates if c["embed_score"] is not None]
    rerank_scores = [c["rerank_score"] for c in candidates if c["rerank_score"] is not None]
    record = KbQuery(
        id=uuid.uuid4(),
        kb_id=kb.id,
        query=normalized,
        source=source,
        normalizer_config_id=NORMALIZER_CONFIG_ID,
        run_id=run_id,
        candidates=candidates,
        best_embed_score=max(embed_scores, default=None),
        best_rerank_score=max(rerank_scores, default=None),
        returned=len(hits),
        threshold_mode=threshold_mode,
        filtered_by_rerank_floor=filtered_floor,
        filtered_by_min_score=filtered_min,
        rerank_truncated=sum(1 for c in candidates if c.get("rerank_truncated")),
        latency_ms=latency_ms,
        user_id=user_id,
    )
    session.add(record)
    await session.flush()
    return SearchResult(
        query_id=record.id,
        hits=hits,
        threshold_mode=threshold_mode,
        filtered_by_rerank_floor=filtered_floor,
        filtered_by_min_score=filtered_min,
        normalizer_config_id=NORMALIZER_CONFIG_ID,
        latency_ms=latency_ms,
        candidates=candidates,
    )
