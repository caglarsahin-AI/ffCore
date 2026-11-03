"""08-tam-1a r1 MAJOR-1 on the real Redis token store (KARARLAR "Yer tutucu sayacı"): when a
scope's mapping expires (PII_TOKEN_TTL_S), a new value in that scope must not get an old
number, or a stored placeholder would be read back as another person's value. The reviewer's
probe: ali → <<PII_1>>, TTL passes, veli in the same scope; the old answer stays a placeholder.
A lookup renews the mapping's TTL."""

import asyncio
import os
import time
import uuid

import redis.asyncio as aioredis

from ffcore.guardrails.masking import RedisTokenStore, detokenize


def _with_store(ttl, body):
    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            return await body(RedisTokenStore(client, ttl, prefix=f"t08m1:{uuid.uuid4().hex}:"))
        finally:
            await client.aclose()

    return asyncio.run(go())


def test_08t_m1_expired_scope_never_reuses_a_number():
    scope = "run-a"
    stored = "Kayıt sahibi <<PII_1>>."

    async def before(store):
        return await store.token_for(scope, "EMAIL_ADDRESS:ali@example.test", "ali@example.test")

    async def after(store):
        token = await store.token_for(scope, "EMAIL_ADDRESS:veli@example.test", "veli@example.test")
        return token, await detokenize(stored, store=store, scope=scope)

    async def both(store):
        first = await before(store)
        await asyncio.sleep(2.5)  # the mapping (TTL 2 s) expires; the counter does not
        return first, *(await after(store))

    first, second, (text, unresolved) = _with_store(2, both)
    assert first == "<<PII_1>>"
    assert second == "<<PII_2>>"  # the next number, not 1 again
    assert text == stored and unresolved == ["<<PII_1>>"]  # never "veli@example.test"


def test_08t_m1_lookup_renews_the_mapping():
    scope = "run-b"

    async def body(store):
        token = await store.token_for(scope, "PERSON:Ayşe Kaya", "Ayşe Kaya")
        for _ in range(3):  # 3 x 1.5 s > the 3 s TTL, each lookup renews it
            time.sleep(1.5)
            assert await store.lookup(scope, token) == "Ayşe Kaya"
        return token

    assert _with_store(3, body) == "<<PII_1>>"


def test_08t_m1_reserve_moves_the_counter_past_carried_numbers():
    async def body(store):
        await store.reserve("run-c", 7)
        await store.reserve("run-c", 3)  # never backwards
        return await store.token_for("run-c", "PERSON:x", "x")

    assert _with_store(60, body) == "<<PII_8>>"
