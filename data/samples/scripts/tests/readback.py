"""Stdlib read-back of the generated PDF and DOCX files, for tests only.

PDF: follows Catalog -> Pages -> Kids -> Contents, inflates FlateDecode streams and
decodes Tj strings through the font's /ToUnicode CMap (not through cp1254 directly),
so a broken CMap fails the test. This proves the text layer structurally; it is not a
substitute for Docling, which 04a's ingest test covers.
"""

import re
import zipfile
import zlib
from io import BytesIO

_OBJ = re.compile(rb"(\d+) 0 obj\n(.*?)\nendobj", re.S)


def _objects(data: bytes) -> dict[int, bytes]:
    return {int(n): body for n, body in _OBJ.findall(data)}


def _stream(body: bytes) -> bytes:
    head, _, rest = body.partition(b"stream\n")
    raw = rest.rsplit(b"\nendstream", 1)[0]
    return zlib.decompress(raw) if b"/FlateDecode" in head else raw


def _ref(body: bytes, key: bytes) -> int:
    m = re.search(rb"/" + key + rb" (\d+) 0 R", body)
    if not m:
        raise ValueError(f"no /{key.decode()} reference")
    return int(m.group(1))


def _cmap(text: bytes) -> dict[int, str]:
    return {int(src, 16): chr(int(dst, 16))
            for src, dst in re.findall(rb"<([0-9A-F]{2})> <([0-9A-F]{4})>", text)}


def _pdf_strings(content: bytes) -> list[bytes]:
    out = []
    i = 0
    while True:
        start = content.find(b"(", i)
        if start < 0:
            return out
        buf, j = bytearray(), start + 1
        while content[j:j + 1] != b")":
            c = content[j:j + 1]
            if c == b"\\":
                nxt = content[j + 1:j + 2]
                if nxt.isdigit():
                    buf.append(int(content[j + 1:j + 4], 8))
                    j += 4
                    continue
                buf += nxt
                j += 2
                continue
            buf += c
            j += 1
        out.append(bytes(buf))
        i = j + 1


def pdf_info(data: bytes) -> dict:
    objs = _objects(data)
    root = _ref(data.rsplit(b"trailer", 1)[1], b"Root")
    pages = objs[_ref(objs[root], b"Pages")]
    kids = [int(k) for k in re.findall(rb"(\d+) 0 R", re.search(rb"/Kids \[(.*?)\]", pages).group(1))]
    font = objs[_ref(objs[kids[0]], b"F1")]
    cmap = _cmap(_stream(objs[_ref(font, b"ToUnicode")]))
    page_texts = []
    for kid in kids:
        content = _stream(objs[_ref(objs[kid], b"Contents")])
        lines = ["".join(cmap[b] for b in s) for s in _pdf_strings(content)]
        page_texts.append(lines)
    return {"pages": page_texts, "font": font,
            "flate": all(b"/FlateDecode" in objs[_ref(objs[k], b"Contents")] for k in kids)}


def docx_info(data: bytes) -> dict:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    paragraphs = []
    for p in re.findall(r"<w:p>(.*?)</w:p>", xml, re.S):
        style = re.search(r'<w:pStyle w:val="(\w+)"/>', p)
        text = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&amp;", "&")
        paragraphs.append((style.group(1) if style else None, text))
    return {"paragraphs": paragraphs, "tables": xml.count("<w:tbl>")}


def text_of(path) -> str:
    data = path.read_bytes()
    if data.startswith(b"%PDF"):
        return "\n".join(line for page in pdf_info(data)["pages"] for line in page)
    return "\n".join(t for _, t in docx_info(data)["paragraphs"])
