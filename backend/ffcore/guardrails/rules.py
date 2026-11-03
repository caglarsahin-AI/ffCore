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
# FOLLOWUP-106: a token shorter than ENTROPY_MIN_CHARS is a finding only when a credential word
# names it ("API_KEY=", "Authorization: Bearer", "token:", "the secret is"); at these lengths
# entropy does not separate keys from codes and names, the word does. Its value is checked like
# the long tokens' (no digits-only, no word, no plain identifier).
SHORT_TOKEN_MIN_CHARS = 13
_CREDENTIAL_WORD = (
    r"api[_-]?key|access[_-]?key|client[_-]?secret|secret[_-]?key|secret|token|authorization"
    r"|bearer|anahtar(?:ı|i)?"
)
_SHORT_TOKEN = re.compile(
    r"(?i)\b(?P<word>" + _CREDENTIAL_WORD + r")\b[\"']?\s*(?:[:=]|\bis\b)?\s*[\"']?"
    r"(?:(?:bearer|basic)\s+)?"
    r"(?P<value>[A-Za-z0-9_\-+/=]{"
    + str(SHORT_TOKEN_MIN_CHARS)
    + ","
    + str(ENTROPY_MIN_CHARS - 1)
    + r"})(?![A-Za-z0-9_\-+/=])"
)
_UUID = re.compile(r"[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}")


_SEGMENTS = re.compile(r"[-_]")
_VOWELS = set("aeiouy")
_CONSONANT_RUN = re.compile(r"[^aeiouy]{3,}")
_TAG = re.compile(r"[a-z]{1,3}[0-9]*|[a-z]{1,3}[0-9]+[a-z]?")  # v2, q3, p4, kdv, b, el
_CODE = re.compile(r"[A-Z]{2,6}")  # PRSIM, SZL, HBYS: plain only before a number segment
# Words have about a third or more vowels (Turkish and English); random letters about a fifth.
# Measured: words 0.36-0.57, random lowercase 0.00-0.17 (08 review r1). Entropy does not
# separate them at these lengths (both 2.5-3.4 bits/char). Case is normalized first, so the
# same test applies to upper-case segments, and a run of 3 consonants already ends a word
# (08 review r2: random 2-segment exemption 2 % -> 0.1 %).
WORD_MIN_VOWEL_SHARE = 0.3
# Letters that passed only as a tag or a code are unverified; this many of them, in three or
# more segments, make the value token-like whatever its shape (08 review r2, K-SEN-0043).
MAX_UNVERIFIED_LETTERS = 15


def _is_word(part: str) -> bool:
    low = part.lower()
    if not low.isalpha() or len(low) < 4 or not (part.islower() or part.isupper()):
        return False
    vowels = sum(ch in _VOWELS for ch in low) / len(low)
    return vowels >= WORD_MIN_VOWEL_SHARE and not _CONSONANT_RUN.search(low)


def is_plain_identifier(value: str) -> bool:
    """A name built from plain words and numbers (`SZL-2025-003_temizlik-hizmet`, a document
    name in every SOURCES block). Every `-`/`_` segment must be digits, a word (case-normalized:
    at least WORD_MIN_VOWEL_SHARE vowels, no run of 3 consonants), a short tag (`v2`, `q3`,
    `kdv`), or an upper-case code of 2-6 letters directly before a number segment
    (`PRSIM-1234`). With three or more segments, more than MAX_UNVERIFIED_LETTERS letters in
    tags and codes also end the exemption. Anything else (random letters of either case,
    letters and digits mixed) stays under the entropy check (plan/18 F4 finding; 08 review r1,
    r2)."""
    parts = [p for p in _SEGMENTS.split(value) if p]
    if len(parts) < 2:
        return False
    unverified = 0
    for index, part in enumerate(parts):
        following = parts[index + 1] if index + 1 < len(parts) else ""
        if part.isdigit() or _is_word(part):
            continue
        if _TAG.fullmatch(part.lower()) and (
            part.islower() or part.isupper() or not part.isalpha()
        ):
            unverified += sum(ch.isalpha() for ch in part)
        elif _CODE.fullmatch(part) and following.isdigit():
            unverified += len(part)
        else:
            return False
    return not (len(parts) >= 3 and unverified > MAX_UNVERIFIED_LETTERS)


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
    for m in _SHORT_TOKEN.finditer(text):
        value = m.group("value")
        if value.isdigit() or _is_word(value) or is_plain_identifier(value):
            continue
        start, end = m.span("value")
        word = m.group("word").lower()
        hits.append(
            Finding(
                "API_TOKEN", start, end, 0.85, f"credential word '{word}' before the value", value
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
