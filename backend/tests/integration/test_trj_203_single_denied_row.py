"""FOLLOWUP-203 (KARARLAR 'triage-1 plan kararları' S-2 A): one refusal, one `denied` row.

Inside an `@audited` endpoint, authorize() does not write its own row; it hands its reason
(code, min_role, write) to the decorator, whose single row keeps the resource it is about.
A refusal before the endpoint (the route's RoleRequirement) has no decorator and keeps
authorize()'s `route` row. Both cases are counted here; the agent and upload paths are locked
in test_06b2_external_agent and test_04b_r3_upload_acl.
"""

from tests.integration import test_04a_review_r1_acl as r1
from tests.integration.test_04a_review_r1_acl import PROSE, drain, kb_url, upload

backend = r1.backend
world = r1.world


def denied_rows(pg, project):
    return pg.execute(
        "SELECT action, resource_type, resource_id, after->>'code', after->>'min_role'"
        " FROM audit_events WHERE project_id = %s AND outcome = 'denied' ORDER BY ts",
        (project,),
    ).fetchall()


def test_trj_203_acl_patch_refusal_is_one_row(world, pg):
    first = upload(world, world["admin"], "ortak.md", "# O\n\n" + PROSE * 6, acl_roles=["analyst"])
    assert first.status_code == 202, first.text
    drain(world)
    doc_id = first.json()["data"][0]["document"]["id"]
    url = kb_url(world, f"/{world['kb']}/documents/{doc_id}")
    refused = world["analyst"].patch(url, json={"acl_open": True})
    assert refused.status_code == 403, refused.text
    assert refused.json()["error"]["code"] == "insufficient_role"
    assert denied_rows(pg, world["project"]) == [
        ("update_document", "document", doc_id, "insufficient_role", "admin")
    ]


def test_trj_203_route_refusal_keeps_route_row(world, pg):
    refused = world["analyst"].post(kb_url(world), json={"key": "baska", "name": "Başka"})
    assert refused.status_code == 403, refused.text
    assert denied_rows(pg, world["project"]) == [
        ("create_knowledge_base", "route", None, "insufficient_role", "admin")
    ]
