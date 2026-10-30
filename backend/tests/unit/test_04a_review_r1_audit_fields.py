"""Review 04a r1 MAJOR-7 (K-04a-0017): every DocumentOut field is classified as safe for the
audit trail or masked, so a new field cannot slip into audit payloads unreviewed."""

from ffcore.api.knowledge import DOCUMENT_AUDIT_MASKED
from ffcore.api.knowledge_schemas import DocumentOut
from ffcore.core.audit import MASK, mask

SAFE = {
    "id",
    "kb_id",
    "size",
    "sha256",
    "status",
    "page_count",
    "acl_roles",
    "acl_users",
    "version",
    "language",
    "duplicate_of",
    "updated_at_source",  # a source date, no content (FOLLOWUP-101)
    "gate0",
    "gate1",
    "gate2",
    "convert_engine",
    "convert_seconds",
    "chunk_count",
    "created_at",
    "updated_at",
}


def test_04a_r1_7_document_fields_are_classified():
    fields = set(DocumentOut.model_fields)
    assert fields == SAFE | set(DOCUMENT_AUDIT_MASKED), fields ^ (SAFE | set(DOCUMENT_AUDIT_MASKED))
    assert not SAFE & set(DOCUMENT_AUDIT_MASKED)


def test_04a_r1_7_masking_reaches_nested_upload_items():
    payload = {
        "data": [
            {
                "outcome": "created",
                "document": {"id": "d1", "filename": "Ayse_K_10000000146.pdf", "error": "x"},
            }
        ]
    }
    masked = mask(payload, DOCUMENT_AUDIT_MASKED)
    item = masked["data"][0]["document"]
    assert item == {"id": "d1", "filename": MASK, "error": MASK}
