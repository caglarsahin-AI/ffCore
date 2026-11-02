"""Reviewer probes for 06a-egress r2 (integration; real Postgres/Redis/LiteLLM/fake-llm).
Copied into backend/tests/integration/ of the review worktree, removed afterwards."""
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
from ffcore.runtime.graph import guard_in, model as model_node
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings
from ffcore.runtime.state import StopRun
from tests.integration.litellm_support import fake_requests, run_reconcile
from tests.integration.runtime_support import definition, seed_run

ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")
EMAIL, PHONE, SYS = "ali.veli@example.com", "+905321234567", "ops.team@example.com"
EMAIL2, TCKN = "zeynep.k@example.org", "10000000146"
ARGS = {"sql": f"-- {EMAIL}", "nested": {"to": [EMAIL2, {"phone": PHONE}], "n": 3, "flag": True}, "id": int(TCKN)}
CALL = {"id": "c1", "type": "function", "function": {"name": "run_sql", "arguments": json.dumps(ARGS)}}
BAD = {"id": "c2", "type": "function", "function": {"name": "run_sql", "arguments": "{not json"}}
HISTORY = [
    {"role": "system", "content": f"Helpdesk. Escalate to {SYS}."},
    {"role": "user", "content": f"Turn 1: my e-mail is {EMAIL}"},
    {"role": "assistant", "content": f"I will look up {PHONE}", "tool_calls": [CALL]},
    {"role": "tool", "tool_call_id": "c1", "content": f"<tool_result>phone={PHONE} mail={EMAIL}</tool_result>"},
    {"role": "user", "content": "Turn 2: what did I tell you?"},
]


def drive(database_url, catalog, llm_settings, pg, messages, *, twice=False, via_guard_in=False):
    project_id = catalog.project()
    provider = catalog.provider([project_id])
    catalog.model(project_id, provider, key="chat-default", model_id="ok-primary")
    run_reconcile(database_url, llm_settings)
    run_id = seed_run(pg, project_id, definition(knowledge=[]))

    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        slots = LlmSlots(client, SlotSettings(slots=1), ALWAYS, prefix=f"p134:{uuid.uuid4().hex}")
        try:
            async with db.session_scope() as session:
                policy = await resolve_policy(session, project_id, "default")
                writer = RunEventWriter(session, client, run_id, ttl_s=60)
                await writer.start()
                guard = EngineGuard(session, client, writer, policy, run_id=run_id, project_id=project_id,
                                    egress_enabled=True, token_ttl_s=60)
                llm = LiteLLMModel(llm_settings, session, slots, run_id=run_id, project_id=project_id,
                                   user_id=uuid.uuid4(), model_key="chat-default", job_class=JobClass.interactive)

                async def boundary(_):
                    return None

                ctx = SimpleNamespace(definition=parse_definition(definition(knowledge=[])), model=llm, events=writer,
                                      guard=guard, egress_cache={}, boundary=boundary, stream_live=False,
                                      tools=SimpleNamespace(schemas=lambda: []))
                state = {"messages": messages, "iteration": 0, "usage": {}, "timing": {}, "sources": [],
                         "question": f"question with {EMAIL}"}
                if via_guard_in:
                    upd = await guard_in(state, SimpleNamespace(context=ctx))
                    state = {**state, **upd}
                await model_node(state, SimpleNamespace(context=ctx))
                if twice:
                    await model_node(state, SimpleNamespace(context=ctx))
                sent = json.dumps(fake_requests()[-1]["messages"])
                back, unresolved = await detokenize(sent, store=guard._tokens, scope=str(run_id))
                await session.commit()
                return sent, back, unresolved
        finally:
            await client.aclose()
            db.reset()

    sent, back, unresolved = asyncio.run(go())
    return run_id, sent, back, unresolved


@pytest.mark.usefixtures("clean_litellm")
def test_r2_1_nested_arguments_tokenized_and_detokenize_round_trips(database_url, pg, catalog, llm_settings):
    _, sent, back, unresolved = drive(database_url, catalog, llm_settings, pg, HISTORY)
    for raw in (EMAIL, EMAIL2, PHONE, SYS):
        assert raw not in sent, raw
    args = [m for m in json.loads(sent) if m.get("tool_calls")][0]["tool_calls"][0]["function"]["arguments"]
    parsed = json.loads(args)
    print("R2 args sent:", parsed)
    assert parsed["nested"]["n"] == 3 and parsed["nested"]["flag"] is True  # structure kept
    assert EMAIL in back and EMAIL2 in back and PHONE in back and not unresolved
    # integer PII value in arguments (national id as a number)
    print("R2 integer id in args after egress:", parsed["id"], "(raw)" if parsed["id"] == int(TCKN) else "(changed)")


@pytest.mark.usefixtures("clean_litellm")
def test_r2_2_no_duplicate_egress_events_with_guard_in(database_url, pg, catalog, llm_settings):
    run_id, sent, _, _ = drive(database_url, catalog, llm_settings, pg, HISTORY[:1], via_guard_in=True, twice=True)
    hooks = pg.execute(
        "SELECT payload->>'stage', payload->>'events' FROM run_events WHERE run_id=%s AND type='guardrail_hook'", (run_id,)
    ).fetchall()
    print("R2 guardrail_hook rows:", hooks)
    egress = [h for h in hooks if h[0] == "egress"]
    rows = pg.execute("SELECT count(*) FROM guardrail_events WHERE run_id=%s AND stage='egress'", (run_id,)).fetchone()[0]
    print("R2 guardrail_events egress rows:", rows)
    # user message (from guard_in) + system message = 2 distinct texts; a second model call adds none
    assert len(egress) <= 2, egress
    assert EMAIL not in sent


@pytest.mark.usefixtures("clean_litellm")
def test_r2_3_bad_arguments_and_nontext_content_fail_loud(database_url, pg, catalog, llm_settings):
    bad = [*HISTORY[:2], {"role": "assistant", "content": "", "tool_calls": [BAD]}, HISTORY[4]]
    with pytest.raises(StopRun) as e:
        drive(database_url, catalog, llm_settings, pg, bad)
    assert e.value.code == "unsupported_message_content"
    listy = [HISTORY[0], {"role": "user", "content": [{"type": "text", "text": EMAIL}]}]
    with pytest.raises(StopRun) as e2:
        drive(database_url, catalog, llm_settings, pg, listy)
    assert e2.value.code == "unsupported_message_content"
    big = [HISTORY[0], {"role": "tool", "tool_call_id": "c", "content": "a" * 200_001}]
    with pytest.raises(StopRun) as e3:
        drive(database_url, catalog, llm_settings, pg, big)
    assert e3.value.code == "guardrail_text_too_long"
    # nothing reached the provider on any of the failures
    assert all(EMAIL not in json.dumps(r.get("messages")) for r in fake_requests())


@pytest.mark.usefixtures("clean_litellm")
def test_r2_4_second_run_does_not_see_first_runs_tokens(database_url, pg, catalog, llm_settings):
    r1, sent1, _, _ = drive(database_url, catalog, llm_settings, pg, HISTORY)
    r2, sent2, back2, unresolved2 = drive(database_url, catalog, llm_settings, pg, [HISTORY[0], {"role": "user", "content": f"<<PII_1>> and {EMAIL2}"}])
    assert "ali.veli" not in back2  # run 2 cannot resolve run 1's <<PII_1>> to Ali's e-mail
    print("R2 run2 sent:", sent2[:200], "unresolved:", unresolved2)
