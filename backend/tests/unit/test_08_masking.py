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
