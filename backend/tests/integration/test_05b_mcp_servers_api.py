"""05b D2: the published MCP server registry API (real app, real database).

Acceptance 1 (spec in, operations listed, selection), 6 (upstream only to the registered host;
platform services refused), roles, audit, masking, self-consumption (tools row) and S5
(`tools.kind=openapi` refused: OpenAPI is consumed only through a published server).
"""

import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.mcp_publish_support import *  # noqa: F403 - fixtures
from tests.integration.mcp_publish_support import (
    API,
    SIX,
    UPSTREAM_TOKEN,
    create,
    openapi_body,
    publish,
    servers_url,
)


def test_05b_1_spec_upload_lists_operations(world, upstream, pg):
    server = create(world, openapi_body(upstream.url))
    assert server["source_kind"] == "openapi" and server["status"] == "draft"
    assert server["access"] == "internal" and server["guardrail_mode"] == "monitor"
    assert server["guardrail_policy_key"] == "default"
    assert server["endpoint_path"] == f"/mcp/{server['key']}/"
    assert server["exposed_operations"] == []
    ops = {op["name"]: op for op in server["operations"]}
    assert sorted(ops) == SIX
    assert all(op["exposable"] and not op["exposed"] for op in ops.values())
    assert server["upstream_auth"] == {"type": "bearer", "token": "***"}
    stored = pg.execute(
        "SELECT spec_encrypted, upstream_auth_encrypted FROM mcp_servers WHERE id = %s",
        (server["id"],),
    ).fetchone()
    assert b"createChart" not in bytes(stored[0])
    assert UPSTREAM_TOKEN.encode() not in bytes(stored[1])
    rows = audit_rows(pg, "create_mcp_server", project=world["project"])
    # The catalog (operation names) is what admins see; the document and the token are not.
    assert rows and UPSTREAM_TOKEN not in str(rows) and "Sentetik örnek" not in str(rows)


