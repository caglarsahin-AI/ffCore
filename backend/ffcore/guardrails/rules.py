"""Rule types of 08-lite: `secrets` (vendor patterns + entropy) and `tool_args` (regex on tool
arguments). `pii` lives in the engine because it combines recognizers with a PII policy."""

import fnmatch
import json
import math
import re
from collections import Counter

from ffcore.guardrails.findings import Finding
from ffcore.guardrails.recognizers.regex import resolve_overlaps
from ffcore.guardrails.schemas import ToolArgsParams

ENTROPY_MIN_BITS = 3.5
ENTROPY_MIN_CHARS = 24

_VENDOR = (
    ("API_TOKEN", r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}", "vendor key pattern (sk-)"),
    ("API_TOKEN", r"\bAKIA[0-9A-Z]{16}\b", "vendor key pattern (AWS access key)"),
    ("API_TOKEN", r"\bgh[pousr]_[A-Za-z0-9]{36}\b", "vendor key pattern (GitHub token)"),
    ("API_TOKEN", r"\bxox[abprs]-[A-Za-z0-9-]{10,}", "vendor key pattern (Slack token)"),
    (
        "API_TOKEN",
        r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
        "JSON web token",
    ),
    ("API_TOKEN", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----", "private key block"),
    # 32+ hex with letters and digits: below the entropy floor (hex tops out near 4 bits/char),
    # so it gets its own pattern (K-SEN-0032).
    (
        "API_TOKEN",
        r"\b(?=[0-9a-fA-F]*[a-fA-F])(?=[0-9a-fA-F]*[0-9])[0-9a-fA-F]{32,}\b",
        "hex secret (32+ characters)",
    ),
    (
        "PASSWORD",
        r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp)://[^\s:@/]+:[^\s@/]+@",
        "connection string with password",
    ),
)
_VENDOR_RE = [(cat, re.compile(pat), ev) for cat, pat, ev in _VENDOR]
# "password: X", "şifre X", "parola=X": the value after the keyword.
_ASSIGNMENT = re.compile(
    r"(?i)\b(?:password|passwd|pwd|şifre(?:m|si|niz)?|parola(?:m|sı)?)\b\s*(?:[:=]|is)?\s*"
    r"(?P<value>[^\s,;]{6,})"
)
_TOKEN = re.compile(r"[A-Za-z0-9_\-+/=]{" + str(ENTROPY_MIN_CHARS) + ",}")
_UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")


_SEGMENTS = re.compile(r"[-_]")
_VOWELS = set("aeiouyAEIOUY")
_CONSONANT_RUN = re.compile(r"[^aeiouyAEIOUY0-9]{4,}")
# Words have about a third or more vowels (Turkish and English); random letters about a fifth.
# Measured: words 0.36-0.57, random lowercase 0.00-0.17 (08 review r1). Entropy does not
# separate them at this length (words 2.5-3.4 bits/char, random 2.5-3.4).
WORD_MIN_VOWEL_SHARE = 0.25
TAG_MAX_CHARS = 6  # upper-case codes: SZL, PRSIM, HBYS


def _is_plain_segment(part: str) -> bool:
    if part.isdigit() or len(part) <= 3:
        return True
    if not part.isalpha():
        return False  # letters and digits mixed in a long segment: token-like
    if part.isupper() and len(part) <= TAG_MAX_CHARS:
        return True
    if not (part.islower() or part.isupper()):
        return False  # mixed case inside a segment: token-like
    vowels = sum(ch in _VOWELS for ch in part) / len(part)
    return vowels >= WORD_MIN_VOWEL_SHARE and not _CONSONANT_RUN.search(part)


def is_plain_identifier(value: str) -> bool:
    """A name built from plain words and numbers (`SZL-2025-003_temizlik-hizmet`, a document
    name in every SOURCES block): every `-`/`_` segment is digits, a tag of at most 3 characters
    (`p4`, `v2`), an upper-case code of at most 6 letters (`PRSIM`), or a word: one case, at
    least WORD_MIN_VOWEL_SHARE vowels and no run of 4 consonants. One segment that is none of
    these (random letters, letters and digits mixed) keeps the whole value under the entropy
    check (plan/18 F4 finding; 08 review r1: separated random lowercase stays a secret)."""
    parts = [p for p in _SEGMENTS.split(value) if p]
    return len(parts) > 1 and all(_is_plain_segment(p) for p in parts)


def shannon_bits(value: str) -> float:
    counts = Counter(value)
    return -sum(n / len(value) * math.log2(n / len(value)) for n in counts.values())


def find_secrets(text: str) -> list[Finding]:
    hits = []
    for category, pattern, evidence in _VENDOR_RE:
        for m in pattern.finditer(text):
            hits.append(Finding(category, m.start(), m.end(), 0.95, evidence, m.group(0)))
    for m in _ASSIGNMENT.finditer(text):
        start, end = m.span("value")
        hits.append(Finding("PASSWORD", start, end, 0.9, "password keyword", m.group("value")))
    for m in _TOKEN.finditer(text):
        value = m.group(0)
        if (
            _UUID.fullmatch(value)
            or value.isdigit()
            or value.isalpha()
            or is_plain_identifier(value)
        ):
            continue
        bits = shannon_bits(value)
        if bits >= ENTROPY_MIN_BITS:
            hits.append(
                Finding(
                    "API_TOKEN",
                    m.start(),
                    m.end(),
                    0.8,
                    f"high entropy {bits:.1f} bits/char",
                    value,
                )
            )
    return resolve_overlaps(hits)


class ToolArgumentsNotObject(ValueError):
    """`args` was configured but the tool arguments are not a JSON object."""


def find_tool_arg_violations(text: str, params: dict, tool: str | None) -> list[Finding]:
    spec = ToolArgsParams.model_validate(params)
    if tool is None or not any(fnmatch.fnmatchcase(tool, name) for name in spec.tools):
        return []
    spans: list[tuple[int, str]] = []
    if spec.args is None:
        spans.append((0, text))
    else:
        try:
            arguments = json.loads(text)
        except json.JSONDecodeError:
            arguments = None
        if not isinstance(arguments, dict):
            raise ToolArgumentsNotObject("tool arguments are not a JSON object")
        # Offsets refer to the argument value, not the JSON text; the event shows which argument.
        spans.extend((0, str(arguments[name])) for name in spec.args if name in arguments)
    hits = []
    for i, pattern in enumerate(spec.patterns):
        compiled = re.compile(pattern)
        for offset, value in spans:
            for m in compiled.finditer(value):
                hits.append(
                    Finding(
                        f"tool_args:{i}",
                        offset + m.start(),
                        offset + m.end(),
                        1.0,
                        f"pattern {i} matched in tool {tool}",
                        m.group(0),
                    )
                )
    return hits
