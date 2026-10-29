"""Quality gates 1 and 2 and the data dump detector (brief 04 D1). Pure rules: no model, no I/O.

Adapted from PayCore `ingest/gates.py`, thresholds as measured there (`config.py` gate_*):
  min document 30 tokens · min chunk 20 tokens · min stopword ratio 0,05 · no_prose flag from
  2000 characters · code lines > 0,5 · link lines > 0,6 (boilerplate) · data dump from 20 lines
  with a 0,6 line share · structure character density 0,15.
Changes for FFCore: the Atlassian rules (Confluence `status`, Jira `unresolved`, label templates)
stay with the source connectors (16); the language rule takes ALLOWED_LANGUAGES (tr, en)
instead of "Turkish or nothing" (brief 04: Turkish-only had dropped 25 % of PayCore's technical
pages).

Each gate returns (status, reason); nothing is deleted. `skipped` = not indexed, `flagged` =
indexed but reported. Kapı 1 rejecting is final; Kapı 2 never undoes it (`combine`).
"""

import json
import re
from collections import Counter
from dataclasses import dataclass

from ffcore.knowledge.chunking import approx_tokens
from ffcore.knowledge.normalize import fix_unicode

OK, FLAGGED, SKIPPED = "ok", "flagged", "skipped"
Verdict = tuple[str, str | None]


@dataclass(frozen=True)
class GateThresholds:
    min_doc_tokens: int = 30
    min_chunk_tokens: int = 20
    min_stopword_ratio: float = 0.05
    no_prose_flag_chars: int = 2000
    max_code_ratio: float = 0.5
    max_link_ratio: float = 0.6
    data_min_lines: int = 20
    data_line_ratio: float = 0.6
    # Texts shorter than this have no measurable language (PayCore: 40 words).
    language_min_words: int = 40


DEFAULT = GateThresholds()

