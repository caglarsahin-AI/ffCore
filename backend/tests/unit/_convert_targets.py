"""Worker pool test targets; importable by name in a spawned process."""

import time
from pathlib import Path

from ffcore.knowledge.convert.types import ConversionResult


def target(path: Path, deadline: float) -> ConversionResult:
    if path.read_text() == "sleep":
        time.sleep(600)
    return ConversionResult(path.stem, "test")