def test_05b_1_select_rename_and_keep_selection_on_spec_reload(world, upstream):
    server = create(world, openapi_body(upstream.url))
    url = servers_url(world, server["id"])
    patched = world["admin"].patch(
        url,
        json={
            "exposed_operations": ["searchDashboards", "createChart"],
            "aliases": {"searchDashboards": {"name": "find_dashboard", "description": "Find."}},
        },
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["exposed_operations"] == ["createChart", "searchDashboards"]
    alias = {op["name"]: op for op in body["operations"]}["searchDashboards"]
    assert alias["alias"] == "find_dashboard" and alias["alias_description"] == "Find."
    reloaded = world["admin"].put(url + "/spec", json={"spec": openapi_body(upstream.url)["spec"]})
    assert reloaded.status_code == 200, reloaded.text
    assert reloaded.json()["exposed_operations"] == ["createChart", "searchDashboards"]


def test_05b_1_selection_errors_are_coded(world, upstream):
    url = servers_url(world, create(world, openapi_body(upstream.url))["id"])
    unknown = world["admin"].patch(url, json={"exposed_operations": ["nope"]})
    assert unknown.status_code == 422 and unknown.json()["error"]["code"] == "operation_unknown"
    clash = world["admin"].patch(url, json={"aliases": {"listCharts": {"name": "createChart"}}})
    assert clash.status_code == 422 and clash.json()["error"]["code"] == "alias_conflict"
    bad = world["admin"].patch(url, json={"aliases": {"listCharts": {"name": "has space"}}})
    assert bad.status_code == 422
    policy = world["admin"].patch(url, json={"guardrail_policy_key": "missing"})
    assert policy.status_code == 422
    assert policy.json()["error"]["code"] == "guardrail_policy_not_found"


def test_05b_1_spec_reload_losing_a_selected_operation_fails_loud(world, upstream):
    server = publish(world, upstream.url, exposed=["createChart"])
    spec = openapi_body(upstream.url)["spec"].replace("createChart", "makeChart")
    response = world["admin"].put(servers_url(world, server["id"], "/spec"), json={"spec": spec})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "exposed_operation_missing"
    again = world["admin"].get(servers_url(world, server["id"])).json()
    assert "createChart" in {op["name"] for op in again["operations"]}


def test_05b_1_bad_spec_is_422_with_its_code(world, upstream):
    body = openapi_body(upstream.url) | {"spec": '{"swagger": "2.0"}'}
    response = world["admin"].post(servers_url(world), json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "spec_version_unsupported"
    missing = openapi_body(upstream.url)
    missing.pop("spec")
    response = world["admin"].post(servers_url(world), json=missing)
    assert response.status_code == 422 and response.json()["error"]["code"] == "spec_required"


def test_05b_key_is_global_and_reusable_after_delete(
    world, upstream, make_project, make_user, client_factory
):
    shared = f"shared-{uuid.uuid4().hex[:8]}"
    server = create(world, openapi_body(upstream.url, key=shared))
    other = make_project()
    _, admin = make_user(memberships={other: ("admin", "edit")})
    elsewhere = client_factory(admin).post(
        f"{API}/projects/{other}/mcp-servers", json=openapi_body(upstream.url, key=shared)
    )
    assert elsewhere.status_code == 409
    assert elsewhere.json()["error"]["code"] == "mcp_server_key_taken"
    assert world["admin"].delete(servers_url(world, server["id"])).status_code == 204
    assert world["admin"].get(servers_url(world, server["id"])).status_code == 404
    assert create(world, openapi_body(upstream.url, key=shared))["key"] == shared


def test_05b_roles(world, upstream):
    server = create(world, openapi_body(upstream.url))
    assert world["analyst"].get(servers_url(world)).status_code == 200
    assert world["analyst"].get(servers_url(world, server["id"])).status_code == 200
    assert (
        world["developer"]
        .post(servers_url(world), json=openapi_body(upstream.url, key="dev"))
        .status_code
        == 403
    )
    assert (
        world["developer"].patch(servers_url(world, server["id"]), json={"name": "x"}).status_code
        == 403
    )
    assert world["anonymous"].get(servers_url(world)).status_code == 401


@pytest.mark.parametrize(
    "url, code",
    [
        ("http://backend:8000", "upstream_url_refused"),
        ("http://litellm:4000", "upstream_url_refused"),
        ("http://127.0.0.1:8000", "upstream_url_refused"),
        ("http://not-listed.example.com", "egress_not_allowlisted"),
        ("http://u:p@superset.example.com", "endpoint_url_not_allowed"),
    ],
)
def test_05b_6_upstream_url_refused(world, url, code):
    response = world["admin"].post(servers_url(world), json=openapi_body(url))
    assert response.status_code in (400, 422)
    assert response.json()["error"]["code"] == code


def test_05b_forward_user_upstream_is_refused(world, upstream):
    body = openapi_body(upstream.url) | {"upstream_auth": {"type": "forward_user"}}
    assert world["admin"].post(servers_url(world), json=body).status_code == 422


def test_05b_connection_test_reports_status(world, upstream):
    server = create(world, openapi_body(upstream.url))
    result = world["admin"].post(servers_url(world, server["id"], "/test"))
    assert result.status_code == 200, result.text
    body = result.json()
    # The fake upstream answers 404 on "/": reachable, and the status is shown as it is.
    assert body["reachable"] is True and body["status_code"] == 404 and body["error_code"] is None
    down = create(world, openapi_body("http://127.0.0.1:9"))
    result = world["admin"].post(servers_url(world, down["id"], "/test")).json()
    assert result["reachable"] is False and result["error_code"]


def test_05b_add_to_tools_creates_a_forward_user_tool(world, upstream, settings):
    server = publish(world, upstream.url)
    key = server["key"]
    response = world["admin"].post(servers_url(world, server["id"], "/tools"))
    assert response.status_code == 201, response.text
    tool = response.json()
    assert tool["key"] == key and tool["kind"] == "mcp"
    assert tool["endpoint_url"] == f"{settings.internal_api_url.rstrip('/')}/mcp/{key}/"
    assert tool["auth"] == {"type": "forward_user"}
    again = world["admin"].post(servers_url(world, server["id"], "/tools"))
    assert again.status_code == 409 and again.json()["error"]["code"] == "tool_key_taken"


def test_05b_s5_openapi_tool_kind_is_refused(world):
    body = {
        "key": "direct",
        "name": "Direct",
        "kind": "openapi",
        "endpoint_url": "http://superset.example.com/api",
        "auth": {"type": "none"},
    }
    response = world["admin"].post(f"{API}/projects/{world['project']}/tools", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "openapi_tool_via_mcp_server"


def test_05b_calls_summary_is_empty_for_a_new_server(world, upstream):
    server = create(world, openapi_body(upstream.url))
    response = world["analyst"].get(servers_url(world, server["id"], "/calls"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["window_hours"] == 24 and body["requests"] == 0 and body["recent"] == []


def test_05b_read_mode_get_parity(world, upstream, make_user, client_factory):
    """Read access sees exactly what edit access sees (03a rule), masked secrets included."""
    server = create(world, openapi_body(upstream.url))
    _, reader = make_user(memberships={uuid.UUID(world["project"]): ("admin", "read")})
    read = client_factory(reader)
    for url in (
        servers_url(world),
        servers_url(world, server["id"]),
        servers_url(world, server["id"], "/calls"),
    ):
        edit_answer, read_answer = world["admin"].get(url), read.get(url)
        assert edit_answer.status_code == 200, (url, edit_answer.text)
        assert (read_answer.status_code, read_answer.content) == (200, edit_answer.content), url
    assert read.patch(servers_url(world, server["id"]), json={"name": "x"}).status_code == 403
