"""Format cleanup: the one normalizer layer that is always on (brief 04 K1, layer a).

Silver text and every query pass the same function, and both record NORMALIZER_CONFIG_ID. The
Turkish correction layer (TEXT_NORMALIZE_TR) is 04b and off by default; this module never
changes words. Adapted from PayCore `ingest/normalize.clean_markdown` (HTML tags limited to real
HTML so `List<string>` survives, entities, literal \\n, double spaces, fenced code untouched)
and the deterministic part of `turkish.fix_unicode` (NFC, invisible characters). PayCore also
folds circumflexes (kâr → kar) there; that changes words, so it is not part of format cleanup.
"""

import re
import unicodedata
from html import unescape

NORMALIZER_CONFIG_ID = "format-v1"

_HTML_NAMES = (
    "a|abbr|b|blockquote|body|br|caption|code|col|colgroup|dd|div|dl|dt|em|figure|figcaption|"
    "font|form|h[1-6]|head|hr|html|i|iframe|img|input|label|li|link|meta|ol|option|p|pre|s|"
    "script|section|select|small|span|strike|strong|style|sub|sup|table|tbody|td|textarea|"
    "tfoot|th|thead|time|title|tr|u|ul"
)
_TAG = re.compile(rf"</?(?:{_HTML_NAMES})(?:\s[^>]*)?/?>", re.I)
_BR = re.compile(r"<br\s*/?>", re.I)
# A closing cell becomes a space so neighbouring cells do not glue together.
_CELL = re.compile(r"</(td|th)\s*>", re.I)
_LITERAL_NL = re.compile(r"\\r\\n|\\n|\\r")
_SPACES = re.compile(r"[ \t ]{2,}")
_SPACE_BEFORE_NL = re.compile(r"[ \t ]+\n")
_BLANK_RUNS = re.compile(r"\n{3,}")
_FENCE = re.compile(r"(```.*?```|~~~.*?~~~)", re.S)
_INVISIBLE = re.compile("[​‌‍⁠﻿­]")


def fix_unicode(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _INVISIBLE.sub("", text)
    # NFC has no single character for i + U+0307 (what str.lower("İ") leaves behind).
    return text.replace("i̇", "i")


def _clean_markup(part: str) -> str:
    part = _BR.sub("\n", part)
    part = _CELL.sub(" ", part)
    part = _TAG.sub(" ", part)
    part = unescape(part)
    part = _LITERAL_NL.sub("\n", part)
    part = _SPACES.sub(" ", part)
    return _SPACE_BEFORE_NL.sub("\n", part)


def clean_markdown(text: str) -> str:
    """Silver write boundary and query entry. Fenced code blocks are left exactly as they are."""
    if not text:
        return ""
    parts = _FENCE.split(fix_unicode(text))
    for index, part in enumerate(parts):
        if index % 2:  # odd indexes are the fenced blocks
            continue
        parts[index] = _BLANK_RUNS.sub("\n\n", _clean_markup(part))
    return "".join(parts).strip()


def normalize_query(query: str) -> str:
    """The same configuration as silver (K1): a query and a document must meet in one form."""
    return clean_markdown(query)
