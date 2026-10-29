"""A converter for tests that runs without model weights (DRIFT-85).

Markdown goes through Docling in the product (docs/bilgi-tabani.md), and Docling needs its
layout weights, which a clean `model_cache` does not have. Tests that are about the pipeline
after conversion (gates, chunking, ACL, publication) read a Markdown upload as it is; formats the
product converts with the standard library (plain text, e-mail, MHTML, diagrams) and the
explicit skips use the real converters. A format that needs weights fails the test loudly: such
a test belongs under the `models` marker, which runs the real Docling path.
"""

from pathlib import Path

from ffcore.core.config import Settings
from ffcore.knowledge import ingest
from ffcore.knowledge.convert import router
from ffcore.knowledge.convert.types import ConversionResult

WEIGHTLESS = frozenset({"plaintext", "email_eml", "email_msg", "mhtml", "diagram"})


def convert_without_weights(path: Path, filename: str, settings: Settings) -> ConversionResult:
    handler = router.sniff(path, filename)
    if handler == "office" and path.suffix.lower() == ".md":
        return ConversionResult(path.read_text(encoding="utf-8"), "test-markdown-as-is")
    if handler in WEIGHTLESS or handler.startswith("skip_"):
        return ingest.convert_inline(path, filename, settings)
    raise AssertionError(
        f"{filename}: the {handler} converter needs model weights; mark the test `models`"
    )
