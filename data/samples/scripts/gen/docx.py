"""Minimal deterministic DOCX writer (stdlib only: zipfile + XML strings).

Headings use the built-in Heading1/Heading2 style ids so Docling sees the heading
hierarchy; tables are real w:tbl elements. Zip entries have a fixed timestamp,
order and creator system (Unix on every OS), so output is byte-stable for a given
zlib build.

Blocks: ("h1"|"h2"|"p", text) and ("table", [[cell, ...], ...]).
"""

import io
import zipfile
from xml.sax.saxutils import escape

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
FIXED_TIME = (1980, 1, 1, 0, 0, 0)

OXML = "http://schemas.openxmlformats.org"
WML = "application/vnd.openxmlformats-officedocument.wordprocessingml"
REL = f"{OXML}/officeDocument/2006/relationships"
PKG_REL = f"{OXML}/package/2006/relationships"
XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
BORDER = 'w:val="single" w:sz="4"'


def _xml(*lines: str) -> str:
    return "\n".join(lines) + "\n"


CONTENT_TYPES = _xml(
    XML_DECL,
    f'<Types xmlns="{OXML}/package/2006/content-types">',
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
    '<Default Extension="xml" ContentType="application/xml"/>',
    f'<Override PartName="/word/document.xml" ContentType="{WML}.document.main+xml"/>',
    f'<Override PartName="/word/styles.xml" ContentType="{WML}.styles+xml"/>',
    '<Override PartName="/docProps/core.xml" '
    'ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
    "</Types>",
)

ROOT_RELS = _xml(
    XML_DECL,
    f'<Relationships xmlns="{PKG_REL}">',
    f'<Relationship Id="rId1" Type="{REL}/officeDocument" Target="word/document.xml"/>',
    f'<Relationship Id="rId2" Type="{PKG_REL}/metadata/core-properties" '
    'Target="docProps/core.xml"/>',
    "</Relationships>",
)

DOC_RELS = _xml(
    XML_DECL,
    f'<Relationships xmlns="{PKG_REL}">',
    f'<Relationship Id="rId1" Type="{REL}/styles" Target="styles.xml"/>',
    "</Relationships>",
)


def _heading_style(level: int, size: int) -> str:
    return (
        f'<w:style w:type="paragraph" w:styleId="Heading{level}">'
        f'<w:name w:val="heading {level}"/><w:basedOn w:val="Normal"/>'
        f'<w:pPr><w:outlineLvl w:val="{level - 1}"/></w:pPr>'
        f'<w:rPr><w:b/><w:sz w:val="{size}"/></w:rPr></w:style>'
    )


STYLES = _xml(
    XML_DECL,
    f'<w:styles xmlns:w="{W_NS}">',
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    '<w:rPr><w:sz w:val="22"/></w:rPr></w:style>',
    _heading_style(1, 32),
    _heading_style(2, 26),
    '<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/>'
    "<w:tblPr><w:tblBorders>",
    f"<w:top {BORDER}/><w:left {BORDER}/><w:bottom {BORDER}/>",
    f"<w:right {BORDER}/><w:insideH {BORDER}/><w:insideV {BORDER}/>",
    "</w:tblBorders></w:tblPr></w:style>",
    "</w:styles>",
)


def _para(text: str, style: str | None = None) -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f'<w:p>{ppr}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def _table(rows: list[list]) -> str:
    out = [
        '<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
    ]
    for row in rows:
        cells = "".join(f"<w:tc>{_para(str(c))}</w:tc>" for c in row)
        out.append(f"<w:tr>{cells}</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def document_xml(blocks: list[tuple]) -> str:
    body = []
    for kind, value in blocks:
        if kind == "table":
            body.append(_table(value))
        else:
            body.append(_para(value, {"h1": "Heading1", "h2": "Heading2"}.get(kind)))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document '
        f'xmlns:w="{W_NS}"><w:body>{"".join(body)}<w:sectPr><w:pgSz w:w="11906" '
        'w:h="16838"/></w:sectPr></w:body></w:document>\n'
    )


def core_xml(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        "<cp:coreProperties "
        'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f"<dc:title>{escape(title)}</dc:title><dc:creator>FFCore sample data "
        "generator</dc:creator></cp:coreProperties>\n"
    )


def render(blocks: list[tuple], title: str) -> bytes:
    parts = [
        ("[Content_Types].xml", CONTENT_TYPES),
        ("_rels/.rels", ROOT_RELS),
        ("docProps/core.xml", core_xml(title)),
        ("word/_rels/document.xml.rels", DOC_RELS),
        ("word/document.xml", document_xml(blocks)),
        ("word/styles.xml", STYLES),
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, text in parts:
            info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # ZipInfo defaults to 0 on Windows, 3 elsewhere
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"), compresslevel=9)
    return buf.getvalue()
