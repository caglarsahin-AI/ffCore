"""04b-1 r3 (K-04B-0011, KARARLAR '04b-1 r2 kararları'), on both vector drivers.

A document's ACL is changed by a project admin only; the entry points are PATCH and an upload
under the same name, and both go through the same `authorize()` (403 `insufficient_role`).
MAJOR-1: a re-upload that sends another ACL is refused for a non-admin, with nothing written;
a re-upload without ACL fields keeps the document's ACL (the default applies to new documents
only). MAJOR-2: a same-name document the caller cannot read is never overwritten: 409
`document_name_taken`, content, version and ACL stay, the refusal is audited.
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

BODY = "# Ortak\n\n" + (PROSE + SECRET_TEXT + " ") * 6
OTHER = "# Başka\n\n" + (PROSE + "başka bir metin ") * 6


def document(w, client, document_id):
    return client.get(kb_url(w, f"/{w['kb']}/documents/{document_id}"))


def shared(w):
    """Admin uploads a document admin and analyst may read; returns its id."""
    first = upload(w, w["admin"], "ortak.md", BODY, acl_roles=["admin", "analyst"])
    assert first.status_code == 202, first.text
    drain(w)
    return first.json()["data"][0]["document"]["id"]


def state(w, document_id):
    body = document(w, w["admin"], document_id).json()
    return body["acl_roles"], body["acl_users"], body["version"], body["sha256"]


def test_04b_r3_u1_same_bytes_other_acl_refused_for_analyst(world, pg):
    doc_id = shared(world)
    before = state(world, doc_id)
    refused = upload(world, world["analyst"], "ortak.md", BODY, acl_open="true")
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "insufficient_role"
    assert state(world, doc_id) == before
    assert world["queue"].jobs == []
    assert audit_rows(pg, "upload_documents", "denied", project=world["project"])
    assert search(world, world["peer"])["hits"]  # the ACL reached nobody: peer still reads


def test_04b_r3_u2_new_bytes_other_acl_refused_for_analyst(world):
    doc_id = shared(world)
    before = state(world, doc_id)
    refused = upload(world, world["analyst"], "ortak.md", OTHER, acl_roles=["analyst"])
    assert refused.status_code == 403, refused.text
    assert state(world, doc_id) == before  # no new version, no content written
    assert world["queue"].jobs == []


def test_04b_r3_reupload_without_acl_keeps_the_acl(world):
    doc_id = shared(world)
    same = upload(world, world["analyst"], "ortak.md", BODY)
    assert same.status_code == 202, same.text
    assert same.json()["data"][0]["outcome"] == "unchanged"
    newer = upload(world, world["analyst"], "ortak.md", OTHER)
    assert newer.status_code == 202, newer.text
    assert newer.json()["data"][0]["outcome"] == "new_version"
    acl_roles, acl_users, version, _ = state(world, doc_id)
    assert (sorted(acl_roles), acl_users, version) == (["admin", "analyst"], [], 2)
    # Sending the same ACL again is not a change either.
    again = upload(world, world["analyst"], "ortak.md", OTHER, acl_roles=["analyst", "admin"])
    assert again.status_code == 202, again.text


def test_04b_r3_admin_changes_acl_by_upload(world):
    doc_id = shared(world)
    opened = upload(world, world["admin"], "ortak.md", BODY, acl_open="true")
    assert opened.status_code == 202, opened.text
    assert opened.json()["data"][0]["outcome"] == "unchanged"
    assert state(world, doc_id)[:2] == ([], [])
    narrowed = upload(world, world["admin"], "ortak.md", OTHER, acl_roles=["admin"])
    assert narrowed.status_code == 202, narrowed.text
    assert narrowed.json()["data"][0]["outcome"] == "new_version"
    drain(world)
    assert state(world, doc_id)[:3] == (["admin"], [], 2)
    assert search(world, world["analyst"], "başka bir metin")["hits"] == []


def test_04b_r3_u3_unreadable_name_is_taken(world, pg):
    first = upload(world, world["admin"], "yonetim.md", BODY, acl_roles=["admin"])
    doc_id = first.json()["data"][0]["document"]["id"]
    drain(world)
    before = state(world, doc_id)
    assert document(world, world["analyst"], doc_id).status_code == 404

    for form in ({"acl_open": "true"}, {}):
        taken = upload(world, world["analyst"], "yonetim.md", OTHER, **form)
        assert taken.status_code == 409, taken.text
        assert taken.json()["error"]["code"] == "document_name_taken"
        assert SECRET_TEXT not in taken.text
    assert state(world, doc_id) == before
    assert world["queue"].jobs == []
    assert len(audit_rows(pg, "upload_documents", "error", project=world["project"])) == 2

    admin = upload(world, world["admin"], "yonetim.md", OTHER)
    assert admin.status_code == 202, admin.text
    assert admin.json()["data"][0]["outcome"] == "new_version"
    assert state(world, doc_id)[:3] == (["admin"], [], 2)
