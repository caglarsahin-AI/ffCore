"""04b-2 slice 1 (K-04B-0021).

FOLLOWUP-87 (S-b A): Markdown is already structured text; `.md` and `.markdown` do not go through
Docling (no model weights needed), the text stays as written (headings and tables kept) and the
engine is `markdown`. FOLLOWUP-145: Kapı 2's prose check counts English function words too, so a
short English page is not `no_prose`.
"""

import time

import pytest

from ffcore.knowledge.convert import pipeline, router
from ffcore.knowledge.convert.types import CONVERTED
from ffcore.knowledge.gates import FLAGGED, SKIPPED, text_quality
from ffcore.knowledge.gates import OK as GATE_OK

MARKDOWN = """# Bakım Sözleşmesi

## Madde 1 Kapsam

Bu sözleşme kapsamında yüklenici bakım hizmetini aylık olarak verir ve her ziyaret için bir
rapor düzenler.

| Ziyaret | Süre |
|---|---|
| Aylık | 2 saat |
"""

ENGLISH = (
    "The contractor provides the maintenance service every month and writes a report for each "
    "visit. Disputes between the parties are first settled by mediation, and the notice period "
    "for termination is ninety days."
)


@pytest.mark.parametrize("name", ["sozlesme.md", "sozlesme.markdown", "SOZLESME.MD"])
def test_04b_2_87_markdown_is_its_own_route(tmp_path, name):
    path = tmp_path / name
    path.write_text(MARKDOWN, encoding="utf-8")
    assert router.sniff(path) == "markdown"


def test_04b_2_87_markdown_kept_as_written_without_weights(tmp_path):
    path = tmp_path / "sozlesme.md"
    path.write_text(MARKDOWN, encoding="utf-8")
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == CONVERTED, result
    assert result.method == "markdown"
    assert "## Madde 1 Kapsam" in result.text_md
    assert "| Aylık | 2 saat |" in result.text_md
    assert not result.text_md.startswith("```")  # not fenced like plain text


def test_04b_2_87_undecodable_markdown_fails_loud(tmp_path):
    path = tmp_path / "bozuk.md"
    path.write_bytes(b"ok line\n\x81\x8d broken\n" + b"x" * 40)
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.error_code == "encoding_undecodable"


def test_04b_2_145_english_prose_is_not_no_prose():
    status, reason = text_quality(ENGLISH, title="Maintenance")
    assert (status, reason) == (GATE_OK, None)


def test_04b_2_145_prose_free_text_is_still_no_prose():
    nouns = "\n".join(
        f"Müşteri numarası hesap kodu işlem tarihi tutar bakiye {i}" for i in range(6)
    )
    status, reason = text_quality(nouns, title="Alanlar")
    assert status in {SKIPPED, FLAGGED} and reason == "no_prose"
