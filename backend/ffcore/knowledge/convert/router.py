"""Route a file to a converter by its first bytes, the extension only as a fallback (brief D2).

Adapted from PayCore `convert/router.sniff` (same order). The scope sets come from
knowledge/scope.py, the one definition Kapı 0 also reads. 04a has no LibreOffice: a real old
Office binary is `skip_libreoffice`; a ".doc" that is MHTML (Word "single file web page") is
recognised by its bytes and read.
"""

from pathlib import Path

from ffcore.knowledge import scope

EXT_MAP: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "office",
    ".dotx": "office",
    ".pptx": "office",
    ".html": "office",
    ".htm": "office",
    ".md": "office",
    ".msg": "email_msg",
    ".eml": "email_eml",
    ".mht": "mhtml",
    ".mhtml": "mhtml",
    ".drawio": "diagram",
    ".vsdx": "diagram",
    ".txt": "plaintext",
    ".log": "plaintext",
    ".xml": "plaintext",
    ".yaml": "plaintext",
    ".yml": "plaintext",
    ".json": "plaintext",
    ".doc": "skip_libreoffice",
}

# Handler → MIME type recorded in documents.mime_sniffed.
MIME = {
    "pdf": "application/pdf",
    "office": "application/vnd.openxmlformats-officedocument",
    "mhtml": "multipart/related",
    "email_msg": "application/vnd.ms-outlook",
    "email_eml": "message/rfc822",
    "diagram": "application/vnd.drawio+xml",
    "plaintext": "text/plain",
}

HEAD_BYTES = 256


def is_mhtml(head: bytes) -> bool:
    """MIME headers first and a multipart/related body: a web archive, not an e-mail."""
    start = head.lstrip().lower()
    return start.startswith(b"mime-version:") and b"multipart/related" in start


def head_bytes(path: Path, n: int = HEAD_BYTES) -> bytes:
    # Only the magic bytes: uploads may be hundreds of MB.
    with path.open("rb") as handle:
        return handle.read(n)


def sniff(path: Path, filename: str | None = None) -> str:
    name = filename or path.name
    suffix = Path(name).suffix.lower()
    ext = suffix.lstrip(".")
    if ext in scope.BINARY:
        return "skip_binary"
    if ext in scope.OUT_OF_SCOPE:
        return "skip_scope"
    if ext in scope.VIDEO:
        return "skip_video"
    head = head_bytes(path)
    if b"<mxfile" in head or b"<diagram" in head:
        return "diagram"
    if suffix not in {".eml", ".msg"} and is_mhtml(head):
        return "mhtml"
    if ext in scope.OLD_OFFICE:
        return "skip_libreoffice"
    if suffix in EXT_MAP:
        return EXT_MAP[suffix]
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        # A zip that is not one of the OOXML formats we read is a container: out of scope.
        return "skip_scope"
    return "skip_unknown"
