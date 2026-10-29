"""Plain text, e-mail (.msg, .eml), MHTML web archives and diagrams (draw.io, .vsdx).

Adapted from PayCore `convert/{plaintext,email_msg,mhtml,diagram}.py`. Changes: decoding is
strict (encoding.py) so a file with undecodable bytes fails instead of carrying U+FFFD; the
.msg cp1254 re-read keeps the PayCore rule (pick the reading without replacement characters).
"""

import base64
import email
import re
import tempfile
import zipfile
import zlib
from email import policy
from html import unescape
from pathlib import Path
from xml.etree import ElementTree

from ffcore.knowledge.convert.encoding import FALLBACK, UndecodableText, decode_text
from ffcore.knowledge.convert.limits import LimitExceeded, inflate_raw
from ffcore.knowledge.convert.types import MIN_TEXT_CHARS, ConversionResult, empty, failed

_HTML_START = re.compile(r"^\s*(?:<!DOCTYPE|<html|<head|<body|<div|<p[\s>]|<table)", re.I)
_BLANK_RUNS = re.compile(r"\n\s*\n+")


def _decode_or_fail(data: bytes, method: str) -> tuple[str, str] | ConversionResult:
    try:
        return decode_text(data)
    except UndecodableText as exc:
        return failed(method, "encoding_undecodable", str(exc))


def convert_plaintext(path: Path) -> ConversionResult:
    """Bytes are the content; fenced so chunking does not read config or logs as prose."""
    decoded = _decode_or_fail(path.read_bytes(), "plaintext")
    if isinstance(decoded, ConversionResult):
        return decoded
    text, label = decoded
    text = text.strip()
    warnings = [] if label == "utf-8" else [f"encoding: {label}"]
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, "plaintext", warnings)
    return ConversionResult(f"```\n{text}\n```", "plaintext", warnings=warnings)


def html_body_text(body: str) -> str:
    """An HTML body as the text a reader sees; plain text is returned unchanged."""
    if not _HTML_START.match(body):
        return body
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["style", "script", "head", "title", "xml"]):
        tag.decompose()
    lines = (" ".join(line.split()) for line in soup.get_text("\n").splitlines())
    return _BLANK_RUNS.sub("\n\n", "\n".join(lines)).strip()


def _mail_markdown(subject: str, sender: str, date: str, body: str) -> str:
    return f"# {subject}\n\nFrom: {sender}\nDate: {date}\n\n## Body\n\n{body.strip()}\n".strip()


def convert_eml(path: Path) -> ConversionResult:
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                body = part.get_content()
                break
            if ctype == "text/html" and not body:
                body = part.get_content()
    else:
        body = msg.get_content()
    text = _mail_markdown(
        str(msg.get("subject", "")),
        str(msg.get("from", "")),
        str(msg.get("date", "")),
        html_body_text(str(body)),
    )
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, "email-stdlib")
    return ConversionResult(text, "email-stdlib")


def _read_msg(path: Path, override_encoding: str | None = None) -> str:
    import extract_msg

    kwargs = {"overrideEncoding": override_encoding} if override_encoding else {}
    msg = extract_msg.Message(str(path), **kwargs)
    try:
        body = msg.body or msg.htmlBody or ""
        if isinstance(body, bytes):
            body = decode_text(body)[0]
        return _mail_markdown(
            msg.subject or "", msg.sender or "", str(msg.date or ""), html_body_text(body)
        )
    finally:
        msg.close()


def convert_msg(path: Path) -> ConversionResult:
    warnings: list[str] = []
    text = _read_msg(path)
    if "�" in text:
        retry = _read_msg(path, FALLBACK)
        if retry.count("�") < text.count("�"):
            text, warnings = retry, [f"encoding: {FALLBACK} (override)"]
    if "�" in text:
        return failed("extract-msg", "encoding_undecodable", "replacement characters remain")
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, "extract-msg", warnings)
    return ConversionResult(text, "extract-msg", warnings=warnings)


def _html_part(path: Path) -> str | None:
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.compat32)
    for part in msg.walk():
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if not isinstance(payload, bytes):
            continue
        charset = part.get_content_charset()
        # Word declares charset="unicode" (no codec); a BOM means UTF-16 for decode_text.
        if charset and not payload.startswith((b"\xff\xfe", b"\xfe\xff")):
            try:
                return payload.decode(charset)
            except (LookupError, UnicodeDecodeError):
                pass
        return decode_text(payload)[0]
    return None


def convert_mhtml(path: Path) -> ConversionResult:
    """Only the HTML part is text; images in the archive are out of scope like image files."""
    from ffcore.knowledge.convert import office

    try:
        html = _html_part(path)
    except UndecodableText as exc:
        return failed("mhtml", "encoding_undecodable", str(exc))
    if not html:
        return empty("", "mhtml")
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / f"{path.stem}.html"
        page.write_bytes(html.encode("utf-8"))
        result = office.convert_with_docling(page)
    if result.ok:
        return ConversionResult(result.text_md, f"mhtml+{result.method}")
    text = html_body_text(html).strip()
    warnings = [f"docling: {result.error_code or result.status}", *result.warnings]
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, "mhtml+html_text", warnings)
    return ConversionResult(text, "mhtml+html_text", warnings=warnings)


_TAG = re.compile(r"<[^>]+>")


def _mx_labels(xml: str) -> list[str]:
    labels = []
    for match in re.finditer(r'\bvalue="([^"]*)"', xml):
        value = unescape(_TAG.sub("", unescape(match.group(1)))).strip()
        if value:
            labels.append(value)
    return labels


def _drawio(path: Path) -> str:
    raw = decode_text(path.read_bytes())[0]
    labels: list[str] = []
    for match in re.finditer(r"<diagram[^>]*>([^<]+)</diagram>", raw):
        payload = match.group(1).strip()
        try:
            labels.extend(_mx_labels(inflate_raw(base64.b64decode(payload)).decode()))
        except (ValueError, zlib.error, UnicodeDecodeError):
            labels.extend(_mx_labels(payload))
    labels.extend(_mx_labels(raw))
    return "\n".join(f"- {label}" for label in dict.fromkeys(labels))


def _vsdx(path: Path) -> str:
    labels = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("visio/pages/page") and name.endswith(".xml"):
                for element in ElementTree.fromstring(archive.read(name)).iter():
                    if element.tag.endswith("Text") and (element.text or "").strip():
                        labels.append(element.text.strip())
    return "\n".join(f"- {label}" for label in labels)


def convert_diagram(path: Path) -> ConversionResult:
    method = "vsdx-stdlib" if path.suffix.lower() == ".vsdx" else "drawio-stdlib"
    try:
        text = (_vsdx(path) if method == "vsdx-stdlib" else _drawio(path)).strip()
    except LimitExceeded as exc:
        return failed(method, exc.code, str(exc))
    if len(text) < MIN_TEXT_CHARS:
        return empty(text, method)
    return ConversionResult(f"# Diagram: {path.name}\n\n{text}\n", method)
