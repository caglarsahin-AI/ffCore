"""04a slice 2: scope, gates, normalizer (format cleanup) and chunking. Pure functions."""

import pytest

from ffcore.knowledge import chunking, gates, normalize, scope
from ffcore.knowledge.chunking import ChunkSettings, approx_tokens, chunk_markdown

PROSE = (
    "Bu sözleşme kapsamında yüklenici, bakım hizmetini aylık olarak verir ve her ziyaret için "
    "bir rapor düzenler. Taraflar arasında çıkan anlaşmazlıklar önce uzlaşma ile çözülür, "
    "sonra yetkili mahkemeye gidilir. "
)


# --- scope (Kapı 0 format scope, one definition) ---


@pytest.mark.parametrize(
    ("name", "size", "expected"),
    [
        ("tool.exe", 10, ("skipped", "binary")),
        ("export.xlsx", 10, ("skipped", "out_of_scope")),
        ("screen.png", 10, ("skipped", "out_of_scope")),
        ("archive.zip", 10, ("skipped", "out_of_scope")),
        ("talk.mp4", 10, ("skipped", "video_disabled")),
        ("old.ppt", 10, ("skipped", "libreoffice_unavailable")),
        ("notes.txt", 6 * 1024 * 1024, ("skipped", "too_large")),
        ("contract.pdf", 6 * 1024 * 1024, ("ok", None)),
        ("contract.pdf", 501 * 1024 * 1024, ("skipped", "too_large")),
        ("contract.docx", 10, ("ok", None)),
    ],
)
def test_04a_gate0_upload_rule(name, size, expected):
    assert scope.gate0_upload(name, size) == expected


def test_04a_gate0_doc_extension_is_left_to_sniffing():
    # A ".doc" may be MHTML (Word "single file web page"): only content sniffing can tell.
    assert scope.gate0_upload("report.doc", 10) == ("ok", None)


# --- normalizer: format cleanup only (K1 default) ---


def test_04a_12_clean_markdown_format_only():
    raw = "Başlık<br>satır1&nbsp;&nbsp;satır2\\nüç  boşluk <td>a</td><td>b</td>"
    assert normalize.clean_markdown(raw) == "Başlık\nsatır1 satır2\nüç boşluk a b"


def test_04a_12_clean_markdown_keeps_code_and_angle_text():
    raw = "Tip `List<string>` ve <müşteri_adı>\n\n```\n<config>a  b</config>\n```"
    assert normalize.clean_markdown(raw) == raw


def test_04a_12_format_cleanup_nfc_and_invisible_characters():
    decomposed = "Şu​ metin ş"  # zero width space, s + combining cedilla
    assert normalize.clean_markdown(decomposed) == "Şu metin ş"


def test_04a_12_normalizer_config_id_is_format_only():
    assert normalize.NORMALIZER_CONFIG_ID == "format-v1"


# --- gates ---


def test_04a_8a_navigation_page_is_boilerplate():
    nav = "\n".join(f"- [Alt sayfa {i}](https://wiki.example.test/p/{i})" for i in range(40))
    assert gates.text_quality(nav, title="Ana sayfa") == ("skipped", "boilerplate")


def test_04a_8b_log_attachment_is_data_dump():
    log = "\n".join(f"2026-10-0{i % 9 + 1} 10:00:0{i % 10} INFO job={i} ok" for i in range(10_000))
    assert gates.data_dump(log) == "log"
    assert gates.data_dump(PROSE * 30) is None


def test_04a_8_data_dump_kinds():
    trace = "\n".join(["Traceback (most recent call last)"] + ['  File "a.py", line 3'] * 30)
    encoded = "\n".join(["QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVphYmNkZWZn" * 2] * 30)
    tabular = "\n".join(f"{i};4111{i:04d};{i * 3}.50;TRY" for i in range(30))
    assert gates.data_dump(trace) == "stack_trace"
    assert gates.data_dump(encoded) == "encoded"
    assert gates.data_dump(tabular) == "tabular"
    markdown_table = "\n".join(f"| Alan {i} | Açıklama {i} |" for i in range(30))
    assert gates.data_dump(markdown_table) is None  # a document's own table is not data


def test_04a_gate1_language_rule_allows_tr_and_en():
    english = (
        "This agreement is made between the parties and it sets out the terms of the service "
        "that will be provided by the contractor for the hospital. "
    ) * 5
    german = (
        "Dieser Vertrag wird zwischen den Parteien geschlossen und regelt die Bedingungen der "
        "Leistungen, die der Auftragnehmer erbringt. "
    ) * 5
    assert gates.gate1(PROSE * 3, title="T", allowed_languages=("tr", "en")) == ("ok", None)
    assert gates.gate1(english, title="T", allowed_languages=("tr", "en")) == ("ok", None)
    assert gates.gate1(english, title="T", allowed_languages=("tr",)) == (
        "skipped",
        "language_not_allowed",
    )
    assert gates.gate1(german, title="T", allowed_languages=("tr", "en")) == (
        "skipped",
        "language_not_allowed",
    )


