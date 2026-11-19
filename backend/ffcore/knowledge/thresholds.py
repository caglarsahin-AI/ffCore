"""Score thresholds per embedding model (brief 04 "eşik tablosu", 04b-2 D5) and the query
statistics a screen uses to suggest one.

The table holds only measured values (K-04B-0021 S-a A). The rerank floor 0.1 for
bge-reranker-v2-m3 is PayCore's measurement (RERANK_MIN_SCORE, source accuracy 100 % at 0.1); an
embedding `min_score` for bge-m3 was never measured, and the e5 comparison is a measurement on the
target machine, outside this package. "Not measured" stays null, never a guessed number.

`query_stats` only informs: it reads `kb_queries` and never changes a threshold (no "auto").
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ThresholdRow:
    embed_model: str
    rerank_model: str | None
    rerank_min_score: float | None
    min_score: float | None
    note: str


TABLE: dict[str, ThresholdRow] = {
    row.embed_model: row
    for row in (
        ThresholdRow(
            "BAAI/bge-m3",
            "BAAI/bge-reranker-v2-m3",
            0.1,
            None,
            "rerank floor measured by PayCore (RERANK_MIN_SCORE 0.1); embedding min_score not "
            "measured: with the reranker on it does not filter (single threshold rule)",
        ),
        ThresholdRow(
            "intfloat/multilingual-e5-large",
            None,
            None,
            None,
            "not measured (the Turkish embedding comparison runs on the target machine)",
        ),
    )
}


def row(embed_model: str) -> ThresholdRow | None:
    return TABLE.get(embed_model)


@dataclass(frozen=True)
class ScoreStats:
    threshold: float | None
    scored: int
    below: int | None
    below_ratio: float | None
    p10: float | None
    p50: float | None
    p90: float | None


@dataclass(frozen=True)
class QueryStats:
    days: int
    queries: int
    zero_result: int
    zero_result_ratio: float | None
    rerank: ScoreStats
    embed: ScoreStats


_STATS = text(
    "SELECT count(*) AS queries,"
    " count(*) FILTER (WHERE returned = 0) AS zero_result,"
    " count(best_rerank_score) AS rerank_scored,"
    " count(*) FILTER (WHERE best_rerank_score < :rerank_threshold) AS rerank_below,"
    " percentile_cont(ARRAY[0.1, 0.5, 0.9]) WITHIN GROUP (ORDER BY best_rerank_score)"
    "   AS rerank_p,"
    " count(best_embed_score) AS embed_scored,"
    " count(*) FILTER (WHERE best_embed_score < :embed_threshold) AS embed_below,"
    " percentile_cont(ARRAY[0.1, 0.5, 0.9]) WITHIN GROUP (ORDER BY best_embed_score) AS embed_p"
    " FROM kb_queries WHERE kb_id = :kb AND ts >= now() - make_interval(days => :days)"
)


def _ratio(part: int | None, whole: int) -> float | None:
    return None if part is None or whole == 0 else part / whole


def _scores(threshold, scored, below, percentiles) -> ScoreStats:
    p10, p50, p90 = percentiles if percentiles else (None, None, None)
    below = below if threshold is not None else None
    return ScoreStats(threshold, scored, below, _ratio(below, scored), p10, p50, p90)


async def query_stats(
    session: AsyncSession,
    kb_id: UUID,
    *,
    days: int,
    rerank_threshold: float,
    embed_threshold: float | None,
) -> QueryStats:
    """Best score per query against the thresholds in force, over the last `days` days."""
    r = (
        await session.execute(
            _STATS,
            {
                "kb": kb_id,
                "days": days,
                "rerank_threshold": rerank_threshold,
                # NULL: no embedding threshold in force, nothing is below it.
                "embed_threshold": embed_threshold,
            },
        )
    ).one()
    return QueryStats(
        days=days,
        queries=r.queries,
        zero_result=r.zero_result,
        zero_result_ratio=_ratio(r.zero_result, r.queries),
        rerank=_scores(rerank_threshold, r.rerank_scored, r.rerank_below, r.rerank_p),
        embed=_scores(embed_threshold, r.embed_scored, r.embed_below, r.embed_p),
    )
