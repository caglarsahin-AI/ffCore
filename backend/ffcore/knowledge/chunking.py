"""Heading-aware chunking with a breadcrumb prefix and a hard character ceiling (brief 04 D2, D5).

Adapted from PayCore `ingest/chunking.py`, with its measured values (K-04a-0002 S2):
greedy packing between `min_tokens` 400 and `max_tokens` 600, no overlap; tokens estimated as
max(words × 1,6, characters / 6) (Turkish tokenizes 30-40 % heavier; text without spaces is
counted by length, PayCore 2026-10-08); over-long text is split by paragraph, then sentence,
then word, and a word longer than the limit by the counter itself. The limit holds for the
embedded text "<breadcrumb>\\n\\n<body>", breadcrumb included (review r1 MAJOR-4); a breadcrumb
that leaves no room fails loud. The body alone is what duplicate detection hashes.
PDF converters mark pages with `<!-- page: N -->`; the marker sets the chunk's page and is
removed from the text.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

TOKENS_PER_WORD = 1.6
CHARS_PER_TOKEN = 6
# Measured upper/lower ratio (PayCore 600 / 400).
MAX_TO_MIN_RATIO = 1.5
MAX_MERGED_HEADINGS = 3
BREADCRUMB_SEPARATOR = " › "
# A section heading in a breadcrumb: at most this long, structure only (FOLLOWUP-108).
MAX_HEADING_CHARS = 60
# A breadcrumb may take at most half of max_tokens; a longer one is a document error, not a
# reason to shrink every body to a few tokens.
MAX_BREADCRUMB_SHARE = 0.5
# Tokens can merge across the breadcrumb/body boundary, so a body is split to this many tokens
# under the remaining budget; the final count is checked anyway.
BOUNDARY_SLACK = 2

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.M)
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")
_PAGE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")
# A paragraph that opens a contract article: "Madde 10 - Fesih 10.1 ...". Used as the section
# boundary when the converter produced no Markdown headings (brief 04 step 7: article numbers
# start chunks). The heading is "Madde 10 - Fesih", without the first sub-clause.
_ARTICLE = re.compile(
    r"^(?:<!--\s*page:\s*\d+\s*-->\s*)?(Madde\s+\d+(?:\s*[-–:]\s*[^\n]*?)?)"
    r"(?=\s+\d+\.\d+|\s*\n|$)",
    re.M,
)
_ARTICLE_NUMBER = re.compile(r"Madde\s+\d+")
_SECTION_NUMBER = re.compile(r"(\d+(?:\.\d+)*)\.?(?:\s|$)")


class ChunkingError(ValueError):
    """A text that cannot be chunked within the limits; the document fails with this code."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code


