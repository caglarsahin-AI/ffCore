"""Review 04a r1 MAJOR-4: the embedded text (breadcrumb + body) stays within max_tokens under the
counter the ingest uses, words longer than the limit are split by that counter, a breadcrumb that
leaves no room fails loud, and no content is lost. The real bge-m3 tokenizer runs the same inputs
in tests/models/test_04a_convert_models.py."""

import re

import pytest

from ffcore.knowledge.chunking import ChunkingError, ChunkSettings, approx_tokens, chunk_markdown


def per_char(text: str) -> int:
    """CJK-like: every character one token (bge-m3 counts 1002 for 1000 Chinese characters)."""
    return len(text)


def per_byte_pair(text: str) -> int:
    """Emoji-like: multi-byte characters weigh several tokens."""
    return len(text.encode("utf-8")) // 2


def compact(text: str) -> str:
    """Without whitespace and heading lines: headings move into the breadcrumb."""
    return "".join(re.sub(r"^#{1,3}\s+.*$", "", text, flags=re.M).split())


def check(body, breadcrumb, count):
    settings = ChunkSettings.from_kb(400, 0, count)
    chunks = chunk_markdown(body, breadcrumb=breadcrumb, settings=settings)
    assert chunks
    for chunk in chunks:
        assert count(chunk.text) <= settings.max_tokens, (count(chunk.text), chunk.body[:40])
        assert chunk.token_count == count(chunk.text)
    assert "".join(compact(c.body) for c in chunks) == compact(body)  # nothing dropped
    return chunks


def test_04a_r1_4_long_breadcrumb_counts_toward_the_budget():
    crumb = "KB › " + " ".join(["Uzun-bölüm-başlığı"] * 40)
    check("the " * 600, crumb, approx_tokens)


def test_04a_r1_4_single_long_word_is_split_by_tokens():
    check("中" * 1000, "KB › Belge", per_char)


def test_04a_r1_4_emoji_run_is_split_by_tokens():
    check("🙂" * 500 + " son", "KB › Belge", per_byte_pair)


def test_04a_r1_4_mixed_text_with_headings_stays_within_budget():
    body = "\n\n".join(f"# Bölüm {i}\n\n" + "中" * 300 + " açıklama " * 40 for i in range(4))
    check(body, "KB › Belge", per_char)


def test_04a_r1_4_breadcrumb_without_room_fails_loud():
    settings = ChunkSettings.from_kb(400, 0, per_char)
    with pytest.raises(ChunkingError) as raised:
        # 400 + 300 tokens: the body must be split, and the breadcrumb leaves less than half.
        chunk_markdown("gövde " * 50, breadcrumb="B" * 400, settings=settings)
    assert raised.value.code == "chunk_breadcrumb_too_long"
