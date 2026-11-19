"""A converter for tests that runs without model weights (DRIFT-85).

Docling needs its layout weights, which a clean `model_cache` does not have. Formats the
product converts without weights (Markdown since 04b-2 FOLLOWUP-87, plain text, e-mail, MHTML,
diagrams) and the explicit skips use the real converters. A format that needs weights fails the
test loudly: such a test belongs under the `models` marker, which runs the real Docling path.
"""

from pathlib import Path

from ffcore.core.config import Settings
from ffcore.knowledge import ingest
from ffcore.knowledge.convert import router
from ffcore.knowledge.convert.types import ConversionResult

WEIGHTLESS = frozenset({"markdown", "plaintext", "email_eml", "email_msg", "mhtml", "diagram"})


def convert_without_weights(path: Path, filename: str, settings: Settings) -> ConversionResult:
    handler = router.sniff(path, filename)
    if handler in WEIGHTLESS or handler.startswith("skip_"):
        return ingest.convert_inline(path, filename, settings)
    raise AssertionError(
        f"{filename}: the {handler} converter needs model weights; mark the test `models`"
    )
