"""Kapı 0 for source attachments, decided from the listing before any download (PayCore D1).

Order (first match wins; each skip is recorded with its reason, nothing is dropped silently):
1. empty name → `name_invalid`;
2. 04's format and size rule (`scope.gate0_upload`: binary, out_of_scope, video_disabled,
   libreoffice_unavailable, too_large; the limit is 5 MB for plain text, 500 MB otherwise);
3. the source date rule `ATTACHMENT_MIN_DATE` (only connectors have a source date): older →
   `stale`; an attachment without a date passes (the source did not say);
4. the duplicate rule is the engine's (`shared_from`, it needs the database).

A size the listing does not give cannot be judged here; the download is then bounded by the same
limit while streaming (`too_large` mid-stream, the partial file removed).
"""

from datetime import date, datetime

from ffcore.knowledge import scope

Verdict = tuple[str, str | None]


def decide(
    name: str, size: int | None, modified_at: datetime | None, *, min_date: date | None
) -> Verdict:
    if not name or not name.strip():
        return "skipped", "name_invalid"
    status, reason = scope.gate0_upload(name, size if size is not None else 0)
    if status == "skipped":
        return status, reason
    if min_date is not None and modified_at is not None and modified_at.date() < min_date:
        return "skipped", "stale"
    return "ok", None


def max_bytes(name: str) -> int:
    """The streaming bound for an attachment whose listing gave no size."""
    return scope.max_bytes(name)
