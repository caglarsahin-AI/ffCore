"""PDF: which tool reads it, in order of how much structure it keeps (brief 04 D2).

    Docling → pymupdf4llm → PyMuPDF text layer → PaddleOCR (only without a text layer)

Adapted from PayCore `convert/pdf.py` with its measured limits: a text layer of at least
3 × 40 characters means "not a scan"; text PDFs over 150 pages skip Docling (1-3 s per page);
a result under 40 characters falls to the next tool. Rasterizing a text-layer PDF into OCR is
the failure this order exists to prevent (PayCore: four manuals held every worker nine hours).
"""

import importlib.metadata
from pathlib import Path

from ffcore.knowledge.convert import office
from ffcore.knowledge.convert.ocr import ocr_pdf
from ffcore.knowledge.convert.types import ConversionResult

OCR_MIN_CHARS = 40
DOCLING_MAX_PAGES = 150


def native_chars(path: Path) -> int:
    import fitz

    with fitz.open(path) as doc:
        return sum(len((page.get_text("text") or "").strip()) for page in doc)


def page_count(path: Path) -> int:
    import fitz

    with fitz.open(path) as doc:
        return len(doc)


def route(path: Path) -> str:
    return "text_layer" if native_chars(path) >= OCR_MIN_CHARS * 3 else "ocr"


def _markdown(path: Path) -> tuple[str, str] | None:
    import pymupdf4llm

    try:
        chunks = pymupdf4llm.to_markdown(str(path), page_chunks=True, show_progress=False)
    except Exception:  # noqa: BLE001 - the plain text layer is the next tool
        return None
    pages = []
    for index, chunk in enumerate(chunks, start=1):
        text = str(chunk.get("text") or "").strip()
        number = (chunk.get("metadata") or {}).get("page", index)
        pages.append(f"<!-- page: {number} -->\n\n{text}\n")
    return "\n".join(pages).strip(), f"pymupdf4llm@{importlib.metadata.version('pymupdf4llm')}"


def _text_layer(path: Path) -> str:
    import fitz

    with fitz.open(path) as doc:
        return "\n".join(
            f"<!-- page: {i + 1} -->\n\n{(page.get_text('text') or '').strip()}\n"
            for i, page in enumerate(doc)
        ).strip()


def convert_pdf(path: Path) -> ConversionResult:
    if route(path) == "ocr":
        return ocr_pdf(path)
    pages = page_count(path)
    warnings: list[str] = []
    if pages <= DOCLING_MAX_PAGES:
        docling = office.convert_with_docling(path)
        if docling.ok and len(docling.text_md) >= OCR_MIN_CHARS:
            docling.page_count = pages
            return docling
        warnings.append(f"docling: {docling.error_code or docling.status}")
    else:
        warnings.append(f"docling skipped: {pages} pages > {DOCLING_MAX_PAGES}")
    markdown = _markdown(path)
    text, method = markdown if markdown else (_text_layer(path), "pymupdf-text-layer")
    if len(text) >= OCR_MIN_CHARS:
        return ConversionResult(text, method, warnings=warnings, page_count=pages)
    # A text layer this thin after every tool: the pages are images after all.
    return ocr_pdf(path)