def test_04a_gate1_short_empty_template_duplicate():
    assert gates.gate1("", title="T") == ("skipped", "empty")
    assert gates.gate1("kısa not", title="T") == ("skipped", "too_short")
    assert gates.gate1("kısa not", title="T", has_attachment_text=True) == ("ok", None)
    assert gates.gate1(PROSE * 3, title="Şablon: bakım formu") == ("skipped", "template")
    assert gates.gate1(PROSE * 3, title="T", duplicate_of="d-1") == (
        "skipped",
        "duplicate_of:d-1",
    )


def test_04a_8c_no_prose_flagged_when_large_skipped_when_small():
    table = "\n".join(f"KOD{i} TANIM{i} DEGER{i}" for i in range(200))
    assert gates.text_quality(table, title="T") == ("flagged", "no_prose")
    assert gates.text_quality("KOD1 TANIM1 " * 20, title="T") == ("skipped", "no_prose")


def test_04a_gate_combine_order():
    ok, flag, skip = ("ok", None), ("flagged", "no_prose"), ("skipped", "empty")
    assert gates.combine(skip, ok) == skip
    assert gates.combine(ok, skip) == skip
    assert gates.combine(ok, flag) == flag
    assert gates.combine(ok, None) == ok


# --- chunking (PayCore measured: min 400 / max 600 tokens, no overlap; K-04a-0002 S2) ---

SETTINGS = ChunkSettings(min_tokens=400, max_tokens=600)


def test_04a_chunk_settings_defaults_are_measured_values():
    assert ChunkSettings.from_kb(chunk_size=400) == SETTINGS
    assert chunking.TOKENS_PER_WORD == 1.6 and chunking.CHARS_PER_TOKEN == 6


def test_04a_approx_tokens_floor_on_length():
    assert approx_tokens("bir iki üç") == 4
    assert approx_tokens("x" * 6000) == 1000  # no spaces: counted by length


def test_04a_11a_breadcrumb_prefixes_embedded_text():
    body = "# Madde 10 Fesih\n\n" + PROSE * 10 + "\n\n## 10.1 Bildirim\n\n" + PROSE * 10
    chunks = chunk_markdown(body, breadcrumb="Sözleşmeler › SZL-2024-011", settings=SETTINGS)
    assert chunks
    for chunk in chunks:
        assert chunk.text.startswith(chunk.breadcrumb + "\n\n")
        assert chunk.breadcrumb.startswith("Sözleşmeler › SZL-2024-011")
        assert chunk.text == f"{chunk.breadcrumb}\n\n{chunk.body}"
    assert any("Madde 10 Fesih" in c.breadcrumb for c in chunks)


def test_04a_9e_no_chunk_exceeds_char_ceiling():
    ceiling = SETTINGS.max_tokens * chunking.CHARS_PER_TOKEN
    shapes = [
        "a" * 50_000,  # one huge word
        ("veri;" * 5000),  # no spaces, no sentence end
        PROSE * 400,  # one huge paragraph
        "\n".join(["satır " * 30] * 500),  # many lines, no blank line
    ]
    for body in shapes:
        for chunk in chunk_markdown(body, breadcrumb="KB › Doc", settings=SETTINGS):
            assert len(chunk.body) <= ceiling, (len(chunk.body), body[:20])
            assert approx_tokens(chunk.body) <= SETTINGS.max_tokens


def test_04a_chunks_pack_to_the_minimum():
    sections = "\n\n".join(f"## Bölüm {i}\n\n{PROSE}" for i in range(20))
    chunks = chunk_markdown(sections, breadcrumb="KB › Doc", settings=SETTINGS)
    # Greedy packing: every chunk but the last reaches the minimum (PayCore measurement).
    assert all(approx_tokens(c.body) >= SETTINGS.min_tokens for c in chunks[:-1])
    assert all(c.breadcrumb.count("Bölüm") <= 3 for c in chunks)  # at most three headings named


def test_04a_chunk_page_markers_set_page():
    body = "<!-- page: 1 -->\n" + PROSE * 8 + "\n\n<!-- page: 2 -->\n" + PROSE * 8
    chunks = chunk_markdown(body, breadcrumb="KB › Doc", settings=SETTINGS)
    assert chunks[0].page == 1
    assert "<!-- page" not in chunks[0].body
