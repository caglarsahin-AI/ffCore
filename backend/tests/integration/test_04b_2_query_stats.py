"""04b-2 slice 5, D5 (K-04B-0021 S-a A). The threshold table per embedding model holds only what
was measured: bge-m3 with bge-reranker-v2-m3 has the rerank floor 0.1 (PayCore's measurement);
an embedding `min_score` for bge-m3 and the e5 row are "not measured" (null), never invented.
`GET …/query-stats` gives the numbers a screen needs to warn "X% of queries are below the
threshold"; it only informs, it never changes a threshold (no "auto")."""

import uuid
from datetime import UTC, datetime, timedelta

from ffcore.knowledge import thresholds
from tests.integration import test_04a_api as kb_api
from tests.integration.test_04a_api import create_kb, kb_url

queue = kb_api.queue
settings = kb_api.settings
world = kb_api.world


def test_04b_2_d5_table_has_only_measured_values():
    bge = thresholds.row("BAAI/bge-m3")
    assert bge.rerank_model == "BAAI/bge-reranker-v2-m3" and bge.rerank_min_score == 0.1
    assert bge.min_score is None and "not measured" in bge.note
    e5 = thresholds.row("intfloat/multilingual-e5-large")
    assert (e5.rerank_min_score, e5.min_score) == (None, None) and "not measured" in e5.note
    assert thresholds.row("unknown/model") is None


def _query(pg, kb_id, *, rerank, embed, returned, mode="rerank_floor", age_days=0):
    pg.execute(
        "INSERT INTO kb_queries (id, kb_id, query, source, normalizer_config_id, candidates,"
        " best_embed_score, best_rerank_score, returned, threshold_mode,"
        " filtered_by_rerank_floor, filtered_by_min_score, latency_ms, ts)"
        " VALUES (%s, %s, 'q', 'api', 'format-v1', '[]', %s, %s, %s, %s, 0, 0, 10, %s)",
        (
            uuid.uuid4(),
            kb_id,
            embed,
            rerank,
            returned,
            mode,
            datetime.now(UTC) - timedelta(days=age_days),
        ),
    )


def test_04b_2_d5_query_stats_inform_only(world, settings, pg):
    kb = create_kb(world)
    for rerank, embed, returned in [
        (0.9, 0.7, 3),
        (0.5, 0.6, 2),
        (0.05, 0.4, 0),  # below the rerank floor 0.1: nothing returned
        (0.02, 0.3, 0),
        (None, None, 0),  # no candidates at all
    ]:
        _query(pg, kb["id"], rerank=rerank, embed=embed, returned=returned)
    _query(pg, kb["id"], rerank=0.01, embed=0.1, returned=0, age_days=40)  # outside 30 days

    url = f"{kb_url(world, kb['id'])}/query-stats?days=30"
    response = world["admin_read"].get(url)  # a reader, also in read mode
    assert response.status_code == 200, response.text
    stats = response.json()
    assert stats["days"] == 30 and stats["queries"] == 5
    assert stats["zero_result"] == 3 and round(stats["zero_result_ratio"], 2) == 0.6
    rerank = stats["rerank"]
    assert rerank["threshold"] == 0.1 and rerank["scored"] == 4 and rerank["below"] == 2
    assert round(rerank["below_ratio"], 2) == 0.5
    assert rerank["p50"] is not None and rerank["p10"] <= rerank["p50"] <= rerank["p90"]
    embed = stats["embed"]
    assert embed["threshold"] is None and embed["below"] is None  # KB has no min_score
    assert embed["scored"] == 4
    assert stats["table"] == {
        "embed_model": "BAAI/bge-m3",
        "rerank_model": "BAAI/bge-reranker-v2-m3",
        "rerank_min_score": 0.1,
        "min_score": None,
        "note": thresholds.row("BAAI/bge-m3").note,
    }
    after = world["admin"].get(kb_url(world, kb["id"])).json()
    assert after["default_min_score"] is None  # nothing was changed


def test_04b_2_d5_days_bounds(world, settings):
    kb = create_kb(world)
    base = f"{kb_url(world, kb['id'])}/query-stats"
    assert world["admin"].get(base).json()["days"] == 30
    assert world["admin"].get(f"{base}?days=0").status_code == 422
    assert world["admin"].get(f"{base}?days=366").status_code == 422
