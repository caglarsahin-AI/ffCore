"""04b-1 r2 (K-04B-0007, KARARLAR '04b-1 r1 kararları'), on both vector drivers.

MINOR-2 (A): a document's ACL (`acl_roles`, `acl_users`, `acl_open` on PATCH) is changed only by
a project admin; analyst+write still corrects the other fields. NOTE-2: an upload of the same
name and bytes with another ACL (`unchanged`, FOLLOWUP-157) reaches the vector store too, so a
widened ACL is visible in search at once and a narrowed one is closed (Qdrant payload not stale).
"""

from tests.integration import test_04a_review_r1_acl as r1
from tests.integration.conftest import audit_rows
from tests.integration.test_04a_review_r1_acl import (
    PROSE,
    SECRET_TEXT,
    drain,
    kb_url,
    search,
    upload,
)

# 04a r1's fixtures: pgvector and Qdrant (`vectorstore` mark), admin/analyst/peer of a project.
backend = r1.backend
world = r1.world

BODY = "# Gizli\n\n" + (PROSE + SECRET_TEXT + " ") * 6


def doc_url(w, document_id):
    return kb_url(w, f"/{w['kb']}/documents/{document_id}")


def test_04b_r2_acl_change_is_admin_only(world, pg):
    item = upload(world, world["admin"], "ortak.md", BODY, acl_roles=["admin", "analyst"])
    url = doc_url(world, item.json()["data"][0]["document"]["id"])
    drain(world)
    assert search(world, world["analyst"])["hits"]
    assert search(world, world["peer"])["hits"]  # peer is an analyst too

    changes = ({"acl_open": True}, {"acl_roles": ["analyst"]}, {"acl_users": [world["analyst_id"]]})
    for body in changes:
        refused = world["analyst"].patch(url, json=body)
        assert refused.status_code == 403, refused.text
        assert refused.json()["error"]["code"] == "insufficient_role"
    assert audit_rows(pg, "update_document", "success", project=world["project"]) == []
    assert world["analyst"].get(url).json()["acl_roles"] == ["admin", "analyst"]

    corrected = world["analyst"].patch(url, json={"updated_at_source": "2026-01-02T00:00:00Z"})
    assert corrected.status_code == 200, corrected.text  # other fields stay analyst's

    narrowed = world["admin"].patch(url, json={"acl_roles": ["admin"]})
    assert narrowed.status_code == 200, narrowed.text
    assert search(world, world["analyst"])["hits"] == []
    opened = world["admin"].patch(url, json={"acl_open": True})
    assert opened.status_code == 200 and opened.json()["acl_roles"] == []
    assert search(world, world["analyst"])["hits"]


def test_04b_r2_same_bytes_widening_and_narrowing_reach_search(world):
    first = upload(world, world["admin"], "gizli.md", BODY, acl_roles="admin")
    assert first.status_code == 202, first.text
    drain(world)
    assert search(world, world["analyst"])["hits"] == []

    widened = upload(world, world["admin"], "gizli.md", BODY, acl_roles=["admin", "analyst"])
    assert widened.json()["data"][0]["outcome"] == "unchanged"
    assert world["queue"].jobs == []  # nothing re-indexed: the store got the ACL itself
    assert search(world, world["analyst"])["hits"]

    narrowed = upload(world, world["admin"], "gizli.md", BODY, acl_roles="admin")
    assert narrowed.json()["data"][0]["outcome"] == "unchanged"
    assert search(world, world["analyst"])["hits"] == []
    assert search(world, world["admin"])["hits"]
