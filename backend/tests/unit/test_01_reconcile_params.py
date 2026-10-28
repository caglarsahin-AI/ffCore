"""Package 01: table row -> LiteLLM deployment (pure mapping, no network)."""

import uuid
from types import SimpleNamespace

import pytest

from ffcore.services.litellm_reconcile import ReconcileProblem, desired_model

FERNETLESS = {"api_key": "dummy-not-secret-provider-key"}


def _model(**over):
    base = dict(
        id=uuid.uuid4(),
        key="chat-default",
        category="llm",
        model_id="claude-sonnet-5-5",
        capabilities={"tool_calls": True, "reasoning": True, "structured_outputs": False},
        input_types=["text"],
        pricing={"input_per_1m": 3, "output_per_1m": 15, "cached_per_1m": None},
        limits={"context_window": 200000, "max_output": 8192, "temperature": None},
        upstream_api="chat",
        request_policy={"extra_body": {"reasoning_effort": "none"}, "reject_params": ["top_k"]},
    )
    base.update(over)
    return SimpleNamespace(**base)


def _provider(driver="anthropic", config=None):
    return SimpleNamespace(driver=driver, config=dict(config or FERNETLESS))


def _desired(settings, model=None, provider=None, project_key="hastane"):
    return desired_model(project_key, model or _model(), provider or _provider(), settings)


def test_01_c1_litellm_name_and_id(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    model = _model()
    d = _desired(settings, model)
    assert d.name == "hastane.chat-default"
    assert d.model_info["id"] == str(model.id)
    assert d.model_info["ffcore_managed"] is True


@pytest.mark.parametrize(
    ("driver", "config", "prefix", "base"),
    [
        ("anthropic", FERNETLESS, "anthropic/", None),
        ("openai", FERNETLESS, "openai/", None),
        (
            "openai_compatible",
            {"base_url": "http://fake-llm:9999/v1"},
            "openai/",
            "http://fake-llm:9999/v1",
        ),
        ("ollama", {"base_url": "http://ollama:11434"}, "openai/", "http://ollama:11434/v1"),
        ("vllm", {"base_url": "http://vllm:8000"}, "hosted_vllm/", "http://vllm:8000/v1"),
    ],
)
def test_01_driver_prefix(settings, driver, config, prefix, base):
    settings.allowed_internal_hosts = ["fake-llm", "ollama", "vllm"]
    settings.egress_allowlist = ["api.anthropic.com", "api.openai.com"]
    d = _desired(settings, provider=_provider(driver, config))
    assert d.litellm_params["model"] == prefix + "claude-sonnet-5-5"
    assert d.litellm_params.get("api_base") == base


def test_01_9_extra_body_and_policy(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    p = _desired(settings).litellm_params
    assert p["extra_body"] == {"reasoning_effort": "none"}
    assert p["additional_drop_params"] == ["top_k"]
    assert p["num_retries"] == 2
    assert "reasoning_effort" not in p  # direct param is refused by LiteLLM for unknown models


@pytest.mark.parametrize(("timeout", "expected"), [(60, 60), (600, 600), (120, 120)])
def test_01_11_timeout_from_settings(settings, timeout, expected):
    settings.egress_allowlist = ["api.anthropic.com"]
    settings.llm_call_timeout_s = timeout
    assert _desired(settings).litellm_params["timeout"] == expected


def test_01_pricing_and_capabilities(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    info = _desired(settings).model_info
    assert info["input_cost_per_token"] == pytest.approx(3e-6)
    assert info["output_cost_per_token"] == pytest.approx(15e-6)
    assert info["supports_function_calling"] is True
    assert info["max_input_tokens"] == 200000


def test_01_1_offline_refuses_external(settings):
    settings.offline = True
    with pytest.raises(ReconcileProblem) as err:
        _desired(settings)
    assert err.value.code == "egress_offline"


def test_01_1_not_allowlisted_refused(settings):
    with pytest.raises(ReconcileProblem) as err:
        _desired(settings)
    assert err.value.code == "egress_not_allowlisted"


def test_01_responses_api_is_loud(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    with pytest.raises(ReconcileProblem) as err:
        _desired(settings, _model(upstream_api="responses"))
    assert err.value.code == "upstream_api_unsupported"


def test_01_forward_unknown_params_is_loud(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    policy = {"forward_unknown_params": True}
    with pytest.raises(ReconcileProblem) as err:
        _desired(settings, _model(request_policy=policy))
    assert err.value.code == "forward_unknown_params_unsupported"


def test_01_hash_changes_with_key_but_hides_it(settings):
    settings.egress_allowlist = ["api.anthropic.com"]
    model = _model()
    a = _desired(settings, model, _provider(config={"api_key": "dummy-not-secret-a"}))
    b = _desired(settings, model, _provider(config={"api_key": "dummy-not-secret-b"}))
    assert a.model_info["ffcore_hash"] != b.model_info["ffcore_hash"]
    assert "dummy-not-secret" not in repr(a)
