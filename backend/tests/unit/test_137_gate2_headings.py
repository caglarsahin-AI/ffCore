"""FOLLOWUP-137: Markdown headings are not code lines in Kapı 2 (`code_heavy`).

Docling joins a page's lines into paragraphs, so a short Confluence page keeps its headings as
separate lines while each section's text becomes one line; with `#` counted as code, the
paycore-like 1001/1002 shape (3 headings / 5 lines = 0.6) was skipped as `code_heavy` (B-19-0013).
A `# text` shell comment cannot be told from an H1 heading on one line: outside a fence it counts
as a heading; inside a fence every line is code (K-137-0004 A).
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
    return bool(gates._CODE_LINE.match(line))


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
    """Inside a fence every line is code, a `# text` comment included (K-137-0004 A)."""
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


def test_137_7_fenced_log_counts_as_code():
    """A fenced log or config sample is code by intent, prose-like words or not."""
    log = "\n".join(f"servis {i} yeniden başlatıldı ve kuyruk boşaltıldı" for i in range(4))
    text = f"## Günlük örneği\n{PROSE}\n```\n{log}\n```\n"
    assert gates.text_quality(text, title="T") == ("skipped", "code_heavy")


def test_137_8_unclosed_fence_rest_is_code():
    """A fence that never closes: every line after it is code (fail-safe, not prose)."""
    unclosed = f"{PROSE}\n```\n{PROSE}\n{PROSE}"
    assert gates.text_quality(unclosed, title="T") == ("skipped", "code_heavy")
    closed = f"{PROSE}\n```\n{PROSE}\n```\n{PROSE}\n{PROSE}\n{PROSE}"
    assert gates.text_quality(closed, title="T") == ("ok", None)  # 3 of 7 lines


def test_137_9_unfenced_prose_commented_code_known_limit():
    """Known limit (PR "Kalan riskler"): unfenced code whose `# text` comments are prose reads
    as headings, so it passes Kapı 2. Pinned so a change here is a decision, not a drift."""
    assert gates.text_quality(PY_WITH_COMMENTS, title="T", min_tokens=1) == ("ok", None)
