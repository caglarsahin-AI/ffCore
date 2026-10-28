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
