"""BLOCKERS 134 (e)/(f): what the provider receives. The real graph model node, EngineGuard, token
store and LiteLLM adapter; the fake provider's request log is the evidence (F4 pattern)."""

import asyncio
import json
import os
import uuid
from types import SimpleNamespace

import pytest
import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.guardrails.masking import detokenize
from ffcore.guardrails.service import resolve_policy
from ffcore.runtime.adapters import EngineGuard, LiteLLMModel
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.definition import parse_definition
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.graph import model as model_node
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings
from tests.integration.litellm_support import fake_requests, run_reconcile
from tests.integration.runtime_support import definition, seed_run

ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")
EMAIL, PHONE, SYSTEM_MAIL = "ali.veli@example.com", "+905321234567", "ops.team@example.com"
CALL = {
    "id": "c1",
    "type": "function",
    "function": {"name": "run_sql", "arguments": json.dumps({"sql": f"-- {EMAIL}"})},
}
HISTORY = [
    {"role": "system", "content": f"You are the helpdesk agent. Escalate to {SYSTEM_MAIL}."},
    {"role": "user", "content": f"Turn 1: my e-mail is {EMAIL}"},  # a persistent conversation
    {"role": "assistant", "content": "", "tool_calls": [CALL]},
    {"role": "tool", "tool_call_id": "c1", "content": f"<tool_result>phone={PHONE}</tool_result>"},
    {"role": "user", "content": "Turn 2: what did I tell you?"},
]


def _send(database_url, catalog, llm_settings, pg, egress):
    project_id = catalog.project()
    provider = catalog.provider([project_id])
    catalog.model(project_id, provider, key="chat-default", model_id="ok-primary")
    run_reconcile(database_url, llm_settings)
    run_id = seed_run(pg, project_id, definition(knowledge=[]))

    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        slots = LlmSlots(client, SlotSettings(slots=1), ALWAYS, prefix=f"t134:{uuid.uuid4().hex}")
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
                llm = LiteLLMModel(
                    llm_settings,
                    session,
                    slots,
                    run_id=run_id,
                    project_id=project_id,
                    user_id=uuid.uuid4(),
                    model_key="chat-default",
                    job_class=JobClass.interactive,
                )

                async def boundary(_):
                    return None

                ctx = SimpleNamespace(
                    definition=parse_definition(definition(knowledge=[])),
                    model=llm,
                    events=writer,
                    guard=guard,
                    egress_cache={},
                    boundary=boundary,
                    stream_live=False,
                    tools=SimpleNamespace(schemas=lambda: []),
                )
                state = {"messages": HISTORY, "iteration": 0, "usage": {}, "timing": {}}
                await model_node(state, SimpleNamespace(context=ctx))
                sent = json.dumps(fake_requests()[-1]["messages"])
                back, unresolved = await detokenize(sent, store=guard._tokens, scope=str(run_id))
                await session.commit()
                return sent, back, unresolved
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


@pytest.mark.usefixtures("clean_litellm")
def test_134_llmaas_provider_sees_no_raw_identifier(database_url, pg, catalog, llm_settings):
    sent, back, unresolved = _send(database_url, catalog, llm_settings, pg, True)
    for raw in (EMAIL, PHONE, SYSTEM_MAIL):
        assert raw not in sent  # history, tool result, tool call arguments, system prompt
    assert "<<PII_" in sent
    assert EMAIL in back and PHONE in back and not unresolved  # detokenize brings them back


@pytest.mark.usefixtures("clean_litellm")
def test_134_airgap_has_no_egress_stage_so_provider_gets_text_as_is(
    database_url, pg, catalog, llm_settings
):
    sent, _, _ = _send(database_url, catalog, llm_settings, pg, False)
    assert EMAIL in sent and PHONE in sent  # GUARDRAIL_EGRESS_ENABLED=false: the model is local
