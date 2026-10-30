"""FOLLOWUP-113 (closed, K-07F-0002 A): `POST .../tools/sql-context` is a read, not a write.

mcp-sql's get_schema calls it on behalf of whoever runs the agent (forward_user, an OBO token
with `aud=[<tool_key>, "ffcore-backend"]`), and any project member may start a run
(api/runs.py). So every member role reads it; a non-member gets 404 like every project-scoped
resource. This pins that decision: narrowing it to developer/admin would break the SQL
assistant for the analysts who run it.
"""

import pytest

from ffcore.core.auth import sign_on_behalf_of
from tests.dummy import SERVICE_TOKEN
from tests.integration.test_05a_sql import TOOL_KEY, demo, settings, world  # noqa: F401


def _on_behalf(client_factory, settings, user_id, project_id):  # noqa: F811 - fixture name
    token = sign_on_behalf_of(
        user_id=str(user_id),
        project_id=str(project_id),
        audience=[TOOL_KEY, settings.obo_audience],
        settings=settings,
    )
    client = client_factory()
    client.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
    return client


@pytest.mark.parametrize("role", ["user", "analyst"])
def test_07f_6_sql_context_any_member_reads_on_behalf(
    world,  # noqa: F811 - the imported fixture
    settings,  # noqa: F811
    make_user,
    make_project,
    client_factory,
    role,
):
    url = f"/api/v1/projects/{world['project']}/tools/sql-context"
    body = {"tool_key": TOOL_KEY, "question": "yatak kapasitesi"}
    member_id, _ = make_user(memberships={world["project"]: (role, "edit")})
    member = _on_behalf(client_factory, settings, member_id, world["project"])
    response = member.post(url, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["tables"]
    # A non-member, also on behalf: 404, the project's existence does not leak.
    other = make_project()
    stranger_id, _ = make_user(memberships={other: ("admin", "edit")})
    stranger = _on_behalf(client_factory, settings, stranger_id, world["project"])
    missing = stranger.post(url, json=body)
    assert (missing.status_code, missing.json()["error"]["code"]) == (404, "project_not_found")
