"""06a adapters against the real neighbours: LiteLLM + fake provider (01), the 08 engine."""

import asyncio
import os
import uuid

import pytest
import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.guardrails.service import resolve_policy
from ffcore.runtime.adapters import EngineGuard, LiteLLMModel
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings
from tests.integration.litellm_support import project_key, run_reconcile
from tests.integration.runtime_support import definition, events, seed_run

ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")


def _slots(client):
    return LlmSlots(client, SlotSettings(slots=1), ALWAYS, prefix=f"t06a:{uuid.uuid4().hex}")


@pytest.mark.usefixtures("clean_litellm")
def test_06a_model_adapter_streams_through_litellm_with_a_slot(
    database_url, pg, catalog, llm_settings
):
    project_id = catalog.project()
    provider = catalog.provider([project_id])
    catalog.model(project_id, provider, key="chat-default", model_id="fail-primary")
    catalog.model(project_id, provider, key="chat-fallback", model_id="ok-backup")
    run_reconcile(database_url, llm_settings)
    tokens: list[str] = []

    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        slots = _slots(client)
        try:
            async with db.session_scope() as session:
                model = LiteLLMModel(
                    llm_settings,
                    session,
                    slots,
                    run_id=uuid.uuid4(),
                    project_id=project_id,
                    user_id=uuid.uuid4(),
                    model_key="chat-default",
                    job_class=JobClass.interactive,
                )

                async def on_token(text):
                    tokens.append(text)

                turn = await model.call(
                    [{"role": "user", "content": "hi"}], tools=[], max_tokens=50, on_token=on_token
                )
            status = await slots.status()
        finally:
            await client.aclose()
            db.reset()
        return turn, status

    turn, status = asyncio.run(go())
    key = project_key(pg, project_id)
    assert turn.content == "hello" and "".join(tokens) == "hello"
    assert turn.fallback == {
        "source_model": f"{key}.chat-default",
        "target_model": f"{key}.chat-fallback",
        "reason": "primary_failed",
    }
    assert turn.finish_reason == "stop" and turn.usage
    assert uuid.UUID(turn.call_id)  # x-litellm-call-id from the real proxy (K-06a-0007)
    assert status["in_use"] == 0  # the slot is given back


def test_06a_guard_adapter_runs_the_08_engine_and_records(database_url, pg, make_project):
    project_id = make_project()
    run_id = seed_run(pg, project_id, definition())

    async def go(egress):
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            async with db.session_scope() as session:
                policy = await resolve_policy(session, project_id, "default")
                writer = RunEventWriter(session, client, run_id, ttl_s=60)
                await writer.start()
                guard = EngineGuard(
                    session,
                    client,
                    writer,
                    policy,
                    run_id=run_id,
                    project_id=project_id,
                    egress_enabled=egress,
                    token_ttl_s=60,
                )
                checked = await guard.check("input.pre", "TC kimlik no 10000000146 olan kişi")
                skipped = await guard.check("egress", "anything")
                await session.commit()
                return guard.streams_live, checked, skipped
        finally:
            await client.aclose()
            db.reset()

    live, checked, skipped = asyncio.run(go(False))
    assert live is True  # the built-in policy is monitor: answers stream
    assert checked.events >= 1
    stored = pg.execute(
        "SELECT stage, run_id FROM guardrail_events WHERE run_id = %s", (run_id,)
    ).fetchall()
    assert ("input.pre", run_id) in [(s, r) for s, r in stored]
    hooks = [p for _, t, p in events(pg, run_id) if t == "guardrail_hook"]
    assert hooks and hooks[0]["stage"] == "input.pre" and hooks[0]["policy_key"] == "default"
    assert (skipped.action, skipped.events) == ("allow", 0)  # egress off on airgap: no stage
