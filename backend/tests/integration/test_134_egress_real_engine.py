"""BLOCKERS 134 on the real 08 engine and token store: every message passes egress, twice is the
same text, both profiles (llmaas egress on, airgap egress off)."""

import asyncio
import os
from types import SimpleNamespace

import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.guardrails.masking import detokenize
from ffcore.guardrails.service import resolve_policy
from ffcore.runtime.adapters import EngineGuard
from ffcore.runtime.events import RunEventWriter
from ffcore.runtime.graph import _egress_messages
from tests.integration.runtime_support import definition, seed_run

EMAIL, PHONE = "ali.veli@example.com", "+905321234567"
MESSAGES = [
    {"role": "system", "content": "You help the team."},
    {"role": "user", "content": f"my mail is {EMAIL}"},
    {"role": "assistant", "content": "Noted."},
    {"role": "tool", "tool_call_id": "t1", "content": f"row: name=Ali, phone={PHONE}"},
]


def _run(database_url, run_id, project_id, egress):
    async def go():
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
                ctx = SimpleNamespace(guard=guard, egress_cache={})
                first = await _egress_messages(ctx, MESSAGES)
                again = await _egress_messages(SimpleNamespace(guard=guard, egress_cache={}), first)
                text = "\n".join(m["content"] for m in first)
                back, unresolved = await detokenize(text, store=guard._tokens, scope=str(run_id))
                await session.commit()
                return first, again, back, unresolved
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


def test_134_llmaas_every_message_tokenized_and_idempotent(database_url, pg, make_project):
    project_id = make_project()
    run_id = seed_run(pg, project_id, definition())
    first, again, back, unresolved = _run(database_url, run_id, project_id, True)
    sent = "\n".join(m["content"] for m in first)
    assert EMAIL not in sent and PHONE not in sent
    assert again == first  # egress twice: same text, placeholders not matched again
    assert EMAIL in back and PHONE in back and not unresolved  # detokenize restores them


def test_134_airgap_has_no_egress_stage(database_url, pg, make_project):
    project_id = make_project()
    run_id = seed_run(pg, project_id, definition())
    first, _, _, _ = _run(database_url, run_id, project_id, False)
    assert first == MESSAGES
