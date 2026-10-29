"""The one result every converter returns. A failure is a status with a reason, never an
empty string that looks like a document."""

from dataclasses import dataclass, field

CONVERTED = "converted"
SKIPPED_EMPTY = "skipped_empty"
ERROR = "error"
TIMEOUT = "timeout"


@dataclass
class ConversionResult:
    text_md: str
    method: str
    status: str = CONVERTED
    warnings: list[str] = field(default_factory=list)
    page_count: int | None = None
    # Stable machine code for failed results, e.g. encoding_undecodable, docling_failed.
    error_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == CONVERTED


def failed(method: str, code: str, message: str) -> ConversionResult:
    return ConversionResult("", method, status=ERROR, warnings=[message], error_code=code)


def empty(text: str, method: str, warnings: list[str] | None = None) -> ConversionResult:
    return ConversionResult(text, method, status=SKIPPED_EMPTY, warnings=warnings or [])


# Shorter than this a conversion produced nothing a reader could use (PayCore: 20 characters).
MIN_TEXT_CHARS = 20
