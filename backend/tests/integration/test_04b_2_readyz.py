"""04b-2 slice 6. S7 / FOLLOWUP-31 (K-04B-0021 S-c A, K-04B-0022): after the configuration check,
/readyz asks Ollama's `/api/ps` what context each loaded model really runs with
(`models[].context_length`). Smaller than the largest context_tokens → 503
`context_configuration_invalid`; the field missing → `ollama_ps_unexpected` (no silent pass); no
model loaded → skipped with a detail. The answer here is a stand-in: the field was not verified
against the pinned ollama 0.12.6 image (ENV-204).

S6 / FOLLOWUP-86: the ingest queue depth (arq's queue in Redis) is reported, information only.
"""

import asyncio

import pytest
import redis

from ffcore.core import readiness
from tests.integration import test_04a_readyz as r04a
from tests.integration.test_04a_readyz import _checks, _ollama_model

ready_app = r04a.ready_app
MODEL = "qwen3.5:35b"  # the model_id test_04a_readyz's helper registers


@pytest.fixture
def ollama_project(pg, make_project):
    """The database is shared by the session: the model is deactivated afterwards so 04a's own
    readiness tests see no Ollama model (as test_06a_readyz does for its agent)."""
    project_id = make_project()
    _ollama_model(pg, project_id, 16000)
    yield project_id
    pg.execute("UPDATE models SET is_active = false WHERE project_id = %s", (project_id,))


def _ollama(ready_app, monkeypatch, ps_models):
    async def fake_ps(config_encrypted, settings):
        return ps_models

    monkeypatch.setattr(readiness, "_ollama_ps", fake_ps)
    asyncio.run(readiness.warmup(ready_app["settings"]))
    ready_app["settings"] = ready_app["settings"].model_copy(
        update={"inference_backend": "ollama", "ollama_context_length": 32768}
    )


def test_04b_2_s7_loaded_model_context_is_checked(
    client_factory, ready_app, monkeypatch, ollama_project
):
    _ollama(ready_app, monkeypatch, [{"name": MODEL, "context_length": 32768}])
    ok = client_factory().get("/readyz")
    assert ok.status_code == 200, ok.text
    check = _checks(ok)["ollama_runtime_context"]
    assert check["status"] == "ok" and f"{MODEL}=32768" in check["detail"]


def test_04b_2_s7_smaller_runtime_context_is_503(
    client_factory, ready_app, monkeypatch, ollama_project
):
    _ollama(ready_app, monkeypatch, [{"name": MODEL, "context_length": 8192}])
    small = client_factory().get("/readyz")
    assert small.status_code == 503
    check = _checks(small)["ollama_runtime_context"]
    assert check["code"] == "context_configuration_invalid" and "8192" in check["detail"]


def test_04b_2_s7_missing_field_is_an_error(client_factory, ready_app, monkeypatch, ollama_project):
    _ollama(ready_app, monkeypatch, [{"name": MODEL, "size": 1}])
    response = client_factory().get("/readyz")
    assert response.status_code == 503
    check = _checks(response)["ollama_runtime_context"]
    assert check["code"] == "ollama_ps_unexpected" and "context_length" in check["detail"]


def test_04b_2_s7_not_loaded_is_skipped_with_detail(
    client_factory, ready_app, monkeypatch, ollama_project
):
    _ollama(ready_app, monkeypatch, [])
    response = client_factory().get("/readyz")
    assert response.status_code == 200, response.text
    check = _checks(response)["ollama_runtime_context"]
    assert check["status"] == "skipped" and MODEL in check["detail"]
    assert "not loaded" in check["detail"]


def test_04b_2_s7_not_ollama_is_skipped(client_factory, ready_app):
    asyncio.run(readiness.warmup(ready_app["settings"]))
    check = _checks(client_factory().get("/readyz"))["ollama_runtime_context"]
    assert check["status"] == "skipped"


def test_04b_2_s6_ingest_queue_depth(client_factory, ready_app):
    settings = ready_app["settings"]
    asyncio.run(readiness.warmup(settings))
    client = redis.Redis.from_url(settings.redis_url.get_secret_value())
    queue = f"{settings.arq_queue_ingest}-04b2-test"
    ready_app["settings"] = settings.model_copy(update={"arq_queue_ingest": queue})
    try:
        client.zadd(queue, {"job-a": 1, "job-b": 2, "job-c": 3})
        response = client_factory().get("/readyz")
        check = _checks(response)["ingest_queue"]
        assert check["status"] == "ok" and check["detail"] == "queued=3"
    finally:
        client.delete(queue)
        client.close()


# --- r2 (K-04B-0026) ---


@pytest.fixture
def untagged_project(pg, make_project):
    """An active Ollama model registered without a tag (`llama3`); Ollama lists it `:latest`."""
    import json
    import uuid

    project_id = make_project()
    provider = uuid.uuid4()
    pg.execute(
        "INSERT INTO providers (id, key, label, driver, domains, config_encrypted,"
        " supports_test, created_by) VALUES (%s, %s, 'Ollama', 'ollama', '{model}', %s, true,"
        " 'test')",
        (provider, f"ol-{provider.hex[:8]}", b"x"),
    )
    pg.execute(
        "INSERT INTO models (id, project_id, key, display_name, provider_id, category, model_id,"
        " capabilities, input_types, pricing, limits, upstream_api, request_policy, created_by)"
        " VALUES (%s, %s, 'chat-untagged', 'Chat', %s, 'llm', 'llama3', '{}', '{text}',"
        " '{}', %s, 'chat', '{}', 'test')",
        (uuid.uuid4(), project_id, provider, json.dumps({"context_tokens": 16000})),
    )
    yield project_id
    pg.execute("UPDATE models SET is_active = false WHERE project_id = %s", (project_id,))


def test_04b_2_r2_untagged_model_matches_latest(
    client_factory, ready_app, monkeypatch, untagged_project
):
    """MINOR-2: `llama3` and `llama3:latest` are one model; a small context is caught."""
    _ollama(ready_app, monkeypatch, [{"name": "llama3:latest", "context_length": 8192}])
    small = client_factory().get("/readyz")
    assert small.status_code == 503
    check = _checks(small)["ollama_runtime_context"]
    assert check["code"] == "context_configuration_invalid" and "llama3=8192" in check["detail"]


def test_04b_2_r2_ps_shape_error_is_unexpected(
    client_factory, ready_app, monkeypatch, ollama_project
):
    """NOTE-1 (P4): Ollama answered, but not in the documented shape."""

    async def odd_ps(config_encrypted, settings):
        raise readiness.OllamaPsUnexpected("/api/ps answer has no models list")

    asyncio.run(readiness.warmup(ready_app["settings"]))
    monkeypatch.setattr(readiness, "_ollama_ps", odd_ps)
    ready_app["settings"] = ready_app["settings"].model_copy(
        update={"inference_backend": "ollama", "ollama_context_length": 32768}
    )
    response = client_factory().get("/readyz")
    assert response.status_code == 503
    check = _checks(response)["ollama_runtime_context"]
    assert check["code"] == "ollama_ps_unexpected" and "models" in check["detail"]
