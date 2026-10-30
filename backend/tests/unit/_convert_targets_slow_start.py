"""Worker pool test target whose import is slow, like a converter loading its libraries.

Imported only in a spawned worker (never at collection: the name has no `test_` prefix). The
delay comes from the environment the worker inherits, so one module serves every case."""

import os
import time
from pathlib import Path

from ffcore.knowledge.convert.types import ConversionResult

time.sleep(float(os.environ.get("FFCORE_TEST_START_DELAY", "0")))


def target(path: Path, deadline: float) -> ConversionResult:
    return ConversionResult(path.stem, "test")