def approx_tokens(text: str) -> int:
    return max(int(len(text.split()) * TOKENS_PER_WORD), len(text) // CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ChunkSettings:
    min_tokens: int
    max_tokens: int
    # Token counter for the limits. The ingest passes the embedding model's tokenizer (K-04a-0010:
    # the estimate counted 593 where bge-m3 counts 678); the estimate stays for tests and as the
    # documented fallback of nothing: the caller chooses explicitly.
    count: Callable[[str], int] = field(default=approx_tokens, compare=False)

    @classmethod
    def from_kb(
        cls, chunk_size: int, chunk_overlap: int = 0, count: Callable[[str], int] = approx_tokens
    ) -> "ChunkSettings":
        if chunk_overlap:
            # Not measured and not implemented: refused, never silently ignored (ARCH-06).
            raise ValueError("chunk_overlap_unsupported")
        return cls(
            min_tokens=chunk_size, max_tokens=round(chunk_size * MAX_TO_MIN_RATIO), count=count
        )

    @property
    def max_chars(self) -> int:
        return self.max_tokens * CHARS_PER_TOKEN


@dataclass(frozen=True)
class TextChunk:
    ordinal: int
    breadcrumb: str
    body: str
    page: int | None
    section_path: str | None
    tokens: int = 0

    @property
    def text(self) -> str:
        return f"{self.breadcrumb}\n\n{self.body}"

    @property
    def token_count(self) -> int:
        return self.tokens or approx_tokens(self.text)


def structural_heading(heading: str) -> str | None:
    """The part of a heading a breadcrumb may carry (FOLLOWUP-108): structure, never body text.
    An article keeps "Madde N - Title" up to the first colon (plain text writes "Madde 2 - Süre:
    the clause..."); anything over MAX_HEADING_CHARS keeps only its number, and a long heading
    without a number stays out of the breadcrumb (it is still in the chunk body)."""
    heading = " ".join(heading.split())
    article = _ARTICLE_NUMBER.match(heading)
    if article:
        heading = heading.split(":", 1)[0].rstrip(" -–")
    if not heading:
        return None
    if len(heading) <= MAX_HEADING_CHARS:
        return heading
    if article:
        return article.group(0)
    number = _SECTION_NUMBER.match(heading)
    return number.group(1) if number else None


def _article_sections(body: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    starts = [m for m in _ARTICLE.finditer(body) if m.start() == 0 or body[m.start() - 1] == "\n"]
    if not starts:
        return []
    head = body[: starts[0].start()].strip()
    if head:
        out.append(("", head))
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        text = body[match.start() : end].strip()
        if text:
            # The heading stays in the text too, so the chunk body starts with the article number.
            out.append((match.group(1).strip()[:80], text))
    return out


def _sections(body: str) -> list[tuple[str, str]]:
    if not _HEADING.search(body):
        articles = _article_sections(body)
        if articles:
            return articles
    out: list[tuple[str, str]] = []
    last_end, heading = 0, ""
    for match in _HEADING.finditer(body):
        text = body[last_end : match.start()].strip()
        if text:
            out.append((heading, text))
        heading, last_end = match.group(2).strip(), match.end()
    tail = body[last_end:].strip()
    if tail:
        out.append((heading, tail))
    return out


def _split_word(word: str, max_tokens: int, count) -> list[str]:
    """A word over the limit, cut at the longest prefix the counter accepts (binary search)."""
    if count(word) <= max_tokens:
        return [word]
    pieces: list[str] = []
    start = 0
    while start < len(word):
        low, high = start + 1, len(word)
        if count(word[start:low]) > max_tokens:
            raise ChunkingError("chunk_unsplittable", f"one character exceeds {max_tokens} tokens")
        while low < high:
            middle = (low + high + 1) // 2
            if count(word[start:middle]) <= max_tokens:
                low = middle
            else:
                high = middle - 1
        pieces.append(word[start:low])
        start = low
    return pieces


def _split_words(text: str, max_tokens: int, count=approx_tokens) -> list[str]:
    if count(text) <= max_tokens:
        return [text]
    out: list[str] = []
    current: list[str] = []
    for word in text.split():
        for piece in _split_word(word, max_tokens, count):
            if current and count(" ".join([*current, piece])) > max_tokens:
                out.append(" ".join(current))
                current = []
            current.append(piece)
    if current:
        out.append(" ".join(current))
    return out


def _split_paragraph(text: str, max_tokens: int, count=approx_tokens) -> list[str]:
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE.split(text):
        if not sentence:
            continue
        if current and count(current + " " + sentence) > max_tokens:
            out.append(current.strip())
            current = ""
        current += (" " if current else "") + sentence
    if current.strip():
        out.append(current.strip())
    return [piece for s in (out or [text]) for piece in _split_words(s, max_tokens, count)]


def _split_long(text: str, max_tokens: int, count=approx_tokens) -> list[str]:
    out: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        if count(para) > max_tokens:
            if current.strip():
                out.append(current.strip())
                current = ""
            out.extend(_split_paragraph(para, max_tokens, count))
            continue
        if current and count(current + "\n\n" + para) > max_tokens:
            out.append(current.strip())
            current = ""
        current += ("\n\n" if current else "") + para
    if current.strip():
        out.append(current.strip())
    return out


def _pack(body: str, settings: ChunkSettings) -> list[tuple[list[str], str]]:
    """(headings, text) pieces: greedy packing into [min, max]; the buffer is flushed once it
    reaches the minimum and before it would pass the maximum (PayCore 2026-09-26)."""
    pieces: list[tuple[list[str], str]] = []
    headings: list[str] = []
    buffer = ""

    def flush() -> None:
        nonlocal buffer, headings
        if buffer.strip():
            pieces.append((headings[:MAX_MERGED_HEADINGS], buffer))
        buffer, headings = "", []

    def note(raw: str) -> None:
        heading = structural_heading(raw)
        if heading and heading not in headings:
            headings.append(heading)

    for heading, text in _sections(body):
        if settings.count(text) > settings.max_tokens:
            flush()
            for piece in _split_long(text, settings.max_tokens, settings.count):
                note(heading)
                buffer = piece
                flush()
            continue
        if buffer and settings.count(buffer + "\n\n" + text) > settings.max_tokens:
            flush()
        note(heading)
        buffer += ("\n\n" if buffer else "") + text
        if settings.count(buffer) >= settings.min_tokens:
            flush()
    flush()
    return pieces


def chunk_markdown(body: str, *, breadcrumb: str, settings: ChunkSettings) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    page: int | None = None
    for headings, text in _pack(body, settings):
        markers = list(_PAGE.finditer(text))
        start_page = page
        if markers and not text[: markers[0].start()].strip():
            start_page = int(markers[0].group(1))
        if markers:
            page = int(markers[-1].group(1))
        clean = re.sub(r"[ \t]*\n{3,}", "\n\n", _PAGE.sub("", text)).strip()
        if not clean:
            continue
        section = " · ".join(headings) if headings else None
        crumb = f"{breadcrumb}{BREADCRUMB_SEPARATOR}{section}" if section else breadcrumb
        for body_piece in _fit(crumb, clean, settings):
            tokens = settings.count(crumb + "\n\n" + body_piece)
            if tokens > settings.max_tokens:
                raise ChunkingError("chunk_over_limit", f"{tokens} > {settings.max_tokens} tokens")
            chunks.append(
                TextChunk(
                    ordinal=len(chunks),
                    breadcrumb=crumb,
                    body=body_piece,
                    page=start_page,
                    section_path=section,
                    tokens=tokens,
                )
            )
    return chunks


def _fit(crumb: str, body: str, settings: ChunkSettings) -> list[str]:
    """The body as is, or split so that breadcrumb + body fits max_tokens (review r1 MAJOR-4)."""
    count = settings.count
    if count(crumb + "\n\n" + body) <= settings.max_tokens:
        return [body]
    prefix = count(crumb + "\n\n")
    if prefix > settings.max_tokens * MAX_BREADCRUMB_SHARE:
        raise ChunkingError(
            "chunk_breadcrumb_too_long",
            f"breadcrumb takes {prefix} of {settings.max_tokens} tokens",
        )
    return _split_long(body, settings.max_tokens - prefix - BOUNDARY_SLACK, count)
