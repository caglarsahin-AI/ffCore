"""Reviewer probe for 08-tam-1a r3 (370912d): MAJOR-r2-2/3 end to end through the worker's own
`adapters.context_factory` (real `_history`, EngineGuard, LiteLLMModel), LiteLLM and the fake
provider; the provider's request log (`/_requests`) is the evidence. Mounted into the tools
container as backend/tests/integration/test_zz_review_08t1a_r3.py for the run, removed after.

Only the project's PII threshold is set by wrapping `resolve_policy` (min_confidence 0.8); the
rest is the worker's path. History of run A (seeded): a phone placeholder in a sentence without a
context word, the same placeholder on a URL line, and a placeholder A never issued (<<PII_7>>).
B's question carries a typed <<PII_9>>. Expected: the provider sees no raw phone; B's phone
placeholder is numbered above 9; <<PII_7>>/<<PII_9>> resolve to nothing in B; A's mapping TTL is
not renewed by reading the history; no stored view of B holds the phone.
"""

import asyncio
import json
import os
import uuid

import pytest
import redis.asyncio as aioredis

from ffcore.guardrails.masking import RedisTokenStore
from ffcore.runtime import adapters
from ffcore.runtime.contracts import JobClass
from ffcore.runtime.events import mark_listening
from ffcore.runtime.runner import Attempt, execute
from ffcore.runtime.scheduler import BackgroundWindow, LlmSlots, SlotSettings
from tests.integration.litellm_support import *  # noqa: F403 - fixtures
from tests.integration.litellm_support import fake_requests, run_reconcile
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runtime_support import definition, seed_run
from tests.integration.test_08t_m2_history import _conversation, _message

PHONE = "0532 123 45 67"
ANSWER_A = (
    "Kendisine <<PII_1>> üzerinden ulaşabilirsiniz.\n"
    "Kayıt: https://crm.example/ara?tel=<<PII_1>>\n"
    "Diğer kayıt <<PII_7>> idi."
)
QUESTION_B = "Onu ve <<PII_9>> kaydını nasıl ararım?"
ALWAYS = BackgroundWindow.parse("", weekends_all_day=False, zone="UTC")

pytestmark = pytest.mark.usefixtures("clean_litellm")


def test_zz_r3_min_confidence_history_e2e(
    database_url, catalog, llm_settings, harness, pg, monkeypatch, make_user
):
    project_id = catalog.project()
    provider = catalog.provider([project_id])
    catalog.model(project_id, provider, key="chat-default", model_id="ok-primary")
    run_reconcile(database_url, llm_settings)
    harness.db.configure(database_url, pooled=False)  # run_reconcile resets the global db
    doc = definition(knowledge=[])
    run_a = seed_run(pg, project_id, doc, status="completed")
    run_b = seed_run(pg, project_id, doc, question=QUESTION_B)
    user_id, _ = make_user(memberships={project_id: ("user", "edit")})
    pg.execute("UPDATE runs SET user_id = %s WHERE id IN (%s, %s)", (user_id, run_a, run_b))
    conversation_id = _conversation(pg, project_id, run_a, run_b)
    _message(pg, conversation_id, run_a, "user", "Telefonu ne?", 0)
    _message(pg, conversation_id, run_a, "assistant", ANSWER_A, 1)
    _message(pg, conversation_id, run_b, "user", QUESTION_B, 2)

    real = adapters.resolve_policy

    async def strict(session, pid, key):
        policy = await real(session, pid, key)
        pii = {k: v.model_copy(update={"min_confidence": 0.8}) for k, v in policy.pii_policies.items()}
        return type(policy)(key=policy.key, spec=policy.spec, pii_policies=pii, builtin=policy.builtin)

    monkeypatch.setattr(adapters, "resolve_policy", strict)
    before = len(fake_requests())

    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 60)
            await store.token_for(str(run_a), "TR_PHONE:" + PHONE, PHONE)
            await client.expire("ffcore:pii:" + str(run_a), 50)
            await mark_listening(client, run_b, 600)
            slots = LlmSlots(client, SlotSettings(slots=1), ALWAYS, prefix=f"r3:{uuid.uuid4().hex}")
            # Langfuse prompts are outside this probe: a fixed platform rules text.
            rules = type("P", (), {"compile": lambda self, **kw: "RULES"})()
            prompts = type("S", (), {"get": lambda self, name, label=None: rules})()
            factory = adapters.context_factory(
                llm_settings, client, slots, prompts, job_class=JobClass.interactive
            )
            async def traced(**kw):
                try:
                    return await factory(**kw)
                except Exception:
                    import traceback

                    traceback.print_exc()
                    raise

            attempt = Attempt(harness.settings, client, harness.db.session_scope, traced)
            status = await execute(attempt, str(run_b), None)
            ttl_a = await client.ttl("ffcore:pii:" + str(run_a))
            b = {t: await store.lookup(str(run_b), t) for t in ("<<PII_7>>", "<<PII_9>>", "<<PII_10>>")}
            return status, ttl_a, b
        finally:
            await client.aclose()

    status, ttl_a, b = asyncio.run(go())
    sent = json.dumps(fake_requests()[before:], ensure_ascii=False)
    print("PROBE status", status, "requests", len(fake_requests()) - before)
    print("PROBE provider saw raw phone:", PHONE in sent)
    print("PROBE provider history lines:", [
        line for line in sent.split("\\n") if "ulaşabilirsiniz" in line or "crm.example" in line or "PII_7" in line
    ])
    print("PROBE B lookups", b)
    print("PROBE A mapping ttl after B (was 50):", ttl_a)
    stored = {
        "messages": ("SELECT content FROM messages WHERE conversation_id = %s", conversation_id),
        "run_events": ("SELECT payload::text FROM run_events WHERE run_id = %s", run_b),
        "guardrail_events": ("SELECT row_to_json(g)::text FROM guardrail_events g WHERE run_id = %s", run_b),
        "runs.output": ("SELECT coalesce(output::text,'') FROM runs WHERE id = %s", run_b),
        "checkpoint_blobs": ("SELECT encode(blob, 'escape') FROM checkpoints.checkpoint_blobs WHERE thread_id = %s", str(run_b)),
        "checkpoint_writes": ("SELECT encode(blob, 'escape') FROM checkpoints.checkpoint_writes WHERE thread_id = %s", str(run_b)),
    }
    for name, (sql, key) in stored.items():
        rows = [r[0] or "" for r in pg.execute(sql, (key,)).fetchall()]
        print(f"PROBE stored {name}: rows {len(rows)}, raw phone {any(PHONE in r for r in rows)}")
        assert not any(PHONE in r for r in rows), name
    assert status == "completed"
    assert PHONE not in sent
    assert b["<<PII_7>>"] is None and b["<<PII_9>>"] is None and b["<<PII_10>>"] == PHONE
    assert ttl_a <= 50
