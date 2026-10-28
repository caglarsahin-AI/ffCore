"""Package 01: seed files and their validation (no database)."""

from pathlib import Path

import httpx2
import pytest
import yaml

from ffcore.core.egress import EgressPolicy
from ffcore.services.litellm_reconcile import _upstream
from ffcore.services.seed_models import SeedError, plan

SEED = Path(__file__).resolve().parents[3] / "deploy" / "seed"
LLMAAS_ENV = {
    "SEED_ANTHROPIC_API_KEY": "dummy-not-secret-anthropic",
    "SEED_AZURE_OPENAI_API_KEY": "dummy-not-secret-azure",
    "SEED_AZURE_OPENAI_API_BASE": "https://ffcore-eu.openai.azure.com",
    "SEED_AZURE_OPENAI_DEPLOYMENT": "gpt-eu",
}


def _doc(profile):
    return yaml.safe_load((SEED / f"models.{profile}.yaml").read_text(encoding="utf-8"))


@pytest.fixture
def llmaas(settings):
    settings.egress_allowlist = ["api.anthropic.com", "*.openai.azure.com"]
    return settings


@pytest.fixture
def airgap(settings):
    settings.deploy_profile = "airgap"
    settings.offline = True
    settings.inference_backend = "ollama"
    settings.allowed_internal_hosts = ["ollama", "vllm"]
    return settings


def test_01_seed_llmaas_full(llmaas):
    providers, models, skipped = plan(_doc("llmaas"), llmaas, LLMAAS_ENV)
    assert [p.key for p in providers] == ["anthropic", "azure-openai"]
    assert [m.body["key"] for m in models] == ["chat-default", "chat-fallback", "memory-extract"]
    assert skipped == []
    # Secrets resolved only into the provider config, which is never printed.
    assert "dummy-not-secret" not in repr(providers)


def test_01_seed_llmaas_without_fallback_reports_skip(llmaas):
    env = {"SEED_ANTHROPIC_API_KEY": "dummy-not-secret-anthropic"}
    providers, models, skipped = plan(_doc("llmaas"), llmaas, env)
    assert [p.key for p in providers] == ["anthropic"]
    assert "chat-fallback" not in [m.body["key"] for m in models]
    assert any("azure-openai" in s for s in skipped)


def test_01_seed_partial_optional_provider_is_an_error(llmaas):
    env = {"SEED_ANTHROPIC_API_KEY": "x", "SEED_AZURE_OPENAI_API_KEY": "dummy-not-secret"}
    with pytest.raises(SeedError, match="SEED_AZURE_OPENAI_API_BASE"):
        plan(_doc("llmaas"), llmaas, env)


def test_01_seed_required_secret_missing(llmaas):
    with pytest.raises(SeedError, match="SEED_ANTHROPIC_API_KEY"):
        plan(_doc("llmaas"), llmaas, {})


def test_01_1_seed_rejects_external_when_offline(llmaas):
    llmaas.offline = True
    with pytest.raises(SeedError, match="egress_offline"):
        plan(_doc("llmaas"), llmaas, LLMAAS_ENV)


def test_01_13_seed_rejects_external_fallback(airgap):
    doc = _doc("airgap")
    doc["providers"].append(
        {
            "key": "anthropic",
            "driver": "anthropic",
            "domains": ["model"],
            "config": {"api_key": "${SEED_ANTHROPIC_API_KEY}"},
        }
    )
    doc["models"].append(
        {
            "key": "chat-fallback",
            "display_name": "x",
            "provider": "anthropic",
            "model_id": "claude-sonnet-5-5",
        }
    )
    with pytest.raises(SeedError, match="egress_offline"):
        plan(doc, airgap, {"SEED_ANTHROPIC_API_KEY": "dummy-not-secret"})


def test_01_seed_airgap_has_no_external_provider_and_no_fallback(airgap):
    doc = _doc("airgap")
    for raw in doc["providers"]:
        config = {
            k: str(v).replace("${", "").split(":-")[-1].rstrip("}")
            for k, v in raw["config"].items()
        }
        base, _ = _upstream(raw["driver"], config, "x")
        EgressPolicy(airgap).check_url(httpx2.URL(base))  # internal only
    assert "chat-fallback" not in [m["key"] for m in doc["models"]]


@pytest.mark.parametrize(("backend", "provider"), [("ollama", "ollama"), ("vllm", "vllm")])
def test_01_seed_airgap_inference_backend_selects(airgap, backend, provider):
    airgap.inference_backend = backend
    providers, models, _ = plan(_doc("airgap"), airgap, {"SEED_VLLM_MODEL": "qwen-gpu"})
    assert [p.key for p in providers] == [provider]
    assert {m.provider for m in models} == {provider}
    assert [m.body["key"] for m in models] == ["chat-default", "memory-extract"]
    assert models[0].body["request_policy"] == {"extra_body": {"reasoning_effort": "none"}}


def test_01_seed_vllm_model_required(airgap):
    airgap.inference_backend = "vllm"
    with pytest.raises(SeedError, match="SEED_VLLM_MODEL"):
        plan(_doc("airgap"), airgap, {})


def test_01_seed_no_backend_no_models(airgap):
    airgap.inference_backend = None
    with pytest.raises(SeedError, match="no model"):
        plan(_doc("airgap"), airgap, {})


def test_01_seed_secret_literal_refused(llmaas):
    doc = _doc("llmaas")
    doc["providers"][0]["config"]["api_key"] = "sk-dummy-not-secret-literal"
    with pytest.raises(SeedError, match="must be a"):
        plan(doc, llmaas, LLMAAS_ENV)


def test_01_seed_invalid_model_fields(llmaas):
    doc = _doc("llmaas")
    doc["models"][0]["key"] = "Chat Default"
    with pytest.raises(SeedError, match="invalid fields"):
        plan(doc, llmaas, LLMAAS_ENV)
