"""08-lite: redact, mask and tokenize (brief 08 "Maskeleme modu")."""

import asyncio

import pytest

from ffcore.guardrails.masking import (
    MemoryTokenStore,
    TokenScopeMissing,
    apply_action,
    detokenize,
    mask_value,
)
from ffcore.guardrails.recognizers.regex import recognize

TEXT = "TC 10000000146, e-posta ayse@ornek.com, tel 0532 256 60 38."


def run(coro):
    return asyncio.run(coro)


def test_08_8_masking_formats():
    assert mask_value("TR_NATIONAL_ID", "10000000146") == "*******0146"
    assert mask_value("EMAIL_ADDRESS", "ayse@ornek.com") == "a***@ornek.com"
    assert mask_value("TR_PHONE", "0532 256 60 38") == "**** *** 60 38"


def test_08_8_redact_and_mask_keep_offsets_with_several_findings():
    findings = recognize(TEXT)
    assert len(findings) == 3
    redacted = run(apply_action(TEXT, findings, "redact"))
    assert redacted == "TC [TR_NATIONAL_ID], e-posta [EMAIL_ADDRESS], tel [TR_PHONE]."
    masked = run(apply_action(TEXT, findings, "mask"))
    assert masked == "TC *******0146, e-posta a***@ornek.com, tel **** *** 60 38."


def test_08_8_non_transforming_actions_leave_text():
    findings = recognize(TEXT)
    for action in ("block", "warn", "log"):
        assert run(apply_action(TEXT, findings, action)) == TEXT


def test_08_3_tokenize_roundtrip():
    store = MemoryTokenStore()
    text = "Ali'nin TC'si 10000000146; tekrar: 10000000146, mail ayse@ornek.com"
    findings = recognize(text)
    out = run(apply_action(text, findings, "tokenize", store=store, scope="run-1"))
    assert out == "Ali'nin TC'si <<PII_1>>; tekrar: <<PII_1>>, mail <<PII_2>>"
    restored, unresolved = run(detokenize(out, store=store, scope="run-1"))
    assert restored == text
    assert unresolved == []


def test_08_3_same_value_same_token_across_calls_in_a_run():
    store = MemoryTokenStore()
    first = run(
        apply_action(
            "a 10000000146", recognize("a 10000000146"), "tokenize", store=store, scope="r"
        )
    )
    second = run(
        apply_action(
            "b 10000000146", recognize("b 10000000146"), "tokenize", store=store, scope="r"
        )
    )
    other_run = run(
        apply_action(
            "c 10000000146", recognize("c 10000000146"), "tokenize", store=store, scope="other"
        )
    )
    assert first == "a <<PII_1>>" and second == "b <<PII_1>>" and other_run == "c <<PII_1>>"
    # Scopes do not leak: the other run's token does not resolve in this one.
    assert run(store.lookup("r", "<<PII_1>>")) == "10000000146"
    assert run(store.lookup("missing", "<<PII_1>>")) is None


def test_08_3_unknown_placeholder_is_reported_not_invented():
    store = MemoryTokenStore()
    restored, unresolved = run(detokenize("x <<PII_7>> y", store=store, scope="r"))
    assert restored == "x <<PII_7>> y"
    assert unresolved == ["<<PII_7>>"]


def test_08_3_tokenize_without_scope_fails_loud():
    with pytest.raises(TokenScopeMissing):
        run(apply_action(TEXT, recognize(TEXT), "tokenize", store=MemoryTokenStore(), scope=None))


def test_08_3_distinct_values_never_share_a_token():
    # Review r1: "a.b@x" and "ab@x" are different addresses; normalising them merged the tokens.
    store = MemoryTokenStore()
    text = "a.b@ornek.com ve ab@ornek.com"
    out = run(apply_action(text, recognize(text), "tokenize", store=store, scope="r"))
    assert out == "<<PII_1>> ve <<PII_2>>"
    restored, _ = run(detokenize(out, store=store, scope="r"))
    assert restored == text


class CooperativeRedis:
    """Hash commands that yield to the event loop between calls, like a network round trip.
    `eval` runs the store's script semantics in one step (Redis runs Lua atomically)."""

    def __init__(self):
        self.data: dict[str, dict[str, str]] = {}
        self.counters: dict[str, int] = {}

    async def _tick(self):
        await asyncio.sleep(0)

    async def hget(self, name, field):
        await self._tick()
        return self.data.get(name, {}).get(field)

    async def hincrby(self, name, field, amount):
        await self._tick()
        h = self.data.setdefault(name, {})
        h[field] = str(int(h.get(field, 0)) + amount)
        return int(h[field])

    async def hsetnx(self, name, field, value):
        await self._tick()
        h = self.data.setdefault(name, {})
        if field in h:
            return False
        h[field] = value
        return True

    async def hset(self, name, field=None, value=None, mapping=None):
        # A slower round trip: the window in which another caller sees only the forward entry.
        for _ in range(5):
            await self._tick()
        h = self.data.setdefault(name, {})
        if field is not None:
            h[field] = value
        h.update(mapping or {})

    async def expire(self, name, ttl):
        await self._tick()

    async def eval(self, script, numkeys, name, counter, key, value, ttl, counter_ttl, top):
        # The store's get-or-create script: mapping hash + its own counter key (r1 MAJOR-1).
        await self._tick()
        h = self.data.setdefault(name, {})
        if "k:" + key not in h:
            n = self.counters.get(counter, 0) + 1
            self.counters[counter] = n
            token = f"<<PII_{n}>>"
            h["k:" + key] = token
            h["t:" + token] = value
        return h["k:" + key]


def test_08_3_redis_store_publishes_both_directions_atomically():
    # Review r1: a second caller could see the forward entry before the reverse one existed.
    from ffcore.guardrails.masking import RedisTokenStore

    async def scenario():
        fake = CooperativeRedis()
        store = RedisTokenStore(fake, ttl_s=60)
        first = asyncio.create_task(store.token_for("r", "TR_NATIONAL_ID:1", "10000000146"))
        # Wait until the forward entry is visible. With a non-atomic write the reverse entry is
        # still missing at this point; an atomic write publishes both at once.
        for _ in range(100):
            if "k:TR_NATIONAL_ID:1" in fake.data.get("ffcore:pii:r", {}):
                break
            await asyncio.sleep(0)
        token = await store.token_for("r", "TR_NATIONAL_ID:1", "10000000146")
        resolved = await store.lookup("r", token)
        await first
        return token, resolved

    token, resolved = run(scenario())
    assert token == "<<PII_1>>"
    assert resolved == "10000000146"


def test_08_8_masked_value_is_never_the_raw_value():
    # Review r1 MAJOR-1: a one-letter local part and short values were stored unchanged.
    assert mask_value("EMAIL_ADDRESS", "a@example.org") == "*@example.org"
    assert mask_value("PIN", "7") == "*"
    assert mask_value("CVV", "738") == "**8"
    assert mask_value("PIN", "1234") == "**34"
    for category, value in [
        ("EMAIL_ADDRESS", "ab@x.io"),
        ("PIN", "0"),
        ("TR_PLATE", "06 A 1"),
        ("PASSWORD", "x"),
        ("API_TOKEN", "--a--"),
        ("PERSON", "..."),
    ]:
        masked = mask_value(category, value)
        assert masked != value, (category, value)
        assert len(masked) == len(value)
