"""08-tam-1a r2 MAJOR-r2-3 end to end (KARARLAR "Konuşma geçmişinde yer tutucu eşlemesi doğrudan ve
hamsız"): the reviewer's case. A project's PII policy asks `min_confidence` 0.8; run A found a
phone number where a context word raised its score and tokenized it; A's answer carries it in a
sentence without that word (0.75, below the threshold). Run B in the same conversation: the real
graph, runner, EngineGuard (llmaas egress), token store and `_history`; a scripted model records
what it was sent. The model gets B's placeholder, never the number, and no stored view of B
(`messages`, `run_events`, `guardrail_events`, the checkpoint) holds it. Before r2 the history was
turned back into the number and egress, not finding it again, sent it on raw."""

import asyncio
import json
import os
import uuid

import redis.asyncio as aioredis

from ffcore.guardrails import engine
from ffcore.guardrails.masking import RedisTokenStore
from ffcore.guardrails.service import resolve_policy
from ffcore.runtime.adapters import EngineGuard, _history
from ffcore.runtime.events import mark_listening
from ffcore.runtime.runner import Attempt, execute
from ffcore.runtime.state import RunContext
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runtime_support import (
    PROMPT,
    ScriptedModel,
    ScriptedRetriever,
    ScriptedTools,
    definition,
    seed_run,
    turn,
)
from tests.integration.test_08t_m2_history import _conversation, _message

PHONE = "0532 123 45 67"
ANSWER_A = "Kendisine <<PII_1>> üzerinden ulaşabilirsiniz."


async def _strict_policy(session, project_id):
    policy = await resolve_policy(session, project_id, "default")
    strict = {
        k: v.model_copy(update={"min_confidence": 0.8}) for k, v in policy.pii_policies.items()
    }
    return type(policy)(
        key=policy.key, spec=policy.spec, pii_policies=strict, builtin=policy.builtin
    )


def _egress_on():
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


def test_08t_r2_history_reaches_the_provider_as_a_placeholder(harness, pg, make_project):
    project_id = make_project()
    doc = definition(knowledge=[])
    run_a = seed_run(pg, project_id, doc, status="completed")
    run_b = seed_run(pg, project_id, doc, question="Onu nasıl ararım?")
    conversation_id = _conversation(pg, project_id, run_a, run_b)
    _message(pg, conversation_id, run_a, "user", "Telefonu ne?", 0)
    _message(pg, conversation_id, run_a, "assistant", ANSWER_A, 1)
    _message(pg, conversation_id, run_b, "user", "Onu nasıl ararım?", 2)
    model = ScriptedModel(turn("Numarayı arayabilirsiniz."))
    egress = _egress_on()

    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 60)
            await store.token_for(str(run_a), "TR_PHONE:" + PHONE, PHONE)
            await mark_listening(client, run_b, 600)
            control = None

            async def context_factory(*, session, run, definition, events, boundary):
                nonlocal control
                policy = await _strict_policy(session, run.project_id)
                ctx = engine.EvalContext(
                    run_id=str(uuid.uuid4()),
                    project_id=str(run.project_id),
                    source="chat",
                    token_store=store,
                    egress_enabled=True,
                )
                # control: egress alone does not find the number in A's sentence
                raw = ANSWER_A.replace("<<PII_1>>", PHONE)
                control = (await engine.evaluate(raw, "egress", policy, ctx=ctx)).text_out
                guard = EngineGuard(
                    session,
                    client,
                    events,
                    policy,
                    run_id=run.id,
                    project_id=run.project_id,
                    egress_enabled=egress,
                    token_ttl_s=60,
                    channel=run.channel,
                )
                return RunContext(
                    run_id=str(run.id),
                    project_id=str(run.project_id),
                    user_id=None,
                    definition=definition,
                    events=events,
                    model=model,
                    retriever=ScriptedRetriever(),
                    tools=ScriptedTools(),
                    guard=guard,
                    boundary=boundary,
                    system={
                        "platform_rules": "RULES",
                        "runtime_profile": "",
                        "user_instructions": PROMPT,
                    },
                    history=await _history(session, run.conversation_id, run.id, store, run.input),
                    stream_live=guard.streams_live,
                    approvals=None,
                )

            attempt = Attempt(harness.settings, client, harness.db.session_scope, context_factory)
            status = await execute(attempt, str(run_b), None)
            sent = json.dumps(model.calls, ensure_ascii=False)
            token = next(t for t in json.loads(sent)[0] if "ulaşabilirsiniz" in t["content"])
            placeholder = token["content"].split(" ")[1]
            return status, control, sent, await store.lookup(str(run_b), placeholder)
        finally:
            await client.aclose()

    status, control, sent, value = asyncio.run(go())
    assert PHONE in control  # the threshold case: re-detection would have sent it raw
    assert PHONE not in sent and value == PHONE
    stored = [
        ("messages", "SELECT content FROM messages WHERE conversation_id = %s", conversation_id),
        ("run_events", "SELECT payload::text FROM run_events WHERE run_id = %s", run_b),
        (
            "guardrail_events",
            "SELECT row_to_json(g)::text FROM guardrail_events g WHERE run_id = %s",
            run_b,
        ),
        (
            "checkpoint_blobs",
            "SELECT encode(blob, 'escape') FROM checkpoints.checkpoint_blobs WHERE thread_id = %s",
            str(run_b),
        ),
        (
            "checkpoint_writes",
            "SELECT encode(blob, 'escape') FROM checkpoints.checkpoint_writes WHERE thread_id = %s",
            str(run_b),
        ),
        (
            "checkpoints",
            "SELECT checkpoint::text FROM checkpoints.checkpoints WHERE thread_id = %s",
            str(run_b),
        ),
    ]
    for name, sql, key in stored:
        rows = [r[0] or "" for r in pg.execute(sql, (key,)).fetchall()]
        assert not any(PHONE in r for r in rows), name
    assert status == "completed"
