"""05a slice 2: the tool registry API (real app, real database).

Acceptance 6 (basic credentials never shown), 8 (SSRF at registration), the forward_user
internal-host rule (C3), roles and audit.
"""

import pytest

from tests.integration.conftest import audit_rows

API = "/api/v1"
USERNAME = "dummy-not-secret-tool-user"
PASSWORD = "dummy-not-secret-tool-password-0123"
TOKEN = "dummy-not-secret-tool-bearer-0123456789"
MCP_SEARCH = "http://mcp-search:8000/mcp"


@pytest.fixture
def settings(app, app_settings):
    from ffcore.core.config import get_settings

    value = app_settings.model_copy(
        update={
            "allowed_internal_hosts": [*app_settings.allowed_internal_hosts, "mcp-search"],
            "egress_allowlist": ["tools.example.com"],
        }
    )
    app.dependency_overrides[get_settings] = lambda: value
    return value


@pytest.fixture
def world(make_user, make_project, client_factory, settings):
    project = make_project()
    _, admin = make_user(memberships={project: ("admin", "edit")})
    _, developer = make_user(memberships={project: ("developer", "edit")})
    _, analyst = make_user(memberships={project: ("analyst", "edit")})
    return {
        "project": str(project),
        "admin": client_factory(admin),
        "developer": client_factory(developer),
        "analyst": client_factory(analyst),
    }


def tools_url(world, tool_id=""):
    base = f"{API}/projects/{world['project']}/tools"
    return f"{base}/{tool_id}" if tool_id else base


def _tool(key="sql", url=MCP_SEARCH, auth=None):
    return {
        "key": key,
        "name": "Tool",
        "kind": "mcp",
        "endpoint_url": url,
        "auth": auth or {"type": "none"},
    }


def test_05a_6_basic_credentials_never_shown(world, pg):
    auth = {"type": "basic", "username": USERNAME, "password": PASSWORD}
    response = world["admin"].post(tools_url(world), json=_tool(auth=auth))
    assert response.status_code == 201, response.text
    tool = response.json()
    assert tool["auth"] == {"type": "basic", "username": "***", "password": "***"}
    fetched = world["admin"].get(tools_url(world, tool["id"])).json()
    listed = world["developer"].get(tools_url(world)).json()["data"]
    for body in (str(tool), str(fetched), str(listed)):
        assert USERNAME not in body and PASSWORD not in body
    stored = pg.execute(
        "SELECT auth_config_encrypted FROM tools WHERE id = %s", (tool["id"],)
    ).fetchone()[0]
    assert USERNAME.encode() not in bytes(stored) and PASSWORD.encode() not in bytes(stored)
    for _, _, after in audit_rows(pg, "create_tool"):
        assert USERNAME not in str(after) and PASSWORD not in str(after)


def test_05a_6_masked_value_keeps_stored_secret(world):
    auth = {"type": "bearer", "token": TOKEN}
    tool = world["admin"].post(tools_url(world), json=_tool(auth=auth)).json()
    response = world["admin"].patch(
        tools_url(world, tool["id"]),
        json={"name": "Renamed", "auth": {"type": "bearer", "token": "***"}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["auth"] == {"type": "bearer", "token": "***"}
    assert response.json()["name"] == "Renamed"


def test_05a_6_masked_value_on_create_refused(world):
    response = world["admin"].post(
        tools_url(world), json=_tool(auth={"type": "bearer", "token": "***"})
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_auth_config"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/mcp",
        "http://10.0.0.5/mcp",
        "http://169.254.169.254/latest",
        "https://not-allowed.example.org/mcp",
    ],
)
def test_05a_8_ssrf_endpoints_refused_at_registration(world, url):
    response = world["admin"].post(tools_url(world), json=_tool(url=url))
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"].startswith("egress_")


def test_05a_8_internal_mcp_search_accepted(world):
    response = world["admin"].post(tools_url(world), json=_tool(url=MCP_SEARCH))
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "registered"


def test_05a_8_ssrf_refused_on_update(world):
    tool = world["admin"].post(tools_url(world), json=_tool()).json()
    response = world["admin"].patch(
        tools_url(world, tool["id"]), json={"endpoint_url": "http://169.254.169.254/latest"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"].startswith("egress_")


def test_05a_forward_user_external_host_400(world):
    # The host passes the egress allowlist, but forward_user only goes to internal services (C3).
    response = world["admin"].post(
        tools_url(world),
        json=_tool(url="https://tools.example.com/mcp", auth={"type": "forward_user"}),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "forward_user_not_internal"


def test_05a_forward_user_internal_accepted(world):
    response = world["admin"].post(
        tools_url(world), json=_tool(key="search", auth={"type": "forward_user"})
    )
    assert response.status_code == 201, response.text
    assert response.json()["auth"] == {"type": "forward_user"}


def test_05a_tool_roles(world):
    assert world["analyst"].get(tools_url(world)).status_code == 403
    assert world["developer"].get(tools_url(world)).status_code == 200
    assert world["developer"].post(tools_url(world), json=_tool()).status_code == 403
    assert world["admin"].post(tools_url(world), json=_tool()).status_code == 201


def test_05a_tool_key_unique_and_soft_delete(world):
    first = world["admin"].post(tools_url(world), json=_tool()).json()
    again = world["admin"].post(tools_url(world), json=_tool())
    assert again.status_code == 409 and again.json()["error"]["code"] == "tool_key_taken"
    assert world["admin"].delete(tools_url(world, first["id"])).status_code == 204
    assert world["admin"].get(tools_url(world, first["id"])).status_code == 404
    assert world["admin"].post(tools_url(world), json=_tool()).status_code == 201


def test_05a_openapi_kind_registered_but_not_callable_yet(world):
    response = world["admin"].post(tools_url(world), json={**_tool(), "kind": "openapi"})
    assert response.status_code == 201
    assert response.json()["kind"] == "openapi"
