"""13b acceptance 5: `make seed` is idempotent. A second seed finds every resource and uploads
no document again: a re-upload of the same bytes would still bump the document's version
(04a `unchanged`), so the seed recognises a live document by file name, content hash and,
when one is given, its source date (FOLLOWUP-101). No stack needed."""

import hashlib

from .seed import existing_upload

DATA = b"Madde 1 - Amac: deneme metni."
SHA = hashlib.sha256(DATA).hexdigest()


def _doc(name="a.txt", sha=SHA, date=None, doc_id="d1"):
    return {"id": doc_id, "filename": name, "sha256": sha, "updated_at_source": date}


def test_13b_5_same_file_is_not_uploaded_again():
    assert existing_upload([_doc()], "a.txt", DATA, None) == "d1"


def test_13b_5_changed_bytes_or_other_name_upload():
    assert existing_upload([_doc(sha="0" * 64)], "a.txt", DATA, None) is None
    assert existing_upload([_doc(name="b.txt")], "a.txt", DATA, None) is None
    assert existing_upload([], "a.txt", DATA, None) is None


def test_13b_5_source_date_must_match_when_given():
    dated = _doc(date="2025-09-01T00:00:00Z")
    assert existing_upload([dated], "a.txt", DATA, "2025-09-01") == "d1"
    assert existing_upload([_doc()], "a.txt", DATA, "2025-09-01") is None  # sets the date
    assert existing_upload([dated], "a.txt", DATA, "2025-10-01") is None
