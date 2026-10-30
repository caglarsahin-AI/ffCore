"""FOLLOWUP-108: a breadcrumb names structure only (file, article number, short title <= 60
characters); the text of a plain-text article line never becomes a breadcrumb."""

import pytest

from ffcore.knowledge.chunking import ChunkSettings, chunk_markdown

SETTINGS = ChunkSettings(min_tokens=400, max_tokens=600)
WORD = "silmesinamasi1234"


def _procedure(word: str) -> str:
    # The plain-text procedure of test_18_f10_7 (no Markdown headings, articles as lines).
    lines = [
        f"{word} kayıt prosedürü",
        f"Madde 1 - Amaç: Bu prosedür {word} kayıtlarının nasıl tutulacağını açıklar.",
        f"Madde 2 - Süre: {word} kayıtları 30 gün boyunca saklanır, sonra arşive taşınır.",
        "Madde 3 - Sorumluluk: Kayıtların doğruluğundan birim sorumlusu sorumludur.",
        "Madde 4 - Erişim: Kayıtları yalnız yetkili personel görüntüleyebilir.",
    ]
    return "\n\n".join(lines * 3)


def test_af_2_article_line_text_stays_out_of_the_breadcrumb():
    chunks = chunk_markdown(_procedure(WORD), breadcrumb="KB › silme.txt", settings=SETTINGS)
    assert chunks
    assert any(WORD in c.body for c in chunks)
    for chunk in chunks:
        assert WORD not in chunk.breadcrumb, chunk.breadcrumb
        assert WORD not in (chunk.section_path or ""), chunk.section_path
    crumbs = " ".join(c.breadcrumb for c in chunks)
    assert "Madde 2 - Süre" in crumbs


@pytest.mark.parametrize(
    ("heading", "expected"),
    [
        ("Madde 10 - Fesih", "Madde 10 - Fesih"),
        ("Madde 2 - Süre: kayıtlar 30 gün saklanır", "Madde 2 - Süre"),
        ("Madde 7", "Madde 7"),
        ("Madde 5 - " + "uzun başlık " * 8, "Madde 5"),
        ("3.2 Teslim koşulları", "3.2 Teslim koşulları"),
        ("3.2 " + "çok uzun bir bölüm başlığı " * 4, "3.2"),
        ("Giriş " + "ve kapsam " * 10, None),
        ("", None),
    ],
)
def test_af_2_structural_heading_rule(heading, expected):
    from ffcore.knowledge.chunking import MAX_HEADING_CHARS, structural_heading

    got = structural_heading(heading)
    assert got == expected
    assert got is None or len(got) <= MAX_HEADING_CHARS
