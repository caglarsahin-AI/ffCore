"""FOLLOWUP-202 (KARARLAR 'triage-1 plan kararları' S-1), on both vector drivers.

A project admin is the only one who changes a document's ACL, so a user-only document it
cannot read (C15) must stay manageable: the single document GET, PATCH and DELETE skip the read
filter for an admin (a superadmin's grant is admin too), by the same rule as the same-name
upload (K-04B-0013 A, `_manages_acl`). Everyone else still gets 404, exactly like a missing
document; the list, search and ingest report keep the C15 filter for the admin too.
"""

from tests.integration import test_04a_review_r1_acl as r1
from tests.integration.test_04a_review_r1_acl import PROSE, SECRET_TEXT, drain, kb_url, upload

backend = r1.backend
world = r1.world

BODY = "# Kişi\n\n" + (PROSE + SECRET_TEXT + " ") * 6


def user_only(w):
    """A document only the analyst may read (acl_users), uploaded by the admin."""
    first = upload(w, w["admin"], "kisi.md", BODY, acl_users=w["analyst_id"])
    assert first.status_code == 202, first.text
    drain(w)
    return first.json()["data"][0]["document"]["id"]


def doc_url(w, document_id):
    return kb_url(w, f"/{w['kb']}/documents/{document_id}")


def test_trj_202_admin_reads_user_only_document(world):
    doc_id = user_only(world)
    got = world["admin"].get(doc_url(world, doc_id))
    assert got.status_code == 200, got.text
    assert got.json()["acl_users"] == [world["analyst_id"]]


def test_trj_202_admin_patches_user_only_document(world):
    doc_id = user_only(world)
    url = doc_url(world, doc_id)
    dated = world["admin"].patch(url, json={"updated_at_source": "2026-01-02T00:00:00Z"})
    assert dated.status_code == 200, dated.text
    opened = world["admin"].patch(url, json={"acl_roles": ["admin"], "acl_users": []})
    assert opened.status_code == 200, opened.text
    assert (opened.json()["acl_roles"], opened.json()["acl_users"]) == (["admin"], [])
    assert world["analyst"].get(url).status_code == 404  # the ACL change reached the read rule


def test_trj_202_admin_deletes_user_only_document(world):
    doc_id = user_only(world)
    assert world["admin"].delete(doc_url(world, doc_id)).status_code == 204
    assert world["analyst"].get(doc_url(world, doc_id)).status_code == 404


def test_trj_202_other_analyst_still_404(world):
    doc_id = user_only(world)
    url = doc_url(world, doc_id)
    for response in (
        world["peer"].get(url),
        world["peer"].patch(url, json={"updated_at_source": None}),
        world["peer"].delete(url),
    ):
        assert response.status_code == 404, response.text
        assert response.json()["error"]["code"] == "document_not_found"
        assert SECRET_TEXT not in response.text
    assert world["analyst"].get(url).status_code == 200  # nothing changed for the reader


def test_trj_202_superadmin_manages_user_only_document(world, make_user, client_factory):
    doc_id = user_only(world)
    url = doc_url(world, doc_id)
    _, reader_email = make_user(superadmin="read")
    _, editor_email = make_user(superadmin="edit")
    assert client_factory(reader_email).get(url).status_code == 200
    assert client_factory(reader_email).delete(url).status_code == 403  # read access: no write
    assert client_factory(editor_email).delete(url).status_code == 204


def test_trj_202_list_keeps_c15_filter_for_admin(world):
    doc_id = user_only(world)
    listed = world["admin"].get(kb_url(world, f"/{world['kb']}/documents"))
    assert listed.status_code == 200, listed.text
    assert doc_id not in [d["id"] for d in listed.json()["data"]]
