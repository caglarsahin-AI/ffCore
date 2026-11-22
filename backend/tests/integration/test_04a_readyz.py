"""04a acceptance 17: warmup and /readyz (moved from 00; C13 context check, FOLLOWUP-31)."""

import asyncio
import json
import uuid

import pytest

from ffcore.core import readiness


@pytest.fixture
def ready_app(app, app_settings, monkeypatch):
    import ffcore.main
    from ffcore.core.config import get_settings

    async def no_warmup(settings):
        return None

    # The test drives warmup itself; the lifespan's background task would race it.
    monkeypatch.setattr(ffcore.main, "warmup", no_warmup)

    async def nothing_loaded(config_encrypted, settings):
        return []

    # 04b-2 S7: no Ollama answers here (the providers' configs are dummies); by default no model
    # is loaded, so the runtime check is skipped. test_04b_2_readyz sets the answers it needs.
    monkeypatch.setattr(readiness, "_ollama_ps", nothing_loaded, raising=False)

    holder = {"settings": app_settings.model_copy(update={"fake_embed": True})}
    app.dependency_overrides[get_settings] = lambda: holder["settings"]
    readiness.reset()
    yield holder
    readiness.reset()


def _checks(response):
    return {c["name"]: c for c in response.json()["checks"]}


def test_04a_17a_readyz_warming_then_ready(client_factory, ready_app):
    client = client_factory()
    warming = client.get("/readyz")
    assert warming.status_code == 503 and warming.json()["status"] == "warming"
    assert _checks(warming)["warmup"]["code"] == "warming"
    asyncio.run(readiness.warmup(ready_app["settings"]))
    ready = client.get("/readyz")
    assert ready.status_code == 200, ready.text
    assert ready.json()["status"] == "ready"
    assert _checks(ready)["models"]["detail"].startswith("FAKE_EMBED=1")


def test_04a_17a_warmup_failure_is_reported(client_factory, ready_app, monkeypatch):
    def broken(settings):
        raise RuntimeError("weights missing")

    monkeypatch.setattr(readiness, "_load_models", broken)
    asyncio.run(readiness.warmup(ready_app["settings"]))
    response = client_factory().get("/readyz")
    assert response.status_code == 503
    assert _checks(response)["warmup"]["code"] == "warmup_failed"


def _ollama_model(pg, project_id, context_window, key="context_window"):
    """An active Ollama LLM model; `limits.context_window` is its window (FOLLOWUP-219). `key`
    writes another limits key straight into the row (the API cannot: ModelLimits is strict)."""
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
        " VALUES (%s, %s, 'chat-default', 'Chat', %s, 'llm', 'qwen3.5:35b', '{}', '{text}',"
        " '{}', %s, 'chat', '{}', 'test')",
        (uuid.uuid4(), project_id, provider, json.dumps({key: context_window})),
    )


def test_04a_17b_context_configuration_invalid(client_factory, ready_app, pg, make_project):
    asyncio.run(readiness.warmup(ready_app["settings"]))
    client = client_factory()
    base = ready_app["settings"].model_copy(update={"inference_backend": "ollama"})

    ready_app["settings"] = base.model_copy(update={"ollama_context_length": None})
    none_yet = client.get("/readyz")
    assert _checks(none_yet)["ollama_context"]["status"] == "skipped"

    project_id = make_project()
    _ollama_model(pg, project_id, 16000)
    ready_app["settings"] = base.model_copy(update={"ollama_context_length": 8192})
    small = client.get("/readyz")
    assert small.status_code == 503
    assert _checks(small)["ollama_context"]["code"] == "context_configuration_invalid"

    ready_app["settings"] = base.model_copy(update={"ollama_context_length": None})
    missing = client.get("/readyz")
    assert _checks(missing)["ollama_context"]["code"] == "context_configuration_invalid"

    ready_app["settings"] = base.model_copy(update={"ollama_context_length": 32768})
    ok = client.get("/readyz")
    assert ok.status_code == 200
    assert "largest needed context=16000" in _checks(ok)["ollama_context"]["detail"]
    pg.execute("UPDATE models SET is_active = false WHERE project_id = %s", (project_id,))


def test_04a_17b_legacy_context_tokens_key_is_not_counted(
    client_factory, ready_app, pg, make_project
):
    """FOLLOWUP-219 A (S5): a model's window is `limits.context_window` only. The old
    `context_tokens` key (not writable through the API) is not a second path: it is not counted."""
    asyncio.run(readiness.warmup(ready_app["settings"]))
    project_id = make_project()
    _ollama_model(pg, project_id, 900000, key="context_tokens")
    ready_app["settings"] = ready_app["settings"].model_copy(
        update={"inference_backend": "ollama", "ollama_context_length": 32768}
    )
    try:
        response = client_factory().get("/readyz")
        check = _checks(response)["ollama_context"]
        assert check["status"] in ("ok", "skipped"), check
        assert "900000" not in (check["detail"] or "")
    finally:
        pg.execute("UPDATE models SET is_active = false WHERE project_id = %s", (project_id,))


def test_04a_17_embed_dim_column_mismatch(client_factory, ready_app):
    asyncio.run(readiness.warmup(ready_app["settings"]))
    ready_app["settings"] = ready_app["settings"].model_copy(update={"embed_dim": 768})
    response = client_factory().get("/readyz")
    assert response.status_code == 503
    assert _checks(response)["embed_dim"]["code"] == "embed_dim_mismatch"
