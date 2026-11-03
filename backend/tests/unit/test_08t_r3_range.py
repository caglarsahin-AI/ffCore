"""08-tam-1a r3 MINOR-r3-2 (KARARLAR "C17 URL bağlam kuralı, ek" (f)): a scope's numbers stay at 8
digits. A carried number is reserved only when the next one stays at most 99,999,999 (the reserve
is at most 99,999,998); a larger one fails loudly (`placeholder_out_of_range`), and so does a
counter that would pass 8 digits. A 9+ digit `<<PII_n>>` is no placeholder: never reversed in any
scope. The reviewer's case: `<<PII_99999999>>` in the history pushed the counter to 9 digits and
a stale 9-digit placeholder read as a new value."""

import asyncio

import pytest

from ffcore.core.errors import ApiError
from ffcore.guardrails.masking import (
    MemoryTokenStore,
    placeholder_numbers,
    reserve_carried,
    reveal_text,
)

run = asyncio.run
AYSE = "ayse@example.test"


def test_08t_r3_largest_carried_number_is_reserved():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_99999998>>")
        return await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)

    assert run(go()) == "<<PII_99999999>>"


def test_08t_r3_carried_number_past_the_range_fails_loudly():
    async def go():
        await reserve_carried(MemoryTokenStore(), "s", "geçmiş <<PII_99999999>>")

    with pytest.raises(ApiError) as caught:
        run(go())
    assert caught.value.code == "placeholder_out_of_range"


def test_08t_r3_counter_past_eight_digits_fails_loudly():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_99999998>>")
        await store.token_for("s", "EMAIL_ADDRESS:a@x.test", "a@x.test")  # 99,999,999
        await store.token_for("s", "EMAIL_ADDRESS:b@x.test", "b@x.test")

    with pytest.raises(ApiError) as caught:
        run(go())
    assert caught.value.code == "placeholder_out_of_range"


def test_08t_r3_nine_digit_text_is_no_placeholder():
    async def go():
        store = MemoryTokenStore()
        store._scopes["s"] = {"t:<<PII_100000000>>": AYSE}  # as if a scope had issued it
        return await reveal_text("eski <<PII_100000000>>", store=store, scope="s")

    assert run(go()) == ("eski <<PII_100000000>>", 0, 0)
    assert placeholder_numbers("<<PII_100000000>> <<PII_7>>") == [7]
