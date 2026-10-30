"""FOLLOWUP-103 (decision A, K-04aWR-0005): a project the caller cannot see answers 404.

A caller who is not a member of the project gets exactly the answer a missing project gets
(404 `project_not_found`, same body), so a project id leaks nothing. A member whose role is too
low still gets 403 `insufficient_role`. The real reason is kept in the audit row, never in the
response.
"""

import re
import uuid

import pytest

from ffcore.main import app as _app
from tests.integration.conftest import audit_rows
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    definition,
    source,
    turn,
)

API = "/api/v1"
NOT_FOUND = {"error": {"message": "Project not found.", "type": "not_found_error",
                       "code": "project_not_found"}}  # fmt: skip


def _project_routes():
    """Every operation whose path carries {project_id}, straight from the OpenAPI document."""
    for path, ops in _app.openapi()["paths"].items():
        if "{project_id}" not in path:
            continue
        for method in ops:
            if method in ("get", "post", "put", "patch", "delete"):
                yield method, path


ROUTES = sorted(set(_project_routes()))


def _fill(path: str, project_id) -> str:
    """The project id in its slot; any other path parameter gets a placeholder that exists nowhere."""
    path = path.replace("{project_id}", str(project_id))
    return re.sub(r"\{[a-z_]+\}", lambda m: str(uuid.uuid4()) if m[0].endswith("_id}") else "x", path)


def _call(client, method, url):
    kwargs = {"json": {}} if method in ("post", "put", "patch") else {}
    return client.request(method.upper(), url, **kwargs)


@pytest.fixture
def stranger(make_user, make_project, client_factory):
    """Admin (edit) of another project; no membership in the target."""
    user_id, email = make_user(memberships={make_project(): ("admin", "edit")})
    return user_id, client_factory(email)


def test_03a_nonmember_route_list_covers_followup_103():
    """The twelve routes of the F10 finding (state/pr/18-e2e.md) are in the scanned list."""
    routes = set(ROUTES)
    base = f"{API}/projects/{{project_id}}"
    f10 = {
        ("get", f"{base}/knowledge-bases"),
        ("get", f"{base}/knowledge-bases/{{kb_id}}"),
        ("get", f"{base}/knowledge-bases/{{kb_id}}/documents/{{document_id}}"),
        ("get", f"{base}/tools"),
        ("get", f"{base}/tools/{{tool_id}}"),
        ("get", f"{base}/agents"),
        ("get", f"{base}/runs"),
        ("get", f"{base}/runs/{{run_id}}"),
        ("get", f"{base}/runs/{{run_id}}/events"),
        ("post", f"{base}/knowledge-bases/{{kb_id}}/search"),
        ("post", f"{base}/tools/{{tool_id}}/actions/{{action_name}}/invoke"),
        ("post", f"{base}/agents/{{agent_key}}/runs"),
    }
    assert f10 <= routes, sorted(f10 - routes)


@pytest.mark.parametrize(("method", "path"), ROUTES, ids=[f"{m} {p}" for m, p in ROUTES])
def test_03a_nonmember_gets_404_like_missing_project(method, path, stranger, make_project):
    _, client = stranger
    target = make_project()
    nonmember = _call(client, method, _fill(path, target))
    missing = _call(client, method, _fill(path, uuid.uuid4()))
    assert (nonmember.status_code, nonmember.json()) == (404, NOT_FOUND), nonmember.text
    assert (missing.status_code, missing.json()) == (404, NOT_FOUND), missing.text


def test_03a_member_with_low_role_still_403(make_user, make_project, client_factory):
    project = make_project()
    _, email = make_user(memberships={project: ("analyst", "edit")})
    response = client_factory(email).post(
        f"{API}/projects/{project}/members", json={"user_id": str(uuid.uuid4()), "role": "analyst"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_role"


def test_03a_deleted_project_404_for_former_member(make_user, make_project, client_factory, pg):
    project = make_project()
    _, email = make_user(memberships={project: ("admin", "edit")})
    pg.execute("UPDATE projects SET deleted_at = now() WHERE id = %s", (project,))
    response = client_factory(email).get(f"{API}/projects/{project}")
    assert (response.status_code, response.json()) == (404, NOT_FOUND)


def test_03a_nonmember_404_audits_real_reason(stranger, make_project, pg):
    user_id, client = stranger
    target, missing = make_project(), uuid.uuid4()
    client.get(f"{API}/projects/{target}")
    client.get(f"{API}/projects/{missing}")
    rows = [r for r in audit_rows(pg, "get_project", "denied") if r[0] == str(user_id)]
    reasons = {row[2]["reason"] for row in rows}
    assert reasons == {"not_member", "no_project"}
    assert all(row[2]["code"] == "project_not_found" for row in rows)
    project_ids = {
        str(r[0])
        for r in pg.execute(
            "SELECT project_id FROM audit_events WHERE action = 'get_project'"
            " AND outcome = 'denied' AND actor_id = %s",
            (str(user_id),),
        ).fetchall()
    }
    assert str(target) in project_ids  # the row says which project was probed


def test_03a_nonmember_404_agrees_with_06a_run_rule(
    make_user, make_project, client_factory, pg, harness, use_queue
):
    """06a: another user's run in your project is 404 `run_not_found`; a run in a project you
    are not in is 404 `project_not_found`. Neither is a 403, so neither confirms the run."""
    project = make_project()
    _, owner = make_user(memberships={project: ("user", "edit")})
    _, other = make_user(memberships={project: ("user", "edit")})
    _, outsider = make_user(memberships={make_project(): ("admin", "edit")})
    publish(pg, project, definition())
    ports = Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([source()]))
    use_queue(InlineQueue(harness, ports))
    run_id = post_run(client_factory(owner), project)[0][2]["run_id"]
    base = f"{API}/projects/{project}/runs/{run_id}"
    for path in ("", "/events"):
        member = client_factory(other).get(base + path)
        assert (member.status_code, member.json()["error"]["code"]) == (404, "run_not_found")
        stranger = client_factory(outsider).get(base + path)
        assert (stranger.status_code, stranger.json()) == (404, NOT_FOUND)
