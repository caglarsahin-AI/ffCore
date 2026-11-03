"""08-tam-1a r3 MINOR-r3-2, r4 MINOR-r4-1, r5 MINOR-r5-1 (KARARLAR "C17 HTML kuralı, düzeltmeler"
(h), which replaces (f′)): a scope issues at most 9,999,999. A carried number at or above
10,000,000 is no placeholder: never reserved or reversed, so a conversation that carries
`<<PII_99999998>>` (or any 8-digit number) keeps working and later values get ordinary numbers;
only ASCII digits make a placeholder (`<<PII_٩٩٩٩٩٩٩٩>>` is text). A scope that would issue past
9,999,999 fails loudly (`placeholder_out_of_range`), in the engine too whatever the policy's
`on_error` says (r4 MINOR-r4-1)."""

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
ARABIC = "<<PII_" + "٩" * 8 + ">>"


def test_08t_r3_largest_carried_number_is_reserved():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_9999998>>")
        return await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)

    assert run(go()) == "<<PII_9999999>>"


@pytest.mark.parametrize(
    "carried", ["<<PII_99999999>>", "<<PII_99999998>>", "<<PII_10000000>>", ARABIC]
)
def test_08t_r5_carried_numbers_from_ten_million_are_ignored(carried):
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", f"geçmiş {carried}")
        return await store.token_for("s", "EMAIL_ADDRESS:" + AYSE, AYSE)

    assert run(go()) == "<<PII_1>>"


def test_08t_r5_issuing_past_9999999_fails_loudly():
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_9999999>>")
        await store.token_for("s", "EMAIL_ADDRESS:a@x.test", "a@x.test")

    with pytest.raises(ApiError) as caught:
        run(go())
    assert caught.value.code == "placeholder_out_of_range"


def test_08t_r5_large_and_non_ascii_numbers_are_no_placeholders():
    texts = ["<<PII_100000000>>", "<<PII_99999999>>", "<<PII_10000000>>", ARABIC]

    async def go():
        store = MemoryTokenStore()
        store._scopes["s"] = {"t:" + t: AYSE for t in texts}  # as if a scope had issued them
        return await reveal_text(" ".join(texts), store=store, scope="s")

    assert run(go()) == (" ".join(texts), 0, 0)
    assert placeholder_numbers(" ".join([*texts, "<<PII_7>>"])) == [7]


def _log_on_error_policy():
    spec = BUILTIN_DEFAULT.spec.model_copy(update={"on_error": "log", "mode": "enforce"})
    return type(BUILTIN_DEFAULT)(
        key="p", spec=spec, pii_policies=BUILTIN_DEFAULT.pii_policies, builtin=False
    )


def test_08t_r4_engine_fails_loudly_whatever_on_error_says():
    # MINOR-r4-1: the caller fills the scope (`<<PII_9999999>>`) and sends a value; with
    # `on_error=log` the old engine let the text through untokenized.
    async def go():
        store = MemoryTokenStore()
        await reserve_carried(store, "s", "<<PII_9999999>>")
        ctx = engine.EvalContext(
            run_id="s", project_id="p", source="api", token_store=store, egress_enabled=True
        )
        return await engine.evaluate(f"Adresim {AYSE}", "egress", _log_on_error_policy(), ctx=ctx)

    with pytest.raises(PlaceholderOutOfRange):
        run(go())
