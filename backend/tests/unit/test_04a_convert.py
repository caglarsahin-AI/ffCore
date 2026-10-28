"""04a slice 3: conversion (brief 04 D2). Real libraries in the tools image; Docling and
PaddleOCR model runs are in tests/models (`-m models`)."""

import base64
import time
import zlib
from pathlib import Path

import pytest

from ffcore.knowledge.convert import encoding, pipeline, router
from ffcore.knowledge.convert.types import CONVERTED, ERROR, TIMEOUT
from ffcore.knowledge.convert.workers import BoundedPool, PersistentPool

TURKISH = "Fesih bildirim süresi doksan gündür; şartname ığdır ve öçü harflerini korur."


def _mhtml(html: str, utf16: bool) -> bytes:
    payload = ("﻿" + html).encode("utf-16-le") if utf16 else html.encode("utf-8")
    charset = "unicode" if utf16 else "utf-8"
    encoded = base64.encodebytes(payload).decode("ascii")
    image = base64.encodebytes(b"\x89PNG" + bytes(600)).decode("ascii")
    return (
        "MIME-Version: 1.0\r\n"
        'Content-Type: multipart/related; boundary="----=_NextPart_01"\r\n\r\n'
        "------=_NextPart_01\r\n"
        f'Content-Type: text/html; charset="{charset}"\r\n'
        "Content-Transfer-Encoding: base64\r\n\r\n"
        f"{encoded}\r\n"
        "------=_NextPart_01\r\n"
        "Content-Type: image/png\r\n"
        "Content-Transfer-Encoding: base64\r\n\r\n"
        f"{image}\r\n"
        "------=_NextPart_01--\r\n"
    ).encode("ascii")


# --- encoding ---


def test_04a_9b_cp1254_text_keeps_turkish_letters(tmp_path):
    path = tmp_path / "not.txt"
    path.write_bytes(("Başlık\n" + TURKISH + "\n").encode("cp1254"))
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == CONVERTED, result.warnings
    assert "şartname ığdır" in result.text_md and "�" not in result.text_md
    assert result.method == "plaintext"
    assert "encoding: cp1254" in result.warnings


def test_04a_9b_mixed_utf8_and_cp1254_lines():
    data = "satır şu\n".encode() + "satır ğı\n".encode("cp1254")
    text, label = encoding.decode_text(data)
    assert text == "satır şu\nsatır ğı\n" and label == "utf-8+cp1254"


def test_04a_9b_undecodable_bytes_fail_loud(tmp_path):
    path = tmp_path / "broken.txt"
    path.write_bytes(b"ok line\n\x81\x8d broken\n" + b"x" * 40)
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == ERROR and result.error_code == "encoding_undecodable"


# --- routing ---


@pytest.mark.parametrize(
    ("name", "content", "handler"),
    [
        ("a.pdf", b"%PDF-1.7 ...", "pdf"),
        ("noext", b"%PDF-1.4", "pdf"),
        ("a.docx", b"PK\x03\x04....", "office"),
        ("a.zip", b"PK\x03\x04", "skip_scope"),
        ("unknown.bin2", b"PK\x03\x04", "skip_scope"),
        ("a.exe", b"MZ", "skip_binary"),
        ("a.mp4", b"\x00\x00", "skip_video"),
        ("a.ppt", b"\xd0\xcf\x11\xe0", "skip_libreoffice"),
        ("a.doc", b"\xd0\xcf\x11\xe0", "skip_libreoffice"),
        ("flow", b'<mxfile host="x">', "diagram"),
        ("a.txt", b"hello", "plaintext"),
        ("a.weird", b"hello", "skip_unknown"),
    ],
)
def test_04a_sniff_by_bytes_then_extension(tmp_path, name, content, handler):
    path = tmp_path / name
    path.write_bytes(content)
    assert router.sniff(path) == handler


def test_04a_9a_mhtml_with_doc_extension_is_sniffed(tmp_path):
    path = tmp_path / "kilavuz.doc"
    path.write_bytes(_mhtml(f"<html><body><h1>Kılavuz</h1><p>{TURKISH}</p></body></html>", True))
    assert router.sniff(path) == "mhtml"


def test_04a_9a_mhtml_doc_yields_turkish_text_without_base64(tmp_path):
    html = f"<html><body><h1>Kılavuz</h1><p>{TURKISH}</p><p>{TURKISH}</p></body></html>"
    path = tmp_path / "kilavuz.doc"
    path.write_bytes(_mhtml(html, utf16=True))
    result = pipeline.convert_one(path, time.time() + 120)
    assert result.status == CONVERTED, result.warnings
    assert "şartname ığdır" in result.text_md
    assert "iVBOR" not in result.text_md and "AAAA" not in result.text_md  # no base64 left
    assert result.method.startswith("mhtml+")


