"""04a slice 4 with the real models: bge-m3 (dense + sparse) and bge-reranker-v2-m3."""

import asyncio

import pytest

from ffcore.core.config import Settings
from ffcore.knowledge.embed import BgeM3Embedder, probe_dimension
from ffcore.knowledge.rerank import BgeReranker
from tests.dummy import SETTINGS_03A

pytestmark = pytest.mark.models

SETTINGS = Settings(
    deploy_profile="airgap",
    offline=False,
    service_token="dummy-not-secret-service-token-0123456789",
    obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
    **SETTINGS_03A,
)


def test_04a_bge_m3_dense_and_sparse():
    out = BgeM3Embedder(SETTINGS.embed_model, SETTINGS.embed_dim).encode(
        ["Fesih bildirim süresi doksan gündür.", "Temizlik hizmeti haftada beş gün verilir."]
    )
    assert len(out.dense) == 2 and len(out.dense[0]) == 1024
    assert all(out.sparse) and out.truncated == [False, False]


def test_04a_bge_m3_reports_truncation():
    long_text = " ".join(f"kelime{i}" for i in range(12_000))
    out = BgeM3Embedder(SETTINGS.embed_model, SETTINGS.embed_dim).encode([long_text])
    assert out.truncated == [True]


def test_04a_probe_measures_installation_dimension():
    assert asyncio.run(probe_dimension({}, SETTINGS.embed_model, SETTINGS)) == 1024


def test_04a_reranker_orders_relevant_first():
    scores = BgeReranker(SETTINGS.rerank_model).score(
        "fesih bildirim süresi kaç gün",
        [
            "Taraflar sözleşmeyi 90 gün önceden yazılı bildirimle feshedebilir.",
            "Otopark ücretsizdir.",
        ],
    )
    assert 0.0 <= min(scores) and max(scores) <= 1.0
    assert scores[0] > scores[1] and scores[0] >= SETTINGS.rerank_min_score


def test_04a_reranker_reads_the_end_of_a_full_chunk():
    """A-04a-0020: the answer at token ~550 of a 600-token chunk must reach the reranker
    (max_length 512 had cut it: 0.0009 instead of 0.90)."""
    filler = " ".join(
        f"Madde {i} - Hüküm {i}.1 Taraflar bu maddedeki yükümlülükleri yerine getirir ve "
        "yazılı bildirimlerini idareye iletir."
        for i in range(1, 30)
    )
    text = filler + " Madde 30 - Fesih 30.1 Fesih bildirim süresi en az 90 gündür."
    reranker = BgeReranker(SETTINGS.rerank_model)
    scores, truncated = reranker.score_with_truncation("fesih bildirim süresi", [text])
    assert truncated == [False]
    assert scores[0] >= 0.5, scores


def test_04a_reranker_flags_pairs_over_its_limit():
    text = " ".join(f"kelime{i}" for i in range(3000))
    scores, truncated = BgeReranker(SETTINGS.rerank_model).score_with_truncation("soru", [text])
    assert truncated == [True] and len(scores) == 1
