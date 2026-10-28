"""scripts/smoke.py fail-loud behaviour (no network)."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "smoke.py"
spec = importlib.util.spec_from_file_location("smoke", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_00_1_smoke_says_skipped_when_ollama_profile_inactive(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "")
    assert smoke.check_ollama() == ["skipped: ollama profile inactive"]


def test_00_1_smoke_requires_context_length(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "ollama")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "")
    with pytest.raises(smoke.SmokeError, match="OLLAMA_CONTEXT_LENGTH"):
        smoke.check_ollama()


def test_00_1_smoke_fails_loud_on_missing_model(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "ollama")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "32768")
    monkeypatch.setenv("DEPLOY_PROFILE", "airgap")
    monkeypatch.setattr(
        smoke, "_request", lambda url, payload=None: (200, json.dumps({"models": []}).encode())
    )
    with pytest.raises(smoke.SmokeError, match="model_not_pulled: qwen3.5:35b; make pull"):
        smoke.check_ollama()


def test_00_1_smoke_rejects_context_above_model_limit(monkeypatch):
    monkeypatch.setenv("COMPOSE_PROFILES", "ollama")
    monkeypatch.setenv("OLLAMA_CONTEXT_LENGTH", "65536")
    monkeypatch.setenv("DEPLOY_PROFILE", "airgap")

    def fake(url, payload=None):
        if url.endswith("/api/tags"):
            return 200, json.dumps(
                {"models": [{"name": "qwen3.5:35b"}, {"name": "bge-m3:latest"}]}
            ).encode()
        return 200, json.dumps({"model_info": {"qwen.context_length": 32768}}).encode()

    monkeypatch.setattr(smoke, "_request", fake)
    with pytest.raises(smoke.SmokeError, match="exceeds"):
        smoke.check_ollama()
