"""`convert_one(path, deadline)`: dispatch one file by its sniffed handler (worker target).

Every skip carries its reason in the status (`skipped_<reason>`), so the report counts it;
nothing is dropped silently (ARCH-06).
"""

from pathlib import Path

from ffcore.knowledge.convert import office, pdf, router, text_formats
from ffcore.knowledge.convert.types import ConversionResult

CONVERT_TARGET = "ffcore.knowledge.convert.pipeline:convert_one"

_HANDLERS = {
    "pdf": pdf.convert_pdf,
    "office": office.convert_with_docling,
    "mhtml": text_formats.convert_mhtml,
    "email_msg": text_formats.convert_msg,
    "email_eml": text_formats.convert_eml,
    "diagram": text_formats.convert_diagram,
    "plaintext": text_formats.convert_plaintext,
}

_SKIP_REASONS = {
    "skip_binary": "binary",
    "skip_scope": "out_of_scope",
    "skip_video": "video_disabled",
    "skip_libreoffice": "libreoffice_unavailable",
    "skip_unknown": "unknown_format",
}


def convert_one(path: Path, deadline: float, filename: str | None = None) -> ConversionResult:
    handler = router.sniff(path, filename)
    if handler in _SKIP_REASONS:
        return ConversionResult("", handler, status=f"skipped_{_SKIP_REASONS[handler]}")
    return _HANDLERS[handler](path)
