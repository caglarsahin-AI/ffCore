"""Package 02 / fix(01): models.pricing reaches LiteLLM's cost calculation (02 S2, measured M3).

LiteLLM computes the response cost only from input/output_cost_per_token in litellm_params; the
same values in model_info alone left every cost at 0.
"""

import uuid
from types import SimpleNamespace

import pytest

from ffcore.services.litellm_reconcile import desired_model


def _model(pricing):
    return SimpleNamespace(
        id=uuid.uuid4(),
        key="chat-default",
        category="llm",
        model_id="ok-model",
        capabilities={},
        input_types=["text"],
        pricing=pricing,
        limits={},
        upstream_api="chat",
        request_policy={},
    )


PROVIDER = SimpleNamespace(
    driver="openai_compatible", config={"base_url": "http://fake-llm:9999/v1"}
)


def test_02_7_pricing_reaches_litellm_params(settings):
    settings.allowed_internal_hosts = ["fake-llm"]
    d = desired_model(
        "p",
        _model({"input_per_1m": 3, "output_per_1m": 15, "cached_per_1m": 1.5}),
        PROVIDER,
        settings,
    )
    assert d.litellm_params["input_cost_per_token"] == pytest.approx(3e-6)
    assert d.litellm_params["output_cost_per_token"] == pytest.approx(15e-6)
    assert d.litellm_params["cache_read_input_token_cost"] == pytest.approx(1.5e-6)


def test_02_7_price_change_changes_hash(settings):
    settings.allowed_internal_hosts = ["fake-llm"]
    a = desired_model("p", _model({"input_per_1m": 3, "output_per_1m": 15}), PROVIDER, settings)
    b = desired_model("p", _model({"input_per_1m": 4, "output_per_1m": 15}), PROVIDER, settings)
    assert a.model_info["ffcore_hash"] != b.model_info["ffcore_hash"]


def test_02_7_no_price_no_cost_params(settings):
    settings.allowed_internal_hosts = ["fake-llm"]
    d = desired_model("p", _model({}), PROVIDER, settings)
    assert "input_cost_per_token" not in d.litellm_params
