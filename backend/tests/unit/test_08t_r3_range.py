"""08-tam-1a r3 MINOR-r3-2, r4 MINOR-r4-1/r4-2 (KARARLAR "C17 URL bağlam kuralı, ek" (f′) and "C17
geri çevirme: cevap düzeyinde HTML fail-closed"): a scope issues at most 99,999,998. 99,999,999
is never issued, reserved or reversed: a carried `<<PII_99999999>>` is ignored, so a conversation
that has one keeps working. A scope that would issue past 99,999,998 fails loudly
(`placeholder_out_of_range`), in the engine too, whatever the policy's `on_error` says: a policy
with `on_error=log` must not let the value leave untokenized. A 9+ digit `<<PII_n>>` is no
placeholder."""

import asyncio

import pytest

from ffcore.core.errors import ApiError
from ffcore.guardrails import engine
from ffcore.guardrails.builtin import BUILTIN_DEFAULT
from ffcore.guardrails.masking import (
    MemoryTokenStore,
    PlaceholderOutOfRange,
    placeholder_numbers,
    reserve_carried,
    reveal_text,
)

run = asyncio.run
AYSE = "ayse@example.test"


def test_08t_r3_largest_carried_number_is_reserved():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_99999997>>")
        return await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)

    assert run(go()) == "<<PII_99999998>>"


def test_08t_r4_carried_99999999_is_ignored():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "geçmiş <<PII_99999999>>")
        return await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)

    assert run(go()) == "<<PII_1>>"


def test_08t_r4_issuing_past_99999998_fails_loudly():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_99999998>>")
        await store.token_for("s", "EMAIL_ADDRESS:a@x.test", "a@x.test")

    with pytest.raises(ApiError) as caught:
        run(go())
    assert caught.value.code == "placeholder_out_of_range"


def test_08t_r3_nine_digit_text_and_99999999_are_no_placeholders():
    async def go():
        store = MemoryTokenStore()
        store._scopes["s"] = {"t:<<PII_100000000>>": AYSE, "t:<<PII_99999999>>": AYSE}
        return await reveal_text("<<PII_100000000>> <<PII_99999999>>", store=store, scope="s")

    assert run(go()) == ("<<PII_100000000>> <<PII_99999999>>", 0, 0)
    assert placeholder_numbers("<<PII_100000000>> <<PII_99999999>> <<PII_7>>") == [7]


def _log_on_error_policy():
    spec = BUILTIN_DEFAULT.spec.model_copy(update={"on_error": "log", "mode": "enforce"})
    return type(BUILTIN_DEFAULT)(
        key="p", spec=spec, pii_policies=BUILTIN_DEFAULT.pii_policies, builtin=False
    )


def test_08t_r4_engine_fails_loudly_whatever_on_error_says():
    # MINOR-r4-1: the caller fills the scope (`<<PII_99999998>>`) and sends a value; with
    # `on_error=log` the old engine let the text through untokenized.
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_99999998>>")
        ctx = engine.EvalContext(
            run_id="s", project_id="p", source="api", token_store=store, egress_enabled=True
        )
        return await engine.evaluate(f"Adresim {AYSE}", "egress", _log_on_error_policy(), ctx=ctx)

    with pytest.raises(PlaceholderOutOfRange):
        run(go())
