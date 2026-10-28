"""Built-in regex recognizers (08-lite): TR national ID, TR phone, TR IBAN, e-mail, card.

Numbers with a check digit are accepted only when the check passes (TC algorithm, mod-97, Luhn).
A context word in the 30 characters before a hit raises its score (`context_boost`).
"""

import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from ffcore.guardrails.findings import Finding

CONTEXT_WINDOW = 30
CONTEXT_BONUS = 0.1


def tc_valid(value: str) -> bool:
    """11 digits, first not 0; digit 10 and 11 from the official check algorithm."""
    if len(value) != 11 or not value.isdigit() or value[0] == "0":
        return False
    d = [int(c) for c in value]
    tenth = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    return d[9] == tenth and d[10] == sum(d[:10]) % 10


def iban_valid(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"TR\d{24}", compact):
        return False
    rearranged = compact[4:] + compact[:4]
    number = "".join(str(int(c, 36)) for c in rearranged)
    return int(number) % 97 == 1


def luhn_valid(value: str) -> bool:
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_PHONE = re.compile(
    r"(?<![\d+])(?P<cc>\+90[\s.-]?|0[\s.-]?)?"
    r"(?:\((?P<pa>[2-5]\d{2})\)|(?P<a>[2-5]\d{2}))"
    r"(?P<s1>[\s.-]?)\d{3}(?P<s2>[\s.-]?)\d{2}(?P<s3>[\s.-]?)\d{2}(?!\d)"
)


def _phone_shape(match: re.Match) -> str | None:
    # A bare ten-digit run is too often a tax or order number: a phone needs a prefix (0, +90),
    # a parenthesised area code or separators between the groups.
    separators = sum(1 for name in ("s1", "s2", "s3") if match.group(name))
    if match.group("cc") or match.group("pa") or separators >= 2:
        return "phone pattern"
    return None


@dataclass(frozen=True)
class _Recognizer:
    category: str
    pattern: re.Pattern
    base_score: float
    check: Callable[[re.Match], str | None]
    context: tuple[str, ...]


def _checked(fn: Callable[[str], bool], evidence: str) -> Callable[[re.Match], str | None]:
    return lambda m: evidence if fn(m.group(0)) else None


RECOGNIZERS = (
    _Recognizer(
        "TR_IBAN",
        re.compile(r"(?<![A-Za-z0-9])TR\d{2}(?: ?\d{4}){5} ?\d{2}(?!\d)", re.IGNORECASE),
        0.95,
        _checked(iban_valid, "mod-97 valid"),
        ("iban", "hesap", "account"),
    ),
    _Recognizer(
        "EMAIL_ADDRESS",
        re.compile(r"(?<![\w.+-])[\w.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
        0.9,
        lambda m: "pattern match",
        ("e-posta", "eposta", "mail", "email"),
    ),
    _Recognizer(
        "TR_NATIONAL_ID",
        re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"),
        0.85,
        _checked(tc_valid, "checksum valid"),
        ("tc", "t.c.", "tckn", "kimlik", "national id", "identity"),
    ),
    _Recognizer(
        "CREDIT_CARD",
        re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)"),
        0.85,
        _checked(luhn_valid, "Luhn valid"),
        ("kart", "card", "kredi", "ekstre"),
    ),
    _Recognizer(
        "TR_PHONE",
        _PHONE,
        0.75,
        _phone_shape,
        ("tel", "telefon", "cep", "gsm", "phone", "ara", "numara", "irtibat"),
    ),
)
_BY_CATEGORY = {r.category: r for r in RECOGNIZERS}


def _fold(text: str) -> str:
    # Turkish dotted capital I lowercases to "i" + combining dot; drop the dot.
    return text.casefold().replace("i̇", "i")


def _context_word(text: str, start: int, words: tuple[str, ...]) -> str | None:
    window = _fold(text[max(0, start - CONTEXT_WINDOW) : start])
    for word in words:
        if re.search(r"(?<![\w])" + re.escape(word), window):
            return word
    return None


def resolve_overlaps(findings: Iterable[Finding]) -> list[Finding]:
    """Keep the strongest of overlapping hits (score, then length); return them by position."""
    kept: list[Finding] = []
    for finding in sorted(findings, key=lambda f: (-f.score, -(f.end - f.start), f.start)):
        if not any(finding.overlaps(k) for k in kept):
            kept.append(finding)
    return sorted(kept, key=lambda f: f.start)


def recognize(
    text: str, categories: Iterable[str] | None = None, *, context_boost: bool = True
) -> list[Finding]:
    """Regex findings in `text`, overlaps resolved. `categories` limits the recognizers."""
    selected = (
        RECOGNIZERS
        if categories is None
        else [_BY_CATEGORY[c] for c in categories if c in _BY_CATEGORY]
    )
    hits = []
    for rec in selected:
        for match in rec.pattern.finditer(text):
            evidence = rec.check(match)
            if evidence is None:
                continue
            score = rec.base_score
            word = _context_word(text, match.start(), rec.context) if context_boost else None
            if word is not None:
                score = min(1.0, score + CONTEXT_BONUS)
                evidence += f" · context word '{word}'"
            hits.append(
                Finding(rec.category, match.start(), match.end(), score, evidence, match.group(0))
            )
    return resolve_overlaps(hits)
