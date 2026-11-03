"""08-tam-1a r2 MAJOR-r2-2/r2-3, MINOR-r2-1 at the store level (KARARLAR "Konuşma geçmişinde yer
tutucu eşlemesi doğrudan ve hamsız"): a placeholder moves from its scope to another for the same
value and identity, never through the raw text; an unknown one stays; the counter is reserved
past every number a scope can issue (at most 8 digits) before its first value."""

import asyncio

from ffcore.guardrails.masking import (
    MemoryTokenStore,
    placeholder_numbers,
    rescope,
    reserve_carried,
)

run = asyncio.run
AYSE = "ayse@example.test"


def test_08t_r2_entry_returns_value_and_identity():
    async def go():
        store = MemoryTokenStore()
        token = await store.token_for("a", "EMAIL_ADDRESS:" + AYSE, AYSE)
        return await store.entry("a", token), await store.entry("a", "<<PII_9>>")

    assert run(go()) == ((AYSE, "EMAIL_ADDRESS:" + AYSE), None)


def test_08t_r2_rescope_maps_without_the_raw_value():
    async def go():
        store = MemoryTokenStore()
        await store.token_for("a", "EMAIL_ADDRESS:" + AYSE, AYSE)  # <<PII_1>> in a
        await store.token_for("b", "EMAIL_ADDRESS:x@example.test", "x@example.test")  # 1 in b
        out = await rescope("Bkz. <<PII_1>> ve <<PII_4>>", store=store, source="a", target="b")
        return out, await store.lookup("b", "<<PII_2>>")

    out, value = run(go())
    assert out == "Bkz. <<PII_2>> ve <<PII_4>>" and value == AYSE
    assert AYSE not in out


def test_08t_r2_rescope_same_scope_is_unchanged():
    async def go():
        return await rescope("<<PII_1>>", store=MemoryTokenStore(), source="a", target="a")

    assert run(go()) == "<<PII_1>>"


def test_08t_r2_numbers_are_at_most_seven_digits():
    text = "<<PII_3>> <<PII_1234567>> <<PII_12345678>> <<PII_99999999999999999999999>>"
    assert placeholder_numbers(text) == [3, 1234567]  # r5 (h): from 10,000,000 none


def test_08t_r2_reserve_carried_reads_text_and_data():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", [{"content": "<<PII_4>>"}, "x <<PII_2>>"])
        await reserve_carried(store, "t", "nothing")
        first = await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)
        other = await store.token_for("t", "EMAIL_ADDRESS:" + AYSE, AYSE)
        return first, other

    assert run(go()) == ("<<PII_5>>", "<<PII_1>>")
