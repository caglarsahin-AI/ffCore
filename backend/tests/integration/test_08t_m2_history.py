"""08-tam-1a r1 MAJOR-2 on Postgres and Redis (KARARLAR "Yer tutucu sayacı ve konuşma geçmişi"):
an earlier run's answer in the conversation carries that run's placeholders. When the history
goes into a new run they are reversed in the earlier run's scope (egress tokenizes them again in
the new scope before the model sees them); a placeholder whose mapping is gone stays, and the
new scope's counter starts after it, so it never becomes another value of the new run. The
reviewer's probe: A has ayse = <<PII_1>>, B has fatma = <<PII_1>>; A's answer must not read
"fatma" in B."""

import asyncio
import os
import uuid

import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.guardrails.masking import RedisTokenStore, detokenize
from ffcore.runtime.adapters import _history
from tests.integration.runtime_support import definition, seed_run

AYSE, FATMA = "ayse@example.test", "fatma@example.test"


def _conversation(pg, project_id, *runs):
    agent_id = pg.execute("SELECT agent_id FROM runs WHERE id = %s", (runs[0],)).fetchone()[0]
    conversation_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO conversations (id, project_id, agent_id, created_by) VALUES (%s, %s, %s, 't')",
        (conversation_id, project_id, agent_id),
    )
    for run_id in runs:
        pg.execute("UPDATE runs SET conversation_id = %s WHERE id = %s", (conversation_id, run_id))
    return conversation_id


def _message(pg, conversation_id, run_id, role, content, n):
    pg.execute(
        "INSERT INTO messages (id, conversation_id, run_id, role, content, created_at)"
        " VALUES (%s, %s, %s, %s, %s, now() + make_interval(secs => %s))",
        (uuid.uuid4(), conversation_id, run_id, role, content, n),
    )


def _setup(pg, make_project):
    project_id = make_project()
    run_a = seed_run(pg, project_id, definition(knowledge=[]), status="completed")
    run_b = seed_run(pg, project_id, definition(knowledge=[]))
    conversation_id = _conversation(pg, project_id, run_a, run_b)
    _message(pg, conversation_id, run_a, "user", "Kaydın sahibi kim?", 0)
    _message(pg, conversation_id, run_a, "assistant", "Önceki cevap: <<PII_1>>", 1)
    _message(pg, conversation_id, run_b, "user", "Peki onun e-postası?", 2)
    return conversation_id, run_a, run_b


def _go(database_url, body):
    async def go():
        db.configure(database_url, pooled=False)
        client = aioredis.from_url(os.environ["REDIS_URL"])
        store = RedisTokenStore(client, 60, prefix=f"t08m2:{uuid.uuid4().hex}:")
        try:
            async with db.session_scope() as session:
                return await body(session, store)
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


def test_08t_m2_history_reversed_in_its_own_runs_scope(database_url, pg, make_project):
    conversation_id, run_a, run_b = _setup(pg, make_project)

    async def body(session, store):
        assert await store.token_for(str(run_a), "EMAIL_ADDRESS:" + AYSE, AYSE) == "<<PII_1>>"
        assert await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA) == "<<PII_1>>"
        history = await _history(session, conversation_id, run_b, store)
        # what B's reader would see for the earlier answer if B's scope reversed it
        echoed, _ = await detokenize("Önceki cevap: <<PII_1>>", store=store, scope=str(run_b))
        return history, echoed

    history, echoed = _go(database_url, body)
    assert history == [
        {"role": "user", "content": "Kaydın sahibi kim?"},
        {"role": "assistant", "content": f"Önceki cevap: {AYSE}"},  # A's value, from A's scope
    ]
    assert FATMA not in str(history)
    assert echoed.endswith(FATMA)  # why the history must not keep A's placeholder into B


def test_08t_m2_expired_placeholder_stays_and_never_becomes_a_new_value(
    database_url, pg, make_project
):
    conversation_id, _, run_b = _setup(pg, make_project)  # A's mapping is gone (never written)

    async def body(session, store):
        history = await _history(session, conversation_id, run_b, store)
        first_new = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)
        return history, first_new

    history, first_new = _go(database_url, body)
    assert history[1] == {"role": "assistant", "content": "Önceki cevap: <<PII_1>>"}
    assert first_new == "<<PII_2>>"  # B's counter starts after the carried <<PII_1>>
