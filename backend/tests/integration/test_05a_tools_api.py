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


# --- slice 3: discover, action settings, invoke (real MCP server on 127.0.0.1) ---


@pytest.fixture(scope="module")
def mcp_server():
    from tests import mcp_fixture

    fixture, uv = mcp_fixture.start()
    yield fixture
    uv.should_exit = True


@pytest.fixture
def loopback(settings):
    # The fixture MCP server is on 127.0.0.1: allowed as internal for these tests only.
    settings.allowed_internal_hosts = [*settings.allowed_internal_hosts, "127.0.0.0/8"]
    return settings


def _registered(world, mcp_server, key="fixture", **extra):
    body = {**_tool(key=key, url=mcp_server.url), **extra}
    response = world["admin"].post(tools_url(world), json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _discover(world, tool):
    response = world["admin"].post(tools_url(world, tool["id"]) + "/discover")
    assert response.status_code == 200, response.text
    return response.json()


def test_05a_discover_writes_actions_closed(world, mcp_server, loopback):
    tool = _discover(world, _registered(world, mcp_server))
    assert tool["status"] == "discovered" and tool["discovered_at"] and not tool["last_error_code"]
    actions = {a["name"]: a for a in tool["actions"]}
    assert {"echo", "whoami", "big", "slow", "fail"} <= set(actions)
    # K-05a-0002 S8: a newly discovered action is off and needs approval until an admin says so.
    assert all(not a["enabled"] and a["needs_approval"] for a in actions.values())
    assert actions["echo"]["input_schema"]["properties"]["text"]["type"] == "string"


def test_05a_rediscover_keeps_settings_and_marks_missing(world, mcp_server, loopback, pg):
    tool = _discover(world, _registered(world, mcp_server))
    url = tools_url(world, tool["id"]) + "/actions/echo"
    edited = world["admin"].patch(url, json={"enabled": True, "needs_approval": False})
    assert edited.status_code == 200, edited.text
    pg.execute(
        "INSERT INTO tool_actions (id, tool_id, name, input_schema, needs_approval, enabled)"
        " VALUES (gen_random_uuid(), %s, 'gone', '{}', false, true)",
        (tool["id"],),
    )
    again = {a["name"]: a for a in _discover(world, tool)["actions"]}
    assert again["echo"]["enabled"] and not again["echo"]["needs_approval"]
    assert again["gone"]["status"] == "missing" and not again["gone"]["enabled"]


def test_05a_discover_failure_is_recorded(world, loopback):
    body = _tool(key="down", url="http://127.0.0.1:9/mcp")
    tool = world["admin"].post(tools_url(world), json=body).json()
    result = _discover(world, tool)
    assert result["status"] == "error" and result["last_error_code"] == "tool_unreachable"


def test_05a_action_settings(world, mcp_server, loopback):
    tool = _discover(world, _registered(world, mcp_server))
    url = tools_url(world, tool["id"]) + "/actions/echo"
    response = world["admin"].patch(url, json={"timeout_s": 10, "max_calls_per_run": 3})
    assert response.status_code == 200
    assert (response.json()["timeout_s"], response.json()["max_calls_per_run"]) == (10, 3)
    assert world["developer"].patch(url, json={"enabled": True}).status_code == 403
    missing = tools_url(world, tool["id"]) + "/actions/nope"
    assert world["admin"].patch(missing, json={"enabled": True}).status_code == 404


def test_05a_invoke_returns_result_and_is_audited(world, mcp_server, loopback, pg):
    auth = {"type": "basic", "username": USERNAME, "password": PASSWORD}
    tool = _discover(world, _registered(world, mcp_server, auth=auth))
    url = tools_url(world, tool["id"]) + "/actions/echo/invoke"
    response = world["admin"].post(url, json={"arguments": {"text": "hello"}})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["text"] == "hello" and not body["truncated"] and not body["is_error"]
    rows = audit_rows(pg, "invoke_tool_action")
    assert rows and rows[-1][1] == "success"
    assert all(PASSWORD not in str(r) and "hello" not in str(r[2]) for r in rows)
    assert world["developer"].post(url, json={"arguments": {"text": "x"}}).status_code == 403


def test_05a_invoke_errors_are_coded(world, mcp_server, loopback):
    tool = _discover(world, _registered(world, mcp_server))
    base = tools_url(world, tool["id"]) + "/actions"
    unknown = world["admin"].post(f"{base}/nope/invoke", json={"arguments": {}})
    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "action_not_found"
    slow = world["admin"].patch(f"{base}/slow", json={"timeout_s": 1})
    assert slow.status_code == 200
    late = world["admin"].post(f"{base}/slow/invoke", json={"arguments": {"seconds": 3}})
    assert late.status_code == 502 and late.json()["error"]["code"] == "tool_timeout"


def test_05a_invoke_openapi_kind_not_implemented(world, mcp_server, loopback, pg):
    tool = _registered(world, mcp_server, key="openapi-tool", kind="openapi")
    pg.execute(
        "INSERT INTO tool_actions (id, tool_id, name, input_schema, needs_approval, enabled)"
        " VALUES (gen_random_uuid(), %s, 'op', '{}', false, true)",
        (tool["id"],),
    )
    url = tools_url(world, tool["id"]) + "/actions/op/invoke"
    response = world["admin"].post(url, json={"arguments": {}})
    assert response.status_code == 501


def test_05a_read_mode_get_parity(world, make_user, client_factory):
    """Read access sees exactly what edit access sees (03a rule), including masked secrets."""
    project = world["project"]
    import uuid as _uuid

    _, reader = make_user(memberships={_uuid.UUID(project): ("admin", "read")})
    read = client_factory(reader)
    auth = {"type": "basic", "username": USERNAME, "password": PASSWORD}
    tool = world["admin"].post(tools_url(world), json=_tool(auth=auth)).json()
    for url in (tools_url(world), tools_url(world, tool["id"])):
        edit_response, read_response = world["admin"].get(url), read.get(url)
        assert edit_response.status_code == 200
        assert read_response.content == edit_response.content, url
    assert read.post(tools_url(world), json=_tool(key="other")).status_code == 403


# --- review r1 MAJOR-2: endpoint_url is scheme + host + port + path only; credentials go into
# auth (encrypted, masked). Nothing of a refused URL reaches the database or the audit log.

URL_SECRET = "dummy-not-secret-url-secret-0123"


@pytest.mark.parametrize(
    "url",
    [
        f"http://user:{URL_SECRET}@mcp-search:8000/mcp",
        f"http://{URL_SECRET}@mcp-search:8000/mcp",
        f"http://mcp-search:8000/mcp?api_key={URL_SECRET}",
        "http://mcp-search:8000/mcp?",
        f"http://mcp-search:8000/mcp#{URL_SECRET}",
    ],
)
def test_05a_endpoint_url_credentials_refused(world, pg, url):
    response = world["admin"].post(tools_url(world), json=_tool(url=url))
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "endpoint_url_not_allowed"
    assert URL_SECRET not in response.text
    stored = pg.execute(
        "SELECT count(*) FROM tools WHERE project_id = %s", (world["project"],)
    ).fetchone()[0]
    assert stored == 0
    assert all(URL_SECRET not in str(row) for row in audit_rows(pg, "create_tool"))


def test_05a_endpoint_url_credentials_refused_on_update(world, pg):
    tool = world["admin"].post(tools_url(world), json=_tool()).json()
    for url in (
        f"http://u:{URL_SECRET}@mcp-search:8000/mcp",
        f"http://mcp-search:8000/mcp?token={URL_SECRET}",
    ):
        response = world["admin"].patch(tools_url(world, tool["id"]), json={"endpoint_url": url})
        assert response.status_code == 400, response.text
        assert response.json()["error"]["code"] == "endpoint_url_not_allowed"
    stored = pg.execute("SELECT endpoint_url FROM tools WHERE id = %s", (tool["id"],)).fetchone()
    assert stored[0] == MCP_SEARCH
    assert all(URL_SECRET not in str(row) for row in audit_rows(pg, "update_tool"))


# --- review r1 MAJOR-3: a custom auth header never names a transport header (closed list,
# KARARLAR "05a review r1 kararları" item 4); the name is an RFC 7230 token.

RESERVED = [
    "Host",
    "Content-Length",
    "Connection",
    "Transfer-Encoding",
    "Upgrade",
    "TE",
    "Trailer",
    "Keep-Alive",
    "Proxy-Authorization",
    "Proxy-Anything",
    "Authorization",
    "host",
    "X Api Key",
    "X-Api:Key",
]


@pytest.mark.parametrize("name", RESERVED)
def test_05a_reserved_header_name_refused(world, pg, name):
    auth = {"type": "header", "name": name, "value": TOKEN}
    response = world["admin"].post(tools_url(world), json=_tool(auth=auth))
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "header_name_not_allowed"
    stored = pg.execute(
        "SELECT count(*) FROM tools WHERE project_id = %s", (world["project"],)
    ).fetchone()[0]
    assert stored == 0


def test_05a_reserved_header_name_refused_on_update(world):
    tool = world["admin"].post(tools_url(world), json=_tool()).json()
    response = world["admin"].patch(
        tools_url(world, tool["id"]),
        json={"auth": {"type": "header", "name": "Host", "value": TOKEN}},
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "header_name_not_allowed"


def test_05a_business_header_name_accepted(world):
    auth = {"type": "header", "name": "X-Api-Key", "value": TOKEN}
    response = world["admin"].post(tools_url(world), json=_tool(auth=auth))
    assert response.status_code == 201, response.text
    assert response.json()["auth"] == {"type": "header", "name": "X-Api-Key", "value": "***"}
