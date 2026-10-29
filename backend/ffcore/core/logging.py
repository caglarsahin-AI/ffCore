"""The one log configuration of FFCore processes (FOLLOWUP-49, 02 S4).

Standard library logging: every module logs through `logging.getLogger("ffcore.<area>")`. Here
the root handler gets a ScrubFilter that removes secret values and credential patterns from the
rendered message and from exception text, and the same filter goes on uvicorn's own handlers.
Third-party HTTP and telemetry loggers are held at WARNING: at DEBUG httpcore logs response
header values (B-01-0021).

The filter is a safety net, not the rule: code still never logs untrusted upstream text or a
credential in the first place (01 r1/r2).
"""

import logging
import re
import sys
from collections.abc import Iterable
from typing import IO

from pydantic import SecretStr

from ffcore.core.config import Settings

MASK = "***"
QUIET_LOGGERS = (
    "httpcore",
    "httpcore2",
    "httpx",
    "httpx2",
    "urllib3",
    "requests",
    "langfuse",
    "opentelemetry",
    "hpack",
)
FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"

# Credential shapes, whatever their value: Bearer tokens, sk-/pk- keys, key=value pairs with a
# secret-like key, and the password part of a URL.
_PATTERNS = (
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+"), r"\1 " + MASK),
    (re.compile(r"\b(?:sk|pk)-[A-Za-z0-9_-]{6,}"), MASK),
    (
        re.compile(
            r"(?i)([\"']?\b(?:api[_-]?key|password|passwd|secret|token|authorization|"
            r"x-api-key|cookie|set-cookie)[\"']?\s*[=:]\s*[\"']?)([^\s\"',;}&]+)"
        ),
        r"\1" + MASK,
    ),
    (re.compile(r"(://[^/\s:@]*:)([^@\s/]+)(@)"), r"\1" + MASK + r"\3"),
)


def scrub(text: str, secrets: Iterable[str]) -> str:
    for value in secrets:
        if value:
            text = text.replace(value, MASK)
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def secret_values(settings: Settings) -> list[str]:
    """Every SecretStr value of the settings, longest first (a key inside a URL goes whole)."""
    values = []
    for name in type(settings).model_fields:
        value = getattr(settings, name, None)
        if isinstance(value, SecretStr) and len(value.get_secret_value()) >= 6:
            values.append(value.get_secret_value())
    return sorted(set(values), key=len, reverse=True)


_PLAIN = (str, int, float, bool, type(None))


class ScrubFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(secrets)

    def filter(self, record: logging.LogRecord) -> bool:
        # A clean record keeps msg and args: formatters such as uvicorn's AccessFormatter unpack
        # record.args. A dirty one keeps its shape if scrubbing each string argument is enough;
        # otherwise (secret split across msg and args, or inside an object) the rendered text
        # is scrubbed and replaces both.
        rendered = record.getMessage()
        clean = scrub(rendered, self._secrets)
        if clean != rendered:
            args = record.args
            shaped = None
            if isinstance(args, tuple) and all(isinstance(a, _PLAIN) for a in args):
                shaped = tuple(scrub(a, self._secrets) if isinstance(a, str) else a for a in args)
                text = str(record.msg) % shaped
                if scrub(text, self._secrets) != text:
                    shaped = None
            if shaped is None:
                record.msg, record.args = clean, None
            else:
                record.args = shaped
        if record.exc_info:
            text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = scrub(text, self._secrets)
            record.exc_info = None
        if record.stack_info:
            record.stack_info = scrub(record.stack_info, self._secrets)
        return True


def configure_logging(
    settings: Settings, level: str | None = None, stream: IO[str] | None = None
) -> None:
    """Idempotent: replaces the root handler, re-filters uvicorn's handlers."""
    level = (level or settings.log_level).upper()
    scrubber = ScrubFilter(secret_values(settings))
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(scrubber)
    root = logging.getLogger()
    for old in list(root.handlers):
        if getattr(old, "_ffcore", False):
            root.removeHandler(old)
    handler._ffcore = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)
    for name in QUIET_LOGGERS:
        logging.getLogger(name).setLevel(
            max(logging.WARNING, logging.getLevelNamesMapping()[level])
        )
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        for uvicorn_handler in logging.getLogger(name).handlers:
            for old in [f for f in uvicorn_handler.filters if isinstance(f, ScrubFilter)]:
                uvicorn_handler.removeFilter(old)
            uvicorn_handler.addFilter(scrubber)
