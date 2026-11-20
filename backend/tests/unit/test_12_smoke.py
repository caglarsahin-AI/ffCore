"""12-1: smoke runs the compose preflight first and catches LiteLLM's half-migrated schema.

FOLLOWUP-35: an incoherent profile/overlay combination fails smoke by name (it ran nowhere
before). FOLLOWUP-82: LiteLLM can come up healthy on a half-migrated schema (`/key/info` 500);
smoke asks `/key/info` with the master key for a key that does not exist.
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "smoke.py"
spec = importlib.util.spec_from_file_location("smoke12", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_12_smoke_runs_the_preflight_first():
    assert smoke.CHECKS[0] is smoke.check_preflight


def test_12_35_smoke_fails_on_incoherent_profiles(monkeypatch):
    monkeypatch.setenv("DEPLOY_PROFILE", "airgap")
    monkeypatch.setenv("INFERENCE_BACKEND", "ollama")
    monkeypatch.setenv("COMPOSE_PROFILES", "ollama")
    monkeypatch.setenv("COMPOSE_FILE", "compose.yaml")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "32768")
    with pytest.raises(smoke.SmokeError, match="profile_overlay_mismatch"):
        smoke.check_preflight()


def test_12_smoke_fails_on_egress_without_allowlist(monkeypatch):
    monkeypatch.setenv("DEPLOY_PROFILE", "llmaas")
    monkeypatch.setenv("COMPOSE_PROFILES", "egress,tls")
    monkeypatch.setenv(
        "COMPOSE_FILE", "compose.yaml:deploy/docker-compose.egress.yml:deploy/docker-compose.tls.yml"
    )
    monkeypatch.setenv("EGRESS_ALLOWLIST", "")
    with pytest.raises(smoke.SmokeError, match="egress_allowlist_empty"):
        smoke.check_preflight()


def _litellm(monkeypatch, key_info_status):
    calls = []

    def fake(url, payload=None, headers=None):
        calls.append((url, headers))
        if "/key/info" in url:
            return key_info_status, b"{}"
        return 200, b"{}"

    monkeypatch.setenv("LITELLM_MASTER_KEY", "dummy-master")
    monkeypatch.setattr(smoke, "_request", fake)
    return calls


def test_12_82_smoke_fails_on_half_migrated_litellm(monkeypatch):
    _litellm(monkeypatch, 500)
    with pytest.raises(smoke.SmokeError, match="litellm_schema_incomplete"):
        smoke.check_litellm()


@pytest.mark.parametrize("status", [401, 403])
def test_12_82_smoke_fails_on_rejected_master_key(monkeypatch, status):
    _litellm(monkeypatch, status)
    with pytest.raises(smoke.SmokeError, match="master key"):
        smoke.check_litellm()


@pytest.mark.parametrize("status", [200, 400, 404])
def test_12_82_smoke_passes_when_the_key_table_answers(monkeypatch, status):
    calls = _litellm(monkeypatch, status)
    line = smoke.check_litellm()
    assert "/key/info" in line
    url, headers = calls[-1]
    assert headers == {"Authorization": "Bearer dummy-master"}


def test_12_82_smoke_needs_the_master_key(monkeypatch):
    _litellm(monkeypatch, 404)
    monkeypatch.delenv("LITELLM_MASTER_KEY")
    with pytest.raises(smoke.SmokeError, match="LITELLM_MASTER_KEY"):
        smoke.check_litellm()
