"""Package 02 against the real Langfuse 3.120.0 stack (web + worker), LiteLLM and fake-llm.

Needs `docker compose --profile test up -d --wait` (full stack: Langfuse init keys from .env.test).
"""

import asyncio
import base64
import logging
import os
import time
import uuid

import httpx2
import pytest
from pydantic import SecretStr

from ffcore.core import db, tracing
from ffcore.core.prompts import PromptStore, seed_prompts
from ffcore.services.litellm_client import LiteLLMClient, resolve_target
from tests.integration.litellm_support import project_key, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")
LANGFUSE = "http://langfuse-web:3000"
MESSAGES = [{"role": "user", "content": "hi"}]
COST = 3.9e-05  # fake-llm usage 3 + 2 tokens at 3 and 15 USD per 1M


def _keys():
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY"), os.environ.get("LANGFUSE_SECRET_KEY")
    if not pk or not sk:
        pytest.fail("LANGFUSE_PUBLIC_KEY/SECRET_KEY not set; run in the tools container")
    return pk, sk


def _auth():
    pk, sk = _keys()
    return {"Authorization": "Basic " + base64.b64encode(f"{pk}:{sk}".encode()).decode()}


@pytest.fixture
def lf_settings(llm_settings):
    pk, sk = _keys()
    llm_settings.langfuse_host = LANGFUSE
    llm_settings.langfuse_public_key = SecretStr(pk)
    llm_settings.langfuse_secret_key = SecretStr(sk)
    yield llm_settings
    tracing.shutdown_tracing()


def _priced_model(catalog):
    project_id = catalog.project()
    catalog.model(
        project_id,
        catalog.provider([project_id]),
        pricing='{"input_per_1m": 3, "output_per_1m": 15}',
    )
    return project_id


def _traced_calls(database_url, settings, project_id, run_id):
    async def go():
        db.configure(database_url, pooled=False)
        try:
            async with db.session_scope() as session:
                target = await resolve_target(session, project_id, "chat-default")
        finally:
            db.reset()
        with tracing.run_attributes(run_id, "u-02", str(project_id), ["test-02"]):
            with tracing.span("ffcore-test-run"):
                trace_id = tracing.get_client().get_current_trace_id()
                span_id = tracing.get_client().get_current_observation_id()
                meta = tracing.trace_context(run_id=run_id, user_id="u-02", tags=["test-02"])
                async with LiteLLMClient(settings) as client:
                    await client.chat(target, MESSAGES, user="u-02", metadata=meta)
                    async with client.chat_stream(
                        target, MESSAGES, user="u-02", metadata=meta
                    ) as s:
                        async for _ in s:
                            pass
        return trace_id, span_id

    return asyncio.run(go())


def test_02_1_litellm_call_traced_with_cost(database_url, pg, catalog, lf_settings):
    """Kabul 1 and 2: within 30 s, tokens and cost = models.pricing, nested under our span."""
    project_id = _priced_model(catalog)
    run_reconcile(database_url, lf_settings)
    tracing.init_tracing(lf_settings)
    run_id = f"run-{uuid.uuid4().hex[:8]}"

    trace_id, span_id = _traced_calls(database_url, lf_settings, project_id, run_id)
    tracing.shutdown_tracing()  # flush our span
    started = time.monotonic()

    trace, generations = None, []
    while time.monotonic() - started < 30:
        response = httpx2.get(f"{LANGFUSE}/api/public/traces/{trace_id}", headers=_auth())
        if response.status_code == 200:
            trace = response.json()
            generations = [o for o in trace["observations"] if o["type"] == "GENERATION"]
            if len(generations) == 2 and all(o.get("calculatedTotalCost") for o in generations):
                break
        time.sleep(1)
    elapsed = time.monotonic() - started
    print(f"langfuse visible after {elapsed:.1f} s")

    assert trace is not None and len(generations) == 2, f"not complete after {elapsed:.0f} s"
    assert trace["sessionId"] == run_id and trace["userId"] == "u-02"
    assert "test-02" in trace["tags"]
    for generation in generations:
        assert generation["parentObservationId"] == span_id
        assert (
            generation["usageDetails"]["input"] == 3 and generation["usageDetails"]["output"] == 2
        )
        assert generation["calculatedTotalCost"] == pytest.approx(COST)
    name = f"{project_key(pg, project_id)}.chat-default"
    assert {g["model"] for g in generations} == {"ok-model"}, name


def test_02_3_langfuse_unreachable_backend_serves(database_url, pg, catalog, lf_settings, caplog):
    """Kabul 3: traces cannot be delivered; the model call still answers, the loss is logged."""
    project_id = _priced_model(catalog)
    run_reconcile(database_url, lf_settings)
    lf_settings.langfuse_host = "http://langfuse-down:3000"
    lf_settings.allowed_internal_hosts = ["litellm", "fake-llm", "langfuse-down"]
    tracing.init_tracing(lf_settings)

    started = time.monotonic()
    with caplog.at_level(logging.ERROR, logger="ffcore"):
        trace_id, _ = _traced_calls(database_url, lf_settings, project_id, "run-down")
        tracing.shutdown_tracing()
    elapsed = time.monotonic() - started
    print(f"calls + shutdown with langfuse down: {elapsed:.1f} s")

    # Bounded: the calls never wait on Langfuse, shutdown waits at most SHUTDOWN_TIMEOUT_S.
    assert elapsed < tracing.SHUTDOWN_TIMEOUT_S + 15
    assert trace_id
    assert "trace_delivery_failed" in caplog.text


def test_02_4_init_keys_authenticate():
    response = httpx2.get(f"{LANGFUSE}/api/public/projects", headers=_auth())
    assert response.status_code == 200
    assert [p["id"] for p in response.json()["data"]] == ["ffcore"]
    wrong = {"Authorization": "Basic " + base64.b64encode(b"pk-lf-x:sk-lf-y").decode()}
    assert httpx2.get(f"{LANGFUSE}/api/public/projects", headers=wrong).status_code == 401


def test_02_6_seed_and_fetch(lf_settings, tmp_path):
    name = f"test-02-{uuid.uuid4().hex[:8]}"
    (tmp_path / f"{name}.md").write_text("Hello {{who}}", encoding="utf-8")
    (tmp_path / "README.md").write_text("not a prompt", encoding="utf-8")
    client = tracing.init_tracing(lf_settings)

    first = seed_prompts(client, tmp_path)
    second = seed_prompts(client, tmp_path)

    assert first.created == [name] and second.existing == [name] and not second.created
    assert PromptStore(client).get(name).compile(who="FFCore") == "Hello FFCore"
