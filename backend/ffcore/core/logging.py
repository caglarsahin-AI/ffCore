"""The one log configuration of FFCore processes (FOLLOWUP-49, 02 S4, review r1).

Standard library logging: every module logs through `logging.getLogger("ffcore.<area>")`. Every
record is scrubbed where it is made (the log record factory), so no handler ever sees a raw one,
whenever and by whom it was installed: secret values, credential patterns and personal data
(08-lite's recognizers and mask) go out of the message, its arguments, exception and stack text.
Third-party HTTP and telemetry loggers are held at WARNING: at DEBUG httpcore logs response
header values (B-01-0021). The access line has no query string (AccessLogMiddleware).

Scrubbing is a safety net, not the rule: code still never logs untrusted upstream text or a
credential in the first place (01 r1/r2).
"""

import logging
import re
import sys
import time
from collections.abc import Callable, Iterable
from typing import IO, Any

from pydantic import SecretStr

from ffcore.core.config import Settings
from ffcore.guardrails.masking import mask_value
from ffcore.guardrails.recognizers.regex import recognize

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
    return _mask_personal(text)


def _mask_personal(text: str) -> str:
    """Personal data with 08-lite's built-in recognizers and its mask (no recognizer of our own;
    KARARLAR "Log'da kişi verisi")."""
    findings = recognize(text, context_boost=False)
    if not findings:
        return text
    parts, last = [], 0
    for finding in findings:
        parts += [text[last : finding.start], mask_value(finding.category, finding.value)]
        last = finding.end
    return "".join(parts) + text[last:]


def secret_values(settings: Settings) -> list[str]:
    """Every SecretStr value of the settings, longest first (a key inside a URL goes whole)."""
    values = []
    for name in type(settings).model_fields:
        value = getattr(settings, name, None)
        if isinstance(value, SecretStr) and len(value.get_secret_value()) >= 6:
            values.append(value.get_secret_value())
    return sorted(set(values), key=len, reverse=True)


_PLAIN = (str, int, float, bool, type(None))
# Attributes every LogRecord has; anything else on a record came from `extra=` (or a filter).
_STANDARD = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}
_MAX_DEPTH = 8
_FAILED = "log_scrub_failed"
_secrets: tuple[str, ...] = ()
_base_factory: Callable[..., logging.LogRecord] | None = None
_base_make_record: Callable[..., logging.LogRecord] | None = None
scrub_failures = 0
access_log = logging.getLogger("ffcore.access")


def scrub_record(record: logging.LogRecord, secrets: Iterable[str]) -> None:
    """Scrubs a record in place, message, arguments, exception, stack and `extra=` fields, and
    never raises (review r1 MAJOR-2): a record the scrubber cannot handle goes on as
    `log_scrub_failed` with a counter, with no raw message or extra value."""
    secrets = tuple(secrets)
    try:
        _scrub(record, secrets)
        _scrub_extras(record, secrets)
    except Exception as exc:  # noqa: BLE001 - replaced by a counted, content-free record
        _failed(record, exc)


def _failed(record: logging.LogRecord, exc: Exception) -> None:
    global scrub_failures
    scrub_failures += 1
    record.msg = (
        f"{_FAILED} logger={record.name} error={type(exc).__name__} failures={scrub_failures}"
    )
    record.args = None
    record.exc_info = record.exc_text = record.stack_info = None
    for key in [k for k in record.__dict__ if k not in _STANDARD]:
        record.__dict__[key] = _FAILED


def _scrub(record: logging.LogRecord, secrets: tuple[str, ...]) -> None:
    # A clean record keeps msg and args: formatters such as uvicorn's AccessFormatter unpack
    # record.args. A dirty one keeps its shape if scrubbing each string argument is enough;
    # otherwise (value split across msg and args, inside an object, no args) the rendered text
    # is scrubbed and replaces both.
    rendered = record.getMessage()
    clean = scrub(rendered, secrets)
    if clean != rendered:
        args = record.args
        shaped = None
        if args and isinstance(args, tuple) and all(isinstance(a, _PLAIN) for a in args):
            shaped = tuple(scrub(a, secrets) if isinstance(a, str) else a for a in args)
            try:
                text = str(record.msg) % shaped
            except (TypeError, ValueError):
                shaped = None
            else:
                if scrub(text, secrets) != text:
                    shaped = None
        if shaped is None:
            record.msg, record.args = clean, None
        else:
            record.args = shaped
    if record.exc_info:
        text = logging.Formatter().formatException(record.exc_info)
        record.exc_text = scrub(text, secrets)
        record.exc_info = None
    if record.stack_info:
        record.stack_info = scrub(record.stack_info, secrets)


