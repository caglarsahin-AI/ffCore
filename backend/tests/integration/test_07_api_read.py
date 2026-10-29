"""07 slice 2: reading the approval queue (list, count, detail).

Project members from analyst up see the queue, whatever their access mode; `can_decide` says
whether this caller may approve (console session, `edit`, role at least `assigned_role`). The
decision routes come in slice 3.
"""

import uuid
from datetime import UTC, datetime

import pytest

from tests.dummy import SERVICE_TOKEN
from tests.integration.test_07_schema import _insert

P = "/api/v1/projects/{}/approvals"
SERVICE = {"Authorization": f"Bearer {SERVICE_TOKEN}"}


@pytest.fixture
def project(make_project):
    return make_project()


@pytest.fixture
def member(client_factory, make_user, project):
    def make(role, access="edit"):
        _, email = make_user(memberships={project: (role, access)})
        return client_factory(email)

    return make


def _ids(response):
    assert response.status_code == 200, response.text
    return {item["id"] for item in response.json()["data"]}


def test_07_list_only_this_project_and_status(pg, member, project, make_project):
    pending = _insert(pg, project)
    done = _insert(pg, project, status="approved", resolved_at=datetime.now(UTC))
    _insert(pg, make_project())  # another project's approval never shows
    client = member("analyst")
    assert _ids(client.get(P.format(project))) == {str(pending["id"]), str(done["id"])}
    assert _ids(client.get(P.format(project), params={"status": "pending"})) == {
        str(pending["id"])
    }
    assert client.get(P.format(project), params={"status": "waiting"}).status_code == 422


def test_07_count_pending(pg, member, project):
    for _ in range(3):
        _insert(pg, project)
    _insert(pg, project, status="expired", resolved_at=datetime.now(UTC))
    response = member("analyst", "read").get(P.format(project) + "/count")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "pending", "count": 3}


def test_07_detail_fields(pg, member, project):
    row = _insert(pg, project, assigned_role="developer")
    body = member("admin").get(P.format(project) + f"/{row['id']}").json()
    assert body["id"] == str(row["id"]) and body["run_id"] == str(row["run_id"])
    assert body["action"] == "mcp-sql__run_sql" and body["tool_key"] == "mcp-sql"
    assert body["arguments"] == {"sql": "SELECT 1"} and "args_hash" not in body
    assert body["status"] == "pending" and body["assigned_role"] == "developer"
    assert body["reason_from_model"] is None and body["can_decide"] is True


def test_07_detail_of_other_project_is_404(pg, member, project, make_project):
    other = _insert(pg, make_project())
    response = member("admin").get(P.format(project) + f"/{other['id']}")
    assert response.status_code == 404
    assert member("admin").get(P.format(project) + f"/{uuid.uuid4()}").status_code == 404


@pytest.mark.parametrize(
    ("role", "access", "assigned", "expected"),
    [
        ("admin", "edit", "analyst", True),
        ("analyst", "edit", "analyst", True),
        ("analyst", "edit", "developer", False),  # brief acceptance: analyst cannot
        ("admin", "read", "analyst", False),  # read access sees, never decides
    ],
)
def test_07_can_decide(pg, member, project, role, access, assigned, expected):
    row = _insert(pg, project, assigned_role=assigned)
    body = member(role, access).get(P.format(project) + f"/{row['id']}").json()
    assert body["can_decide"] is expected


def test_07_read_access_lists(pg, member, project):
    row = _insert(pg, project)
    client = member("analyst", "read")
    assert _ids(client.get(P.format(project))) == {str(row["id"])}
    assert client.get(P.format(project) + f"/{row['id']}").status_code == 200


def test_07_queue_needs_analyst_membership(pg, member, project, client_factory, make_user):
    _insert(pg, project)
    response = member("user").get(P.format(project))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"
    _, outsider = make_user()
    assert client_factory(outsider).get(P.format(project)).status_code == 403


def test_07_service_token_without_user_cannot_read(pg, project, client_factory):
    _insert(pg, project)
    response = client_factory().get(P.format(project), headers=SERVICE)
    assert (response.status_code, response.json()["error"]["code"]) == (403, "insufficient_role")
    assert client_factory().get(P.format(project)).status_code == 401
