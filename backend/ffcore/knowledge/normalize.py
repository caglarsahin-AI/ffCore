"""Format cleanup, always on (brief 04 K1, layer a), and the Turkish layer A behind
TEXT_NORMALIZE_TR (04b-2 D3, off by default).

Silver text and every query pass the same function, and both record `normalizer_config_id`:
`format-v1`, or `format-v1+tr-a1` with the Turkish layer. Layer A is PayCore's deterministic,
lexicon-free part: circumflexes are folded (kâr → kar, hâlâ → hala), in prose only; code and URLs
keep their exact form. PayCore's layers B-D (lexicon) did not pass its own error gate and are not
here (K-04B-0002 S3 A).

Format cleanup is adapted from PayCore `ingest/normalize.clean_markdown` (HTML tags limited to
real HTML so `List<string>` survives, entities, literal \\n, double spaces, fenced code
untouched) and the NFC/invisible-character part of `turkish.fix_unicode`. Folding changes words,
so it is the separate, switchable layer, never part of format cleanup.
"""

import re
import unicodedata
from html import unescape

# The format layer's id; with TEXT_NORMALIZE_TR the id is extended (normalizer_config_id).
NORMALIZER_CONFIG_ID = "format-v1"
TR_LAYER_ID = "tr-a1"
_CIRCUMFLEX = str.maketrans({"â": "a", "î": "i", "û": "u", "Â": "A", "Î": "İ", "Û": "U"})
# Inline code and URLs are content in their exact form (fenced blocks are split off first).
_EXACT = re.compile(r"`[^`\n]+`|\b(?:https?|ftp)://\S+|\bwww\.\S+", re.I)

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


def normalizer_config_id(settings) -> str:
    """The form silver and queries are in under these settings (K1)."""
    if settings.text_normalize_tr:
        return f"{NORMALIZER_CONFIG_ID}+{TR_LAYER_ID}"
    return NORMALIZER_CONFIG_ID


def fold_circumflex(text: str) -> str:
    """Turkish layer A on prose: inline code and URLs keep their exact form."""
    out, last = [], 0
    for match in _EXACT.finditer(text):
        out.append(text[last : match.start()].translate(_CIRCUMFLEX))
        out.append(match.group(0))
        last = match.end()
    out.append(text[last:].translate(_CIRCUMFLEX))
    return "".join(out)


def clean_markdown(text: str, *, turkish: bool = False) -> str:
    """Silver write boundary and query entry. Fenced code blocks are left exactly as they are;
    `turkish` adds layer A (TEXT_NORMALIZE_TR) to the prose."""
    if not text:
        return ""
    parts = _FENCE.split(fix_unicode(text))
    for index, part in enumerate(parts):
        if index % 2:  # odd indexes are the fenced blocks
            continue
        part = _BLANK_RUNS.sub("\n\n", _clean_markup(part))
        parts[index] = fold_circumflex(part) if turkish else part
    return "".join(parts).strip()


def normalize_query(query: str, *, turkish: bool = False) -> str:
    """The same configuration as silver (K1): a query and a document must meet in one form."""
    return clean_markdown(query, turkish=turkish)
