"""Heading-aware chunking with a breadcrumb prefix and a hard character ceiling (brief 04 D2, D5).

Adapted from PayCore `ingest/chunking.py`, with its measured values (K-04a-0002 S2):
greedy packing between `min_tokens` 400 and `max_tokens` 600, no overlap; tokens estimated as
max(words × 1,6, characters / 6) (Turkish tokenizes 30-40 % heavier; text without spaces is
counted by length, PayCore 2026-10-08); over-long text is split by paragraph, then sentence,
then word, and a word longer than the limit by length. So no chunk body exceeds
max_tokens × 6 characters. The embedded text is "<breadcrumb>\\n\\n<body>"; the body alone is
what duplicate detection hashes.
PDF converters mark pages with `<!-- page: N -->`; the marker sets the chunk's page and is
removed from the text.
"""

import re
from dataclasses import dataclass

TOKENS_PER_WORD = 1.6
CHARS_PER_TOKEN = 6
# Measured upper/lower ratio (PayCore 600 / 400).
MAX_TO_MIN_RATIO = 1.5
MAX_MERGED_HEADINGS = 3
BREADCRUMB_SEPARATOR = " › "

_HEADING = re.compile(r"^(#{1,3})\s+(.*)$", re.M)
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")
_PAGE = re.compile(r"<!--\s*page:\s*(\d+)\s*-->")


def approx_tokens(text: str) -> int:
    return max(int(len(text.split()) * TOKENS_PER_WORD), len(text) // CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ChunkSettings:
    min_tokens: int
    max_tokens: int

    @classmethod
    def from_kb(cls, chunk_size: int, chunk_overlap: int = 0) -> "ChunkSettings":
        if chunk_overlap:
            # Not measured and not implemented: refused, never silently ignored (ARCH-06).
            raise ValueError("chunk_overlap_unsupported")
        return cls(min_tokens=chunk_size, max_tokens=round(chunk_size * MAX_TO_MIN_RATIO))

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

    @property
    def text(self) -> str:
        return f"{self.breadcrumb}\n\n{self.body}"

    @property
    def token_count(self) -> int:
        return approx_tokens(self.text)


def _sections(body: str) -> list[tuple[str, str]]:
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


def _split_words(text: str, max_tokens: int) -> list[str]:
    if approx_tokens(text) <= max_tokens:
        return [text]
    max_chars = max_tokens * CHARS_PER_TOKEN
    out: list[str] = []
    current: list[str] = []
    for word in text.split():
        for piece in (word[i : i + max_chars] for i in range(0, len(word), max_chars)):
            if current and approx_tokens(" ".join([*current, piece])) > max_tokens:
                out.append(" ".join(current))
                current = []
            current.append(piece)
    if current:
        out.append(" ".join(current))
    return out


def _split_paragraph(text: str, max_tokens: int) -> list[str]:
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE.split(text):
        if not sentence:
            continue
        if current and approx_tokens(current + " " + sentence) > max_tokens:
            out.append(current.strip())
            current = ""
        current += (" " if current else "") + sentence
    if current.strip():
        out.append(current.strip())
    return [piece for s in (out or [text]) for piece in _split_words(s, max_tokens)]


def _split_long(text: str, max_tokens: int) -> list[str]:
    out: list[str] = []
    current = ""
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        if approx_tokens(para) > max_tokens:
            if current.strip():
                out.append(current.strip())
                current = ""
            out.extend(_split_paragraph(para, max_tokens))
            continue
        if current and approx_tokens(current + "\n\n" + para) > max_tokens:
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

    def note(heading: str) -> None:
        if heading and heading not in headings:
            headings.append(heading)

    for heading, text in _sections(body):
        if approx_tokens(text) > settings.max_tokens:
            flush()
            for piece in _split_long(text, settings.max_tokens):
                note(heading)
                buffer = piece
                flush()
            continue
        if buffer and approx_tokens(buffer + "\n\n" + text) > settings.max_tokens:
            flush()
        note(heading)
        buffer += ("\n\n" if buffer else "") + text
        if approx_tokens(buffer) >= settings.min_tokens:
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
        chunks.append(
            TextChunk(
                ordinal=len(chunks),
                breadcrumb=crumb,
                body=clean,
                page=start_page,
                section_path=section,
            )
        )
    return chunks