# --- other text formats ---


def test_04a_eml_html_body_becomes_visible_text(tmp_path):
    path = tmp_path / "mail.eml"
    path.write_bytes(
        (
            "From: a@example.test\r\nSubject: Bakım\r\nMIME-Version: 1.0\r\n"
            'Content-Type: text/html; charset="utf-8"\r\n\r\n'
            f"<html><head><style>p{{color:red}}</style></head><body><p>{TURKISH}</p></body></html>"
        ).encode()
    )
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == CONVERTED
    assert (
        TURKISH in result.text_md and "<p>" not in result.text_md and "color" not in result.text_md
    )


def test_04a_drawio_labels(tmp_path):
    inner = '<mxGraphModel><root><mxCell value="Onay adımı"/><mxCell value="Fesih"/></root>'
    packed = base64.b64encode(zlib.compress(inner.encode(), 9)[2:-4]).decode()
    path = tmp_path / "akis.drawio"
    path.write_text(f'<mxfile><diagram name="p">{packed}</diagram></mxfile>', encoding="utf-8")
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == CONVERTED
    assert "- Onay adımı" in result.text_md and "- Fesih" in result.text_md


def test_04a_skip_handlers_carry_reasons(tmp_path):
    path = tmp_path / "eski.ppt"
    path.write_bytes(b"\xd0\xcf\x11\xe0" + bytes(100))
    result = pipeline.convert_one(path, time.time() + 60)
    assert result.status == "skipped_libreoffice_unavailable"


# --- PDF routing without models: text layer decides, never OCR for text PDFs ---


def _text_pdf(path: Path, pages: int) -> Path:
    import fitz

    doc = fitz.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Sayfa {number + 1}: Madde {number} bildirim suresi.")
    doc.save(path)
    doc.close()
    return path


def _blank_pdf(path: Path) -> Path:
    import fitz

    doc = fitz.open()
    doc.new_page()
    doc.save(path)
    doc.close()
    return path


def test_04a_9c_text_layer_pdf_routes_away_from_ocr(tmp_path):
    from ffcore.knowledge.convert import pdf

    assert pdf.route(_text_pdf(tmp_path / "metin.pdf", 50)) == "text_layer"
    assert pdf.route(_blank_pdf(tmp_path / "tarama.pdf")) == "ocr"


def test_04a_9c_text_pdf_fallback_chain_without_docling(tmp_path, monkeypatch):
    # Docling failing (e.g. no layout weights offline) falls back to pymupdf4llm, never to OCR.
    from ffcore.knowledge.convert import office, pdf
    from ffcore.knowledge.convert.types import failed

    monkeypatch.setattr(office, "convert_with_docling", lambda p: failed("docling", "x", "no"))
    monkeypatch.setattr(pdf, "ocr_pdf", lambda p: pytest.fail("a text PDF reached OCR"))
    result = pdf.convert_pdf(_text_pdf(tmp_path / "metin.pdf", 50))
    assert result.status == CONVERTED
    assert result.method.startswith("pymupdf4llm") and result.page_count == 50
    assert "<!-- page: 50 -->" in result.text_md


# --- worker pool: a stuck file is killed, the others go on (D2) ---


def test_04a_9d_timeout_kills_worker_and_continues(tmp_path):
    slow, fast = tmp_path / "slow.txt", tmp_path / "fast.txt"
    slow.write_text("sleep")
    fast.write_text("ok")
    results = {}
    pool = BoundedPool(size=1, timeout=2, name="t", target="tests.unit._convert_targets:target")
    started = time.time()
    pool.run(
        [slow, fast],
        on_start=lambda p: None,
        on_result=lambda p, r, s: results.__setitem__(p.name, r),
    )
    assert results["slow.txt"].status == TIMEOUT
    assert results["fast.txt"].status == CONVERTED and results["fast.txt"].text_md == "fast"
    assert time.time() - started < 30


def test_04a_persistent_pool_reuses_its_process_and_replaces_it_after_timeout(tmp_path):
    slow, fast1, fast2 = (tmp_path / n for n in ("slow.txt", "fast1.txt", "fast2.txt"))
    slow.write_text("sleep")
    fast1.write_text("ok")
    fast2.write_text("ok")
    pool = PersistentPool(timeout=2, name="p", target="tests.unit._convert_targets:target")
    try:
        assert pool.convert(fast1).text_md == "fast1"
        first = pool._worker.process.pid
        assert pool.convert(fast2).text_md == "fast2"
        assert pool._worker.process.pid == first  # same process, models loaded once
        assert pool.convert(slow).status == TIMEOUT
        assert pool._worker is None  # killed; the next file gets a fresh process
        assert pool.convert(fast1).status == CONVERTED
    finally:
        pool.close()
