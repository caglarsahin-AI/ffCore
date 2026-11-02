"""FOLLOWUP-137: Markdown headings are not code lines in Kapı 2 (`code_heavy`).

Docling joins a page's lines into paragraphs, so a short Confluence page keeps its headings as
separate lines while each section's text becomes one line; with `#` counted as code, the
paycore-like 1001/1002 shape (3 headings / 5 lines = 0.6) was skipped as `code_heavy` (B-19-0013).
A `# text` shell comment cannot be told from an H1 heading on one line: outside a fence it counts
as a heading; inside a fence the main rule stays, so it is code there (K-137-0006 A′). The fence
line itself is not code: the plain-text converter wraps every .txt in one fence.
"""

import pytest

from ffcore.knowledge import gates

# 1001.md (data/samples/paycore-like) as Docling returns it: headings on their own lines, each
# section's paragraphs joined into one line.
PAGE_1001 = (
    "# Ödeme Geçidi Kurulum Rehberi\n"
    "## Ön koşullar\n"
    "Ödeme geçidi servisi iç ağda çalışır ve yalnızca uygulama sunucularından erişilir. Kurulumdan "
    "önce veritabanı şeması hazırlanır, sertifikalar yüklenir ve izleme ajanı yapılandırılır.\n"
    "## Doğrulama\n"
    "Kurulum bittikten sonra sağlık ucu çağrılır, cevap 200 olmalıdır. Hata kodları işlem "
    "günlüğüne yazılır ve gün sonu raporunda özetlenir.\n"
)
PROSE = (
    "Bu sözleşme kapsamında yüklenici, bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür."
)
# Python whose comments are Turkish prose: 3 of 8 lines match a code pattern.
PY_WITH_COMMENTS = (
    "# bu betik her gün çalışır ve sonuç için bir kayıt yazar\n"
    "import json\n"
    "# dosya yoksa hata verilir, çünkü eksik veri ile devam edilmez\n"
    "def read(path):\n"
    "    return json.loads(open(path).read())\n"
    "# kayıt ile ilgili ayrıntı için ekibe bakılır\n"
    "class Reader:\n"
    "    pass\n"
)


def _is_code(line: str) -> bool:
    return gates._is_code_line(line, fenced=False)


def test_137_1_short_headed_page_passes():
    lines = [ln for ln in PAGE_1001.splitlines() if ln.strip()]
    assert len(lines) == 5 and sum(ln.startswith("#") for ln in lines) == 3  # the 0.6 shape
    assert gates.text_quality(PAGE_1001, title="Ödeme Geçidi Kurulum Rehberi") == ("ok", None)


@pytest.mark.parametrize("level", range(1, 7))
def test_137_2_heading_levels_not_code(level):
    hashes = "#" * level
    assert not _is_code(f"{hashes} Kurulum")
    assert not _is_code(f"  {hashes}\tÖn koşullar")
    text = f"{hashes} Başlık bir\n{hashes} Başlık iki\n{PROSE}"
    assert gates.text_quality(text, title="T") == ("ok", None)


@pytest.mark.parametrize(
    "line",
    ["#include <stdio.h>", "#!/bin/bash", "#define MAX 10", "#pragma once", "#", "# ", "####### x"],
)
def test_137_3_hash_without_heading_text_is_code(line):
    assert _is_code(line)


@pytest.mark.parametrize(
    "block",
    [
        "#include <stdio.h>\n#define MAX 10\nint main(void)\n{\n    return 0;\n}\n"
        "// toplam değeri yazdırılır ve program kapanır\n",
        f"```python\n{PY_WITH_COMMENTS}```\n",
        f"~~~\n{PY_WITH_COMMENTS}~~~\n",
    ],
    ids=["c", "fenced_python_with_prose_comments", "tilde_fenced_python"],
)
def test_137_4_real_code_still_code_heavy(block):
    """Inside a fence a `# text` comment is code as on main (K-137-0006 A′)."""
    assert gates.text_quality(block, title="T", min_tokens=1) == ("skipped", "code_heavy")


def test_137_5_threshold_unchanged():
    code = "import json"
    half = "\n".join([code, code, PROSE, PROSE])
    assert gates.text_quality(half, title="T") == ("ok", None)  # 0.5 is not over 0.5
    over = "\n".join([code, code, code, PROSE, PROSE])
    assert gates.text_quality(over, title="T") == ("skipped", "code_heavy")


def test_137_6_chunk_with_heading_passes():
    chunk = f"## Destek\n### İletişim\n{PROSE}"  # breadcrumb-free chunk body (ingest.py:533)
    assert gates.text_quality(chunk, title=None) == ("ok", None)


# DEMO-7.txt as the plain-text converter returns it (convert/text_formats.py): one fence around
# the whole file.
FENCED_TXT = (
    "```\nDEMO-7 Gün sonu raporunda kur farkı satırı eksik\n\n"
    "Bu kayıt, gün sonu raporunun döviz işlemlerinde kur farkı satırını göstermediği için açıldı.\n"
    "Sorun bir müşteri bildirimi ile fark edildi ve aynı gün içinde incelendi.\n```"
)


def test_137_7_fenced_plain_text_passes():
    """The fence line is not code and fenced prose is counted by pattern, as on main."""
    assert gates.text_quality(FENCED_TXT, title="DEMO-7") == ("ok", None)


def test_137_8_unclosed_fence_keeps_main_rule():
    """After a fence that never closes the main rule counts (fail-safe = main): `# text` is code."""
    headings = "# Başlık bir\n# Başlık iki\n# Başlık üç\n" + PROSE
    assert gates.text_quality(headings, title="T") == ("ok", None)  # outside a fence: headings
    unclosed = "```\n" + headings
    assert gates.text_quality(unclosed, title="T") == ("skipped", "code_heavy")  # 3 of 5


def test_137_9_unfenced_prose_commented_code_known_limit():
    """Known limit (PR "Kalan riskler"): unfenced code whose `# text` comments are prose reads
    as headings, so it passes Kapı 2. Pinned so a change here is a decision, not a drift."""
    assert gates.text_quality(PY_WITH_COMMENTS, title="T", min_tokens=1) == ("ok", None)
