"""08-tam-1a r1 MAJOR-2 and r2 MAJOR-r2-2/r2-3, MINOR-r2-1/r2-4 on Postgres and Redis (KARARLAR
"Konuşma geçmişinde yer tutucu eşlemesi doğrudan ve hamsız"): an earlier run's answer in the
conversation carries that run's placeholders. When the history goes into a new run each one
becomes the new run's placeholder for the same value, never the raw value; a placeholder whose
mapping is gone stays, and the new scope's counter starts after every number in the history and
the question, so it never becomes another value of the new run. Reading the history does not
renew the earlier run's mapping. The reviewer's probe: A has ayse = <<PII_1>>, B has fatma =
<<PII_1>>; A's answer must not read "fatma" in B."""

import asyncio
import os
import uuid

import redis.asyncio as aioredis

from ffcore.core import db
from ffcore.guardrails.masking import RedisTokenStore
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
        prefix = f"t08m2:{uuid.uuid4().hex}:"
        store = RedisTokenStore(client, 60, prefix=prefix)
        try:
            async with db.session_scope() as session:
                return await body(session, store, client, prefix)
        finally:
            await client.aclose()
            db.reset()

    return asyncio.run(go())


def test_08t_m2_history_maps_to_the_new_scope_without_the_raw_value(database_url, pg, make_project):
    conversation_id, run_a, run_b = _setup(pg, make_project)

    async def body(session, store, client, prefix):
        assert await store.token_for(str(run_a), "EMAIL_ADDRESS:" + AYSE, AYSE) == "<<PII_1>>"
        history = await _history(session, conversation_id, run_b, store)
        token = history[1]["content"].removeprefix("Önceki cevap: ")
        # B's own value for the same address, issued later, shares the placeholder
        again = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + AYSE, AYSE)
        fatma = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)
        return history, token, await store.lookup(str(run_b), token), again, fatma

    history, token, value, again, fatma = _go(database_url, body)
    assert history[0] == {"role": "user", "content": "Kaydın sahibi kim?"}
    assert AYSE not in str(history) and token.startswith("<<PII_")
    assert value == AYSE and again == token  # A's value, as B's placeholder
    assert fatma != token


def test_08t_m2_expired_placeholder_stays_and_never_becomes_a_new_value(
    database_url, pg, make_project
):
    conversation_id, _, run_b = _setup(pg, make_project)  # A's mapping is gone (never written)

    async def body(session, store, client, prefix):
        history = await _history(session, conversation_id, run_b, store)
        first_new = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)
        return history, first_new

    history, first_new = _go(database_url, body)
    assert history[1] == {"role": "assistant", "content": "Önceki cevap: <<PII_1>>"}
    assert first_new == "<<PII_2>>"  # B's counter starts after the carried <<PII_1>>


def test_08t_r2_question_numbers_are_reserved_first(database_url, pg, make_project):
    # MAJOR-r2-2: a placeholder copied into the question (from another run the user saw) is
    # passed by the counter before the run tokenizes anything; a run without a conversation too.
    _, _, run_b = _setup(pg, make_project)

    async def body(session, store, client, prefix):
        await _history(session, None, run_b, store, "<<PII_7>> ve fatma@example.test")
        return await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)

    assert _go(database_url, body) == "<<PII_8>>"


def test_08t_r2_only_numbers_a_scope_can_issue_are_reserved(database_url, pg, make_project):
    # MINOR-r2-1: a nine-digit or overflowing number someone wrote is not reserved.
    conversation_id, _, run_b = _setup(pg, make_project)
    question = "<<PII_100000000>> <<PII_99999999999999999999999>> <<PII_12345678>>"

    async def body(session, store, client, prefix):
        await _history(session, conversation_id, run_b, store, question)
        return await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)

    assert _go(database_url, body) == "<<PII_12345679>>"


def test_08t_r2_history_does_not_renew_the_earlier_mapping(database_url, pg, make_project):
    # MINOR-r2-4
    conversation_id, run_a, run_b = _setup(pg, make_project)

    async def body(session, store, client, prefix):
        await store.token_for(str(run_a), "EMAIL_ADDRESS:" + AYSE, AYSE)
        await client.expire(prefix + str(run_a), 5)
        await _history(session, conversation_id, run_b, store)
        return await client.ttl(prefix + str(run_a))

    assert 0 < _go(database_url, body) <= 5


def test_08t_r2_client_history_rows_take_the_following_runs_scope(database_url, pg, make_project):
    # Rows without a run (a facade agent client's earlier turns) were written in the scope of the
    # run whose question follows them; a later run maps them from there.
    project_id = make_project()
    run_a = seed_run(pg, project_id, definition(knowledge=[]), status="completed")
    run_b = seed_run(pg, project_id, definition(knowledge=[]))
    conversation_id = _conversation(pg, project_id, run_a, run_b)
    _message(pg, conversation_id, None, "user", "Adresim <<PII_1>>", 0)
    _message(pg, conversation_id, run_a, "user", "Kayıt kimde?", 1)
    _message(pg, conversation_id, run_b, "user", "Tekrar?", 2)

    async def body(session, store, client, prefix):
        await store.token_for(str(run_a), "EMAIL_ADDRESS:" + AYSE, AYSE)
        mine = await _history(session, conversation_id, run_a, store)
        later = await _history(session, conversation_id, run_b, store)
        token = later[0]["content"].removeprefix("Adresim ")
        return mine, later, await store.lookup(str(run_b), token)

    mine, later, value = _go(database_url, body)
    assert mine[0] == {"role": "user", "content": "Adresim <<PII_1>>"}  # its own scope, as is
    assert AYSE not in str(later) and value == AYSE


def test_08t_r4_history_99999999_is_ignored_and_the_range_ends_loudly(
    database_url, pg, make_project
):
    # r4 MINOR-r4-2 (KARARLAR ek (f′)): `<<PII_99999999>>` in the conversation is ignored, so the
    # conversation keeps working; a scope that would issue past 99,999,998 fails with a code.
    import pytest

    from ffcore.guardrails.masking import PlaceholderOutOfRange

    conversation_id, run_a, run_b = _setup(pg, make_project)
    _message(pg, conversation_id, run_a, "assistant", "Yankı <<PII_99999999>>", 1.5)

    async def body(session, store, client, prefix):
        history = await _history(session, conversation_id, run_b, store)
        first = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + FATMA, FATMA)
        await store.reserve(str(run_b), 99_999_997)
        last = await store.token_for(str(run_b), "EMAIL_ADDRESS:" + AYSE, AYSE)
        with pytest.raises(PlaceholderOutOfRange):
            await store.token_for(str(run_b), "EMAIL_ADDRESS:x@example.test", "x@example.test")
        return history, first, last

    history, first, last = _go(database_url, body)
    assert history[2]["content"] == "Yankı <<PII_99999999>>"
    assert (first, last) == ("<<PII_2>>", "<<PII_99999998>>")  # after the stale <<PII_1>>