# Short, high-frequency function words: their density separates prose from tables, link lists,
# logs and code (PayCore list, tuned there by hand).
TR_STOPWORDS = frozenset(
    """
    acaba ama ancak artık asla aslında az bana bazı belki ben beni benim bile bir biraz birçok biri
    birkaç birşey biz bize bizi bizim bu buna bunda bundan bunlar bunu bunun burada çok çünkü da
    daha de defa değil diğer diye dolayı eğer en fakat gibi hangi hangisi hani hem hep hepsi her
    herkes hiç hiçbir için ile ise işte kadar karşın kendi kez ki kim kime kimi mi mu mü nasıl ne
    neden nerede nereye niçin niye o olan olarak oldu olduğu olmak olsa olsun olur ona onda ondan
    onlar onu onun orada öyle sanki sen senin siz sizin sonra şey şöyle şu şuna şunu tarafından tüm
    üzere var ve veya ya yani yine yoksa
    """.split()  # noqa: SIM905 - a hand-tuned word list reads as text
)
EN_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can for from has have if in is it its of on or that the
    their there they this to was were will with would you your
    """.split()  # noqa: SIM905
)
STOPWORDS = {"tr": TR_STOPWORDS, "en": EN_STOPWORDS}

_LETTERS = re.compile(r"[^\W\d_]+")
_CODE_LINE = re.compile(
    r"^\s*(?:[{}\[\]();]|//|#|--|<\w|import |from \w|def |class |select |insert |update |"
    r"at [\w.$]+\(|Caused by:|Exception|Traceback|\w+Error\b|\d{4}-\d{2}-\d{2}[ T]\d{2}:)",
    re.I,
)
_LINK_LINE = re.compile(r"^\s*[-*|]?\s*(?:\[[^\]]*\]|https?://\S+|\|)")
_TEMPLATE_TITLE = re.compile(r"^\s*(şablon|template|form örneği|örnek form)\b", re.I)


def tr_lower(text: str) -> str:
    """str.lower is wrong for Turkish: İ → i + U+0307 and I → i instead of ı."""
    return text.replace("İ", "i").replace("I", "ı").lower()


def words(text: str) -> list[str]:
    return [tr_lower(w) for w in _LETTERS.findall(fix_unicode(text))]


def stopword_ratio(text: str, vocabulary: frozenset[str] = TR_STOPWORDS) -> float:
    tokens = words(text)
    if not tokens:
        return 0.0
    return sum(w in vocabulary for w in tokens) / len(tokens)


def language_allowed(
    text: str, allowed: tuple[str, ...], thresholds: GateThresholds = DEFAULT
) -> bool:
    """The text's dominant function-word language is one of `allowed`.

    Technical Turkish is full of English names, so a page counts as Turkish when its Turkish
    ratio matches the English one or reaches the minimum ratio (PayCore rule); otherwise it is
    English when English function words reach the minimum; anything else is another language.
    """
    if len(words(text)) < thresholds.language_min_words:
        return True
    tr, en = stopword_ratio(text, TR_STOPWORDS), stopword_ratio(text, EN_STOPWORDS)
    if tr == 0 and en == 0:
        # No function words of either language: no measurable language (a link list, a table,
        # or a language without a list here). Kapı 1 does not judge it; Kapı 2 does
        # (boilerplate, no_prose), as in PayCore.
        return True
    if tr >= en or tr >= thresholds.min_stopword_ratio:
        detected = "tr"
    elif en >= thresholds.min_stopword_ratio:
        detected = "en"
    else:
        detected = "other"
    return detected in allowed


def gate1(
    body: str,
    *,
    title: str,
    duplicate_of: str | None = None,
    has_attachment_text: bool = False,
    allowed_languages: tuple[str, ...] = ("tr", "en"),
    thresholds: GateThresholds = DEFAULT,
) -> Verdict:
    """Document acceptance. Cheap structural rules first, language last, so the report names
    the most specific reason. A short body passes when the document's own attachments carry text.
    """
    body = (body or "").strip()
    if not has_attachment_text:
        if not body:
            return SKIPPED, "empty"
        if approx_tokens(body) < thresholds.min_doc_tokens:
            return SKIPPED, "too_short"
    if _TEMPLATE_TITLE.match(title or ""):
        return SKIPPED, "template"
    if duplicate_of:
        return SKIPPED, f"duplicate_of:{duplicate_of}"
    if body and not language_allowed(body, allowed_languages, thresholds):
        return SKIPPED, "language_not_allowed"
    return OK, None


def text_quality(
    body: str,
    *,
    title: str | None,
    duplicate_of: str | None = None,
    min_tokens: int | None = None,
    thresholds: GateThresholds = DEFAULT,
) -> Verdict:
    """Kapı 2 for a whole converted document or one chunk body (without the breadcrumb)."""
    body = (body or "").strip()
    min_tokens = thresholds.min_chunk_tokens if min_tokens is None else min_tokens
    if not body:
        return SKIPPED, "empty"
    if body.casefold() == (title or "").strip().casefold():
        return SKIPPED, "title_only"
    if approx_tokens(body) < min_tokens:
        return SKIPPED, "too_short"
    if duplicate_of:
        return SKIPPED, f"duplicate_of:{duplicate_of}"
    lines = [line for line in body.splitlines() if line.strip()]
    if sum(bool(_LINK_LINE.match(ln)) for ln in lines) / len(lines) > thresholds.max_link_ratio:
        return SKIPPED, "boilerplate"
    if sum(bool(_CODE_LINE.match(ln)) for ln in lines) / len(lines) > thresholds.max_code_ratio:
        return SKIPPED, "code_heavy"
    # Prose-free content: a large definition table is reference material (flag, keep); a small
    # one is noise (PayCore calibration 2026-09-25).
    if stopword_ratio(body) < thresholds.min_stopword_ratio:
        if len(body) >= thresholds.no_prose_flag_chars:
            return FLAGGED, "no_prose"
        return SKIPPED, "no_prose"
    return OK, None


# --- data dumps: judged by content, not by extension ---

_LOG_LINE = re.compile(
    r"^\s*\[?(?:\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}|\d{2}[./-]\d{2}[./-]\d{4}[ T]\d{2}:\d{2}"
    r"|\d{2}:\d{2}:\d{2}[.,]\d+|(?:INFO|WARN|WARNING|ERROR|DEBUG|TRACE|FATAL)\b)",
    re.I,
)
_TRACE_LINE = re.compile(
    r"^\s*(?:at [\w.$<>]+\(.*\)|Caused by:|Traceback \(most recent call last\)"
    r"|File \".*\", line \d+|[\w.$]+(?:Exception|Error)\b|\.\.\. \d+ more)"
)
_STRUCTURE_CHARS = frozenset('{}[]<>":=,')
_DELIMITERS = (";", "|", "\t", ",")
_STRUCTURE_DENSITY = 0.15
_FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")
_ENCODED_LINE = re.compile(r"^(?:[A-Za-z0-9+/]{40,}={0,2}|[0-9A-Fa-f]{40,})$")


def _is_structured(text: str, lines: list[str], ratio: float, thresholds: GateThresholds) -> bool:
    body = text.strip()
    if body[:1] in "{[":
        try:
            json.loads(body)
            return True
        except ValueError:
            pass
    if stopword_ratio(text) >= thresholds.min_stopword_ratio:
        return False
    if sum(ln.lstrip().startswith("<") for ln in lines) / len(lines) >= ratio:
        return True
    visible = [ch for ch in text if not ch.isspace()]
    return bool(visible) and (
        sum(ch in _STRUCTURE_CHARS for ch in visible) / len(visible) >= _STRUCTURE_DENSITY
    )


def _is_tabular(lines: list[str], ratio: float) -> bool:
    """Records, not reference: most lines split into the same number of fields by one delimiter
    and the fields are mostly digits. Markdown table rows are a document's own tables: kept."""
    rows = [ln for ln in lines if not ln.lstrip().startswith("|")]
    if len(rows) < len(lines) * ratio:
        return False
    digits = sum(ch.isdigit() for ln in rows for ch in ln)
    letters = sum(ch.isalpha() for ln in rows for ch in ln)
    if digits <= letters:
        return False
    for delimiter in _DELIMITERS:
        count, n = Counter(ln.count(delimiter) for ln in rows).most_common(1)[0]
        if count >= 2 and n / len(lines) >= ratio:
            return True
    return False


