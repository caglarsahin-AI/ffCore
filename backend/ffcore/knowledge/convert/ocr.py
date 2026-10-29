"""PaddleOCR `tr` for scanned PDFs only (PLAN 2d, DRIFT-60; pdf.py decides what is a scan).

Adapted from PayCore `convert/ocr.py`: pages rendered at 150 dpi, at most OCR_PDF_MAX_PAGES (200)
pages with the truncation stated in the text and the warnings, boxes put back into reading order
by a 12 px line band, one PaddleOCR instance per worker thread, loading serialized.
"""

import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from ffcore.knowledge.convert.types import MIN_TEXT_CHARS, ConversionResult, empty, failed
from ffcore.knowledge.models import ModelMissing

DPI = 150
LINE_BAND_PX = 12
METHOD = "paddle_tr"

_local = threading.local()
_load_lock = threading.Lock()


def max_pages() -> int:
    return int(os.environ.get("OCR_PDF_MAX_PAGES", "200"))


def _paddle() -> Any:
    cached = getattr(_local, "paddle", None)
    if cached is not None:
        return cached
    from ffcore.knowledge.models import paddle_dirs

    # Explicit directories in the model cache: PaddleOCR's default (~/.paddleocr) downloads on
    # first use. Missing ones are ModelMissing before PaddleOCR is constructed (r1 MAJOR-6).
    dirs = paddle_dirs()
    from paddleocr import PaddleOCR

    with _load_lock:
        engine = PaddleOCR(
            lang="tr", use_angle_cls=True, show_log=False, enable_mkldnn=True, **dirs
        )
    _local.paddle = engine
    return engine


def _reading_order(items: list[tuple[float, float, str]]) -> str:
    rows = sorted(items, key=lambda r: (round(r[1] / LINE_BAND_PX), r[0]))
    return "\n".join(text for _, _, text in rows)


def _page_text(engine: Any, image: str) -> str:
    items = []
    for block in engine.ocr(image) or []:
        for line in block or []:
            box, (text, _confidence) = line[0], line[1]
            items.append((float(box[0][0]), float(box[0][1]), str(text)))
    return _reading_order(items)


def ocr_pdf(path: Path) -> ConversionResult:
    import fitz

    try:
        engine = _paddle()
    except ModelMissing as exc:
        return failed(METHOD, exc.code, str(exc))
    except Exception as exc:  # noqa: BLE001 - e.g. weights missing offline: a recorded error
        return failed(METHOD, "ocr_unavailable", str(exc)[:500])
    limit = max_pages()
    pages, warnings = [], []
    with fitz.open(path) as doc, tempfile.TemporaryDirectory(prefix="ocr_") as tmp:
        total = len(doc)
        count = min(total, limit) if limit > 0 else total
        matrix = fitz.Matrix(DPI / 72.0, DPI / 72.0)
        for index in range(count):
            image = Path(tmp) / f"page_{index + 1:04d}.png"
            doc.load_page(index).get_pixmap(matrix=matrix, alpha=False).save(str(image))
            pages.append(f"<!-- page: {index + 1} -->\n\n{_page_text(engine, str(image))}\n")
    if count < total:
        warnings.append(f"ocr truncated at {count} of {total} pages")
        pages.append(f"<!-- truncated: {total - count} more pages not OCR'd -->")
    body = "\n".join(pages).strip()
    if len(body) < MIN_TEXT_CHARS:
        return empty(body, METHOD, warnings)
    return ConversionResult(body, METHOD, warnings=warnings, page_count=total)
