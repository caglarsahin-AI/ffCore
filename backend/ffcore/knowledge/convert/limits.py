"""Expansion budgets checked before a converter opens a file (review r1 MAJOR-5).

A small upload must not turn into gigabytes in the converter: ZIP containers (docx, pptx, vsdx)
are refused on member count, total expanded size or per-member ratio from the central
directory, before Docling or the stdlib reader opens them (Python's zipfile never inflates a
member past its declared size, so the declared sizes bound the reading too). A draw.io payload
is inflated with a byte budget. A PDF is refused on page count or on a page whose render at the
OCR resolution would pass the pixel budget. Every refusal is a coded error result; the file's
content never goes into the message.

The values are chosen defaults, not PayCore measurements (PayCore had no such limits): the
samples' docx files expand 3.3-3.5x in total and at most 4.4x per member (measured 2026-10-29),
far below the ratio limit.
"""

import zipfile
import zlib
from pathlib import Path

from ffcore.knowledge.convert.types import ConversionResult, failed

ZIP_MAX_MEMBERS = 10_000
ZIP_MAX_EXPANDED_BYTES = 512 * 1024 * 1024
# Per member, only above ZIP_RATIO_MIN_BYTES: tiny XML parts compress far beyond 100x.
ZIP_MAX_RATIO = 100
ZIP_RATIO_MIN_BYTES = 1024 * 1024
DRAWIO_MAX_INFLATED_BYTES = 64 * 1024 * 1024
PDF_MAX_PAGES = 5_000
# ~A1 at 150 dpi (4967 x 7016 = 34.8 M px); ocr.DPI is the render resolution.
PDF_MAX_PAGE_PIXELS = 40_000_000
PDF_RENDER_DPI = 150


class LimitExceeded(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code


def check_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
    if len(members) > ZIP_MAX_MEMBERS:
        raise LimitExceeded("archive_too_many_members", f"{len(members)} > {ZIP_MAX_MEMBERS}")
    total = sum(m.file_size for m in members)
    if total > ZIP_MAX_EXPANDED_BYTES:
        raise LimitExceeded("archive_too_large", f"{total} > {ZIP_MAX_EXPANDED_BYTES} bytes")
    for member in members:
        if member.file_size >= ZIP_RATIO_MIN_BYTES:
            ratio = member.file_size / max(member.compress_size, 1)
            if ratio > ZIP_MAX_RATIO:
                raise LimitExceeded("archive_ratio", f"member expands {ratio:.0f}x")


def check_pdf(path: Path) -> None:
    import fitz

    with fitz.open(path) as doc:
        if len(doc) > PDF_MAX_PAGES:
            raise LimitExceeded("pdf_too_many_pages", f"{len(doc)} > {PDF_MAX_PAGES}")
        scale = PDF_RENDER_DPI / 72.0
        for index in range(len(doc)):
            rect = doc.load_page(index).rect
            pixels = int(rect.width * scale) * int(rect.height * scale)
            if pixels > PDF_MAX_PAGE_PIXELS:
                raise LimitExceeded(
                    "pdf_page_too_large", f"page {index + 1}: {pixels} > {PDF_MAX_PAGE_PIXELS} px"
                )


def inflate_raw(data: bytes, limit: int = DRAWIO_MAX_INFLATED_BYTES) -> bytes:
    """Raw deflate (draw.io) with a byte budget; zlib.error for data that is not deflate."""
    inflater = zlib.decompressobj(-15)
    out = inflater.decompress(data, limit)
    if inflater.unconsumed_tail:
        raise LimitExceeded("diagram_too_large", f"inflates past {limit} bytes")
    return out + inflater.flush()


def check(path: Path, handler: str) -> ConversionResult | None:
    """The coded refusal for `handler`'s input, or None when it is within the budgets."""
    try:
        if handler == "pdf":
            check_pdf(path)
        elif handler in ("office", "diagram") and zipfile.is_zipfile(path):
            check_zip(path)
    except LimitExceeded as exc:
        return failed("limits", exc.code, str(exc))
    return None
