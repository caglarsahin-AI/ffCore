"""Package 01: litellm_client through the real LiteLLM container to the fake provider.

Model ids select the fake's behaviour: `fail-*` is a provider that is down, `slow-*` streams for
about five seconds, anything else answers "hello" (tests/fakes/fake_openai.py).
"""

import asyncio
import threading

import pytest

from ffcore.core import db
from ffcore.services.litellm_client import (
    FallbackObserved,
    LiteLLMClient,
    ModelUnavailable,
    resolve_target,
)
from tests.integration.litellm_support import (
    fake_requests,
    litellm_models,
    project_key,
    run_reconcile,
)

pytestmark = pytest.mark.usefixtures("clean_litellm")
MESSAGES = [{"role": "user", "content": "hi"}]
META = {"project_id": "p", "agent_key": None, "run_id": None, "channel": "test"}


def _call(database_url, settings, project_id, key="chat-default", stream=False):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                target = await resolve_target(session, project_id, key)
            async with LiteLLMClient(settings) as client:
                if not stream:
                    return await client.chat(target, MESSAGES, user="u1", metadata=META)
                async with client.chat_stream(target, MESSAGES, user="u1", metadata=META) as s:
                    chunks = [c async for c in s]
                return chunks, s.result
        finally:
            db.reset()

    return asyncio.run(go())


@pytest.fixture
def project(catalog):
    project_id = catalog.project()
    return project_id, catalog.provider([project_id])


def test_01_2_fallback_observed_plain(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider, key="chat-default", model_id="fail-primary")
    catalog.model(project_id, provider, key="chat-fallback", model_id="ok-backup")
    run_reconcile(database_url, llm_settings)

    result = _call(database_url, llm_settings, project_id)

    key = project_key(pg, project_id)
    assert result.fallback == FallbackObserved(
        f"{key}.chat-default", f"{key}.chat-fallback", "primary_failed"
    )
    assert result.content == "hello"


def test_01_2_fallback_observed_stream(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider, key="chat-default", model_id="fail-primary")
    catalog.model(project_id, provider, key="chat-fallback", model_id="ok-backup")
    run_reconcile(database_url, llm_settings)

    _, result = _call(database_url, llm_settings, project_id, stream=True)

    assert result.fallback is not None
    assert result.fallback.target_model == f"{project_key(pg, project_id)}.chat-fallback"


def test_01_2_no_fallback_record_503(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider, key="chat-default", model_id="fail-primary")
    run_reconcile(database_url, llm_settings)

    with pytest.raises(ModelUnavailable) as err:
        _call(database_url, llm_settings, project_id)

    assert err.value.status_code == 503 and err.value.code == "model_unavailable"
    # Only the primary was tried (1 + 2 retries at most); nothing else was called.
    assert {r["model"] for r in fake_requests()} == {"fail-primary"}


def test_01_2_airgap_upstream_down_503_no_fallback(
    database_url, pg, catalog, project, llm_settings
):
    """airgap seed shape: Ollama-like internal provider, no chat-fallback, OFFLINE=true."""
    llm_settings.offline = True
    project_id, _ = project
    ollama = catalog.provider(
        [project_id], driver="ollama", config={"base_url": "http://fake-llm:9999/fail"}
    )
    catalog.model(project_id, ollama, key="chat-default", model_id="fail-qwen")
    run_reconcile(database_url, llm_settings)

    with pytest.raises(ModelUnavailable):
        _call(database_url, llm_settings, project_id, stream=True)

    assert all(r["model"] == "fail-qwen" for r in fake_requests())
    for model in litellm_models(llm_settings).values():
        assert "fake-llm" in model["litellm_params"].get("api_base", "")


def test_01_4_stream_last_chunk_has_usage(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider)
    run_reconcile(database_url, llm_settings)

    chunks, result = _call(database_url, llm_settings, project_id, stream=True)

    assert chunks[-1].get("usage", {}).get("total_tokens") == 5
    assert result.usage["completion_tokens"] == 2
    assert "".join(result.content) == "hello"


def test_01_9_extra_body_reaches_upstream(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider)
    run_reconcile(database_url, llm_settings)

    _call(database_url, llm_settings, project_id)
    _call(database_url, llm_settings, project_id, stream=True)

    requests = fake_requests()
    assert len(requests) == 2
    assert all(r["reasoning_effort"] == "none" for r in requests)


def test_01_5_add_model_during_stream(database_url, pg, catalog, project, llm_settings):
    project_id, provider = project
    catalog.model(project_id, provider, key="chat-default", model_id="slow-stream")
    run_reconcile(database_url, llm_settings)
    started = threading.Event()
    outcome = {}

    def stream():
        async def go():
            db.configure(database_url, pooled=False)
            try:
                async with db.session_scope() as session:
                    target = await resolve_target(session, project_id, "chat-default")
                async with LiteLLMClient(llm_settings) as client:
                    async with client.chat_stream(target, MESSAGES, user="u", metadata=META) as s:
                        async for _ in s:
                            started.set()
                return s.result
            finally:
                db.reset()

        try:
            outcome["result"] = asyncio.run(go())
        except Exception as exc:  # reported below
            outcome["error"] = exc

    thread = threading.Thread(target=stream)
    thread.start()
    assert started.wait(10)
    catalog.model(project_id, provider, key="memory-extract", model_id="ok-small")
    report = run_reconcile(database_url, llm_settings)
    thread.join(30)

    assert report.created == [f"{project_key(pg, project_id)}.memory-extract"]
    assert "error" not in outcome, outcome.get("error")
    assert len(outcome["result"].content) == 20  # every chunk of the long stream arrived
    assert f"{project_key(pg, project_id)}.memory-extract" in litellm_models(llm_settings)
