"""What never enters a knowledge base, and Kapı 0 for manual uploads (one definition).

Adapted from PayCore `ingest/scope.py` and `sync.gate0_file_rule` (measured there): archives,
spreadsheets, csv/tsv, sql, images and wsdl are out of scope; binaries have no text. 04a adds
two explicit skips for what it does not convert yet (never a silent drop, ARCH-06): video
(`video_disabled`, VIDEO_TRANSCRIPT_ENABLED in 04b) and old Office binaries
(`libreoffice_unavailable`, 04b). `.doc` is not refused here: a "single file web page" saved as
.doc is MHTML, and only content sniffing in convert can tell.
"""

from pathlib import PurePath

ARCHIVE = frozenset({"zip", "rar", "7z", "tar", "gz", "tgz", "bz2", "xz"})
# Tabular data belongs to text-to-SQL, not to RAG.
SPREADSHEET = frozenset({"xlsx", "xlsm", "xls", "xlsb", "ods"})
TABULAR = frozenset({"csv", "tsv"})
QUERY = frozenset({"sql"})
# PayCore measurement: 1.434 PNG produced 46 usable chunks.
IMAGE = frozenset({"png", "jpg", "jpeg", "jfif"})
SERVICE_DEFINITION = frozenset({"wsdl"})
OUT_OF_SCOPE = ARCHIVE | SPREADSHEET | TABULAR | QUERY | IMAGE | SERVICE_DEFINITION

BINARY = frozenset(
    {"apk", "jar", "aar", "bak", "exe", "dll", "so", "bin", "dmg", "msi", "iso"}
    | {"overflow", "emf", "bmpr", "mpp", "url"}
)
VIDEO = frozenset({"mp4", "m4a", "mov", "mkv", "avi", "wav", "mp3"})
OLD_OFFICE = frozenset({"ppt", "xls", "vsd"})

# Size limits (PayCore attachment_plaintext_max_mb / attachment_max_mb).
PLAINTEXT = frozenset({"log", "txt", "json", "xml", "yaml", "yml"})
PLAINTEXT_MAX_BYTES = 5 * 1024 * 1024
MAX_BYTES = 500 * 1024 * 1024

Verdict = tuple[str, str | None]


def extension(filename: str) -> str:
    return PurePath(filename).suffix.lower().lstrip(".")


def max_bytes(filename: str) -> int:
    """Kapı 0's size limit for this file; uploads stream against it (review r1 MAJOR-5)."""
    return PLAINTEXT_MAX_BYTES if extension(filename) in PLAINTEXT else MAX_BYTES


def gate0_upload(filename: str, size: int) -> Verdict:
    """Kapı 0 for a manual upload: format scope and size. No date rule (an upload has no source
    date; that part of Kapı 0 belongs to the source connectors, 16)."""
    ext = extension(filename)
    if ext in BINARY:
        return "skipped", "binary"
    if ext in OUT_OF_SCOPE:
        return "skipped", "out_of_scope"
    if ext in VIDEO:
        return "skipped", "video_disabled"
    if ext in OLD_OFFICE:
        return "skipped", "libreoffice_unavailable"
    if size > max_bytes(filename):
        return "skipped", "too_large"
    return "ok", None
