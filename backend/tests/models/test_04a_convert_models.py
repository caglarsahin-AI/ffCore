"""04a slice 3 with real converter weights (Docling layout/table models, PaddleOCR `tr`).

make test-models (RUN_MODEL_TESTS=1); the weights come from the model_cache volume.
"""

import time
from pathlib import Path

import pytest

from ffcore.knowledge.convert import pipeline
from ffcore.knowledge.convert.types import CONVERTED

pytestmark = pytest.mark.models

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples" / "contracts"


def _text_pdf(path: Path, pages: int) -> Path:
    import fitz

    doc = fitz.open()
    for number in range(pages):
        page = doc.new_page()
        page.insert_text((72, 72), f"Madde {number + 1}. Bildirim suresi otuz gundur.")
        page.insert_text((72, 100), "Taraflar bu maddeye uygun olarak yazili bildirim yapar.")
    doc.save(path)
    doc.close()
    return path


def _scanned_pdf(path: Path, text: str) -> Path:
    """A page that is only an image of text: no text layer, so it must go to OCR."""
    import fitz

    source = fitz.open()
    page = source.new_page()
    page.insert_text((72, 120), text, fontsize=28)
    pixmap = page.get_pixmap(dpi=200)
    scan = fitz.open()
    scan_page = scan.new_page(width=page.rect.width, height=page.rect.height)
    scan_page.insert_image(scan_page.rect, pixmap=pixmap)
    scan.save(path)
    return path


def test_04a_9c_fifty_page_text_pdf_never_reaches_ocr(tmp_path):
    started = time.time()
    result = pipeline.convert_one(_text_pdf(tmp_path / "elli.pdf", 50), time.time() + 600)
    assert result.status == CONVERTED, result.warnings
    assert not result.method.startswith("paddle"), result.method
    assert result.page_count == 50
    print(f"50-page text PDF: {result.method} in {time.time() - started:.1f} s")


def test_04a_scanned_pdf_goes_to_paddle_ocr(tmp_path):
    result = pipeline.convert_one(
        _scanned_pdf(tmp_path / "tarama.pdf", "FESIH BILDIRIM SURESI"), time.time() + 600
    )
    assert result.status == CONVERTED, result.warnings
    assert result.method == "paddle_tr"
    assert "FESIH" in result.text_md.upper()


@pytest.mark.parametrize(
    "name", ["SZL-2024-011_cihaz-bakim.pdf", "SZL-2025-003_temizlik-hizmet.docx"]
)
def test_04a_13a_samples_convert_with_docling(name):
    result = pipeline.convert_one(SAMPLES / name, time.time() + 600)
    assert result.status == CONVERTED, result.warnings
    assert result.method.startswith("docling@"), result.method
    assert "Madde" in result.text_md and "ş" in result.text_md


def test_04a_chunks_fit_real_tokenizer_limits():
    """K-04a-0010: no chunk body exceeds max_tokens in bge-m3's own tokens, and the reranker
    pair (query + breadcrumb + body) fits its 1024-token limit. Prints the speed of both
    counters for the PR."""
    from ffcore.core.config import Settings
    from ffcore.knowledge.chunking import ChunkSettings, approx_tokens, chunk_markdown
    from ffcore.knowledge.embed import token_counter
    from ffcore.knowledge.normalize import clean_markdown
    from ffcore.knowledge.rerank import MAX_LENGTH
    from tests.dummy import SETTINGS_03A

    settings = Settings(
        deploy_profile="airgap",
        offline=False,
        service_token="dummy-not-secret-service-token-0123456789",
        obo_jwt_secret="dummy-not-secret-obo-jwt-secret-0123456789",
        **SETTINGS_03A,
    )
    count = token_counter(settings)
    text = clean_markdown(
        pipeline.convert_one(SAMPLES / "SZL-2024-011_cihaz-bakim.pdf", time.time() + 600).text_md
    )
    timings = {}
    for name, counter in (("estimate", approx_tokens), ("bge-m3 tokenizer", count)):
        started = time.time()
        chunks = chunk_markdown(
            text,
            breadcrumb="Sözleşmeler › SZL-2024-011",
            settings=ChunkSettings.from_kb(400, 0, counter),
        )
        timings[name] = (time.time() - started, len(chunks))
    print(f"\nchunking timings (s, chunks): {timings}")
    for chunk in chunks:
        assert count(chunk.body) <= 600, (count(chunk.body), chunk.body[:60])
        assert count("fesih bildirim süresi " + chunk.text) + 4 <= MAX_LENGTH
    fesih = [c for c in chunks if "10.1" in c.body]
    assert fesih and fesih[0].body.startswith("Madde")
