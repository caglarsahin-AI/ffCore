"""Minimal deterministic PDF writer with a real text layer (stdlib only).

Text uses the base-14 Helvetica / Helvetica-Bold fonts with a cp1254-based
encoding: WinAnsi plus /Differences for the six Turkish glyphs that WinAnsi lacks
(ğ Ğ ş Ş ı İ), and a /ToUnicode CMap so extractors (Docling/pypdfium2, pymupdf)
map every byte back to the right Unicode character. Content streams are
FlateDecode-compressed. No timestamps or IDs, so output is byte-stable for a given
zlib build.

Blocks: ("h1"|"h2"|"p", text) and ("table", [[cell, ...], ...]).
"""

import textwrap
import zlib

PAGE_W, PAGE_H = 595, 842  # A4 in points
MARGIN = 56
LINE_H = {"h1": 20, "h2": 16, "p": 13, "row": 13}
SIZE = {"h1": 14, "h2": 11, "p": 10, "row": 9}
WRAP = {"h1": 60, "h2": 80, "p": 92, "row": 100}

# cp1254 positions WinAnsi assigns differently, with their standard glyph names
DIFFERENCES = {
    0xD0: "Gbreve",
    0xDD: "Idotaccent",
    0xDE: "Scedilla",
    0xF0: "gbreve",
    0xFD: "dotlessi",
    0xFE: "scedilla",
}


def encode(text: str) -> bytes:
    return text.encode("cp1254")  # raises on characters outside the encoding (fail-loud)


def _pdf_string(data: bytes) -> bytes:
    out = bytearray(b"(")
    for b in data:
        if b in (0x28, 0x29, 0x5C):  # ( ) \
            out += b"\\" + bytes([b])
        elif 0x20 <= b < 0x7F:
            out.append(b)
        else:
            out += b"\\%03o" % b
    return bytes(out + b")")


def to_unicode_cmap() -> bytes:
    pairs = []
    for code in range(0x20, 0x100):
        try:
            ch = bytes([code]).decode("cp1254")
        except UnicodeDecodeError:
            continue
        pairs.append(b"<%02X> <%04X>" % (code, ord(ch)))
    body = [
        b"/CIDInit /ProcSet findresource begin",
        b"12 dict begin",
        b"begincmap",
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        b"/CMapName /FFCore-cp1254 def",
        b"/CMapType 2 def",
        b"1 begincodespacerange",
        b"<00> <FF>",
        b"endcodespacerange",
    ]
    for start in range(0, len(pairs), 100):
        chunk = pairs[start : start + 100]
        body.append(b"%d beginbfchar" % len(chunk))
        body.extend(chunk)
        body.append(b"endbfchar")
    body += [b"endcmap", b"CMapName currentdict /CMap defineresource pop", b"end", b"end"]
    return b"\n".join(body) + b"\n"


def layout(blocks: list[tuple]) -> list[tuple[str, str]]:
    """Flatten blocks into (kind, line) pairs; tables become " | "-joined rows."""
    lines: list[tuple[str, str]] = []
    for kind, value in blocks:
        if kind == "table":
            for row in value:
                lines.append(("row", " | ".join(str(c) for c in row)))
            lines.append(("p", ""))
            continue
        for wrapped in textwrap.wrap(value, WRAP[kind]) or [""]:
            lines.append((kind, wrapped))
        if kind != "p":
            continue
        lines.append(("p", ""))
    return lines


def paginate(lines: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    pages, page, y = [], [], PAGE_H - MARGIN
    for kind, text in lines:
        h = LINE_H[kind]
        if y - h < MARGIN and page:
            pages.append(page)
            page, y = [], PAGE_H - MARGIN
        page.append((kind, text))
        y -= h
    if page:
        pages.append(page)
    return pages


def _content(page: list[tuple[str, str]], number: int, total: int) -> bytes:
    ops, y = [], PAGE_H - MARGIN
    for kind, text in page:
        y -= LINE_H[kind]
        if not text:
            continue
        font = b"/F2" if kind in ("h1", "h2") else b"/F1"
        ops.append(
            b"BT %s %d Tf %d %d Td %s Tj ET"
            % (font, SIZE[kind], MARGIN, y, _pdf_string(encode(text)))
        )
    footer = encode(f"Sayfa {number} / {total} - Sentetik örnek belge")
    ops.append(b"BT /F1 8 Tf %d %d Td %s Tj ET" % (MARGIN, MARGIN - 24, _pdf_string(footer)))
    return b"\n".join(ops) + b"\n"


def _stream(data: bytes, extra: bytes = b"") -> bytes:
    packed = zlib.compress(data, 9)
    return (
        b"<< /Length %d /Filter /FlateDecode%s >>\nstream\n" % (len(packed), extra)
        + packed
        + b"\nendstream"
    )


def render(blocks: list[tuple], title: str, pages_exact: int | None = None, filler=None) -> bytes:
    """Render blocks; with pages_exact, call filler() for extra blocks until the page
    count is reached. Raises if content alone already exceeds pages_exact."""
    blocks = list(blocks)
    pages = paginate(layout(blocks))
    if pages_exact is not None:
        if len(pages) > pages_exact:
            raise ValueError(f"{title}: {len(pages)} pages > {pages_exact}")
        while len(pages) < pages_exact:
            candidate = blocks + [filler()]
            candidate_pages = paginate(layout(candidate))
            if len(candidate_pages) > pages_exact:
                break
            blocks, pages = candidate, candidate_pages
        if len(pages) != pages_exact:
            raise ValueError(f"{title}: could not reach {pages_exact} pages ({len(pages)})")

    diffs = b" ".join(
        b"%d /%s" % (code, name.encode()) for code, name in sorted(DIFFERENCES.items())
    )
    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)

    catalog = add(b"")  # placeholders filled below
    pages_obj = add(b"")
    encoding = add(
        b"<< /Type /Encoding /BaseEncoding /WinAnsiEncoding /Differences [%s] >>" % diffs
    )
    cmap = add(_stream(to_unicode_cmap()))
    f1 = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding %d 0 R /ToUnicode %d 0 R >>"
        % (encoding, cmap)
    )
    f2 = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding %d 0 R /ToUnicode %d "
        b"0 R >>" % (encoding, cmap)
    )
    info = add(
        b"<< /Title %s /Producer (FFCore sample data generator) >>" % _pdf_string(encode(title))
    )

    kids = []
    for i, page in enumerate(pages, start=1):
        content = add(_stream(_content(page, i, len(pages))))
        kids.append(
            add(
                b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] "
                b"/Resources << /Font << /F1 %d 0 R /F2 %d 0 R >> >> /Contents %d 0 R >>"
                % (pages_obj, PAGE_W, PAGE_H, f1, f2, content)
            )
        )
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
    objects[pages_obj - 1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids),
        len(kids),
    )

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        catalog,
        info,
        xref,
    )
    return bytes(out)
