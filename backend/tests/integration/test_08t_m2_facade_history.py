"""08-tam-1a r1 MAJOR-2 and r2 MAJOR-r2-2/r2-3 on the facade agent path: the client's earlier turns
are stored as egress left them, in the run's scope, never raw (llmaas; airgap has no egress). A
stale placeholder the client sends back (an earlier answer's, kept on a URL line) never becomes
one of the run's values: the scope's counter passes it before the first check (the reviewer's
probe, state/reviews/08-tam-1a-r2-int-probe.py)."""

import asyncio
import os

import redis.asyncio as aioredis

from ffcore.guardrails.masking import RedisTokenStore
from tests.integration import test_06b_agent as base
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue

agent = base.agent
EMAIL = "ayse.yilmaz@example.test"


def _egress_on():
    from ffcore.guardrails.settings import get_guardrail_settings

    return get_guardrail_settings().guardrail_egress_enabled


def _lookup(scope, token):
    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            return await RedisTokenStore(client, 60).lookup(scope, token)
        finally:
            await client.aclose()

    return asyncio.run(go())


def _send(agent, harness, use_queue, history):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, base._answer_ports()))
    response = client.chat(model, messages=history)
    assert response.status_code == 200, response.text
    return response.headers["X-Conversation-Id"]


def test_08t_r2_client_history_stored_in_the_runs_scope(agent, harness, use_queue, pg):
    history = [
        {"role": "user", "content": f"Benim adresim {EMAIL}"},
        {"role": "assistant", "content": "Not aldım."},
        {"role": "user", "content": "Fesih süresi nedir?"},
    ]
    conversation = _send(agent, harness, use_queue, history)
    rows = pg.execute(
        "SELECT role, content FROM messages WHERE conversation_id = %s AND run_id IS NULL"
        " ORDER BY created_at",
        (conversation,),
    ).fetchall()
    run_id = pg.execute(
        "SELECT id FROM runs WHERE conversation_id = %s", (conversation,)
    ).fetchone()[0]
    assert [r[0] for r in rows] == ["user", "assistant"]
    if _egress_on():
        assert EMAIL not in rows[0][1]
        token = rows[0][1].removeprefix("Benim adresim ")
        assert _lookup(str(run_id), token) == EMAIL
    else:  # airgap: no egress stage, the text is stored as checked
        assert rows[0][1] == f"Benim adresim {EMAIL}"


def test_08t_r2_stale_client_placeholder_never_becomes_a_new_value(agent, harness, use_queue, pg):
    history = [
        {"role": "user", "content": f"Benim adresim {EMAIL}"},
        {
            "role": "assistant",
            "content": "Kayıt sahibi <<PII_1>>, bağlantı https://crm.example/u?m=<<PII_1>>",
        },
        {"role": "user", "content": "Kayıt sahibi kimdi?"},
    ]
    conversation = _send(agent, harness, use_queue, history)
    run_id = pg.execute(
        "SELECT id FROM runs WHERE conversation_id = %s", (conversation,)
    ).fetchone()[0]
    assert _lookup(str(run_id), "<<PII_1>>") is None
    if _egress_on():
        assert _lookup(str(run_id), "<<PII_2>>") == EMAIL