def data_dump(text: str, thresholds: GateThresholds = DEFAULT) -> str | None:
    """`encoded`, `log`, `stack_trace`, `structured`, `tabular` or None. Stored as
    ("skipped", "data_dump:<kind>"); the owning document is still indexed."""
    lines = [ln for ln in text.splitlines() if ln.strip() and not _FENCE_LINE.match(ln)]
    if len(lines) < thresholds.data_min_lines:
        return None
    ratio = thresholds.data_line_ratio
    if sum(bool(_ENCODED_LINE.match(ln.strip())) for ln in lines) / len(lines) >= ratio:
        return "encoded"
    logs = sum(bool(_LOG_LINE.match(ln)) for ln in lines)
    traces = sum(bool(_TRACE_LINE.match(ln)) for ln in lines)
    if (logs + traces) / len(lines) >= ratio:
        return "log" if logs >= traces else "stack_trace"
    if _is_structured(text, lines, ratio, thresholds):
        return "structured"
    if _is_tabular(lines, ratio):
        return "tabular"
    return None


def combine(gate1_verdict: Verdict, gate2_verdict: Verdict | None) -> Verdict:
    """Final document verdict; each gate keeps its own column, this only reads them."""
    if gate1_verdict[0] == SKIPPED or gate2_verdict is None:
        return gate1_verdict
    if gate2_verdict[0] == SKIPPED:
        return gate2_verdict
    for verdict in (gate1_verdict, gate2_verdict):
        if verdict[0] == FLAGGED:
            return verdict
    return OK, None