def _scrub_extras(record: logging.LogRecord, secrets: tuple[str, ...]) -> None:
    for key in [k for k in record.__dict__ if k not in _STANDARD]:
        record.__dict__[key] = _scrub_value(record.__dict__[key], secrets, 0)


def _scrub_value(value: Any, secrets: tuple[str, ...], depth: int) -> Any:
    """Strings scrubbed; dicts, lists, tuples and sets walked (keys too); numbers kept; any
    other object, and anything deeper than _MAX_DEPTH, becomes its scrubbed text."""
    if isinstance(value, str):
        return scrub(value, secrets)
    if value is None or isinstance(value, bool | int | float):
        return value
    if depth < _MAX_DEPTH:
        if isinstance(value, dict):
            return {
                _scrub_value(k, secrets, depth + 1): _scrub_value(v, secrets, depth + 1)
                for k, v in value.items()
            }
        if isinstance(value, list | tuple | set | frozenset):
            items = [_scrub_value(v, secrets, depth + 1) for v in value]
            return items if isinstance(value, list) else tuple(items)
    return scrub(str(value), secrets)


def _scrubbed_record(*args: Any, **kwargs: Any) -> logging.LogRecord:
    record = _base_factory(*args, **kwargs)  # type: ignore[misc]
    scrub_record(record, _secrets)
    return record


def _make_record(self: logging.Logger, *args: Any, **kwargs: Any) -> logging.LogRecord:
    # Logger.makeRecord adds `extra=` fields after the record factory has run (review r2
    # MAJOR-1); they are scrubbed here, before any handler sees the record.
    record = _base_make_record(self, *args, **kwargs)  # type: ignore[misc]
    try:
        _scrub_extras(record, _secrets)
    except Exception as exc:  # noqa: BLE001 - replaced by a counted, content-free record
        _failed(record, exc)
    return record


def configure_logging(
    settings: Settings, level: str | None = None, stream: IO[str] | None = None
) -> None:
    """Idempotent. Records are scrubbed where they are made: the log record factory (message,
    arguments, exception) and Logger.makeRecord (the `extra=` fields it adds after the factory;
    review r2 MAJOR-1). Every handler sees only scrubbed records, whether it was installed
    before this call or after it (arq's CLI, uvicorn; review r1 MAJOR-1). A Logger subclass
    that overrides makeRecord itself is not covered; FFCore has none. The root gets one FFCore
    handler. uvicorn's access log is off: AccessLogMiddleware writes method, path, status and
    duration, no query string (KARARLAR "Log'da kişi verisi")."""
    global _secrets, _base_factory, _base_make_record
    level = (level or settings.log_level).upper()
    _secrets = tuple(secret_values(settings))
    if _base_factory is None:
        _base_factory = logging.getLogRecordFactory()
        logging.setLogRecordFactory(_scrubbed_record)
    if _base_make_record is None:
        _base_make_record = logging.Logger.makeRecord
        logging.Logger.makeRecord = _make_record  # type: ignore[method-assign]
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT))
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
    logging.getLogger("uvicorn.access").disabled = True


class AccessLogMiddleware:
    """One access line per HTTP request: method, path, status, duration. No query string, no
    headers, no client address (review r1 MAJOR-5)."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = [500]

        async def send_status(message: dict) -> None:
            if message["type"] == "http.response.start":
                status[0] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_status)
        finally:
            access_log.info(
                "access method=%s path=%s status=%d ms=%d",
                scope["method"],
                scope["path"],
                status[0],
                (time.perf_counter() - started) * 1000,
            )
