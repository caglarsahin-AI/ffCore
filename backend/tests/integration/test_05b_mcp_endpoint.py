"""05b D3/D4/D5: the published MCP endpoint `/mcp/{key}/` (real app, real database, fake
upstream and a real MCP server on 127.0.0.1).

Acceptance 1 (tools/list shows only the selection, C7), 2 (access: token + tools_invoke,
internal only for the runtime), 3 (monitor logs, enforce blocks; mcp_server_calls + audit),
5 (remote_mcp), 6 (upstream only to the registered origin, no redirects), S2 (request quota),
S4 (identity before the SDK, whatever the Host header).
"""

import uuid

import pytest

from tests.integration.conftest import audit_rows
from tests.integration.facade_support import make_key
from tests.integration.mcp_publish_support import *  # noqa: F403 - fixtures
from tests.integration.mcp_publish_support import (
    API,
    UPSTREAM_TOKEN,
    bearer,
    call_result,
    calls,
    publish,
    rpc,
    runtime_headers,
    servers_url,
    tool_names,
)

BODY = {
    "slice_name": "Doluluk",
    "viz_type": "table",
    "datasource_id": 1,
    "datasource_type": "table",
}


@pytest.fixture
def keys(world):
    console = world["admin"]
    return {
        "invoke": make_key(console, world["project"], scopes=["tools_invoke"])["key"],
        "agents": make_key(console, world["project"], scopes=["agents"])["key"],
    }


@pytest.fixture
def client(world):
    return world["anonymous"]


def _runtime(world, settings, key):
    return runtime_headers(settings, world["admin_id"], world["project"], key)


def test_05b_1_tools_list_shows_only_the_selection(world, upstream, keys, client):
    server = publish(
        world, upstream.url, exposed=["searchDashboards", "createChart"], access="token"
    )
    names = tool_names(rpc(client, server["key"], "tools/list", headers=bearer(keys["invoke"])))
    assert names == ["createChart", "searchDashboards"]
    world["admin"].patch(
        servers_url(world, server["id"]),
        json={"aliases": {"searchDashboards": {"name": "find_dashboard", "description": "Ara."}}},
    )
    listed = rpc(client, server["key"], "tools/list", headers=bearer(keys["invoke"]))
    tools = {t["name"]: t for t in listed.json()["result"]["tools"]}
    assert set(tools) == {"createChart", "find_dashboard"}
    assert tools["find_dashboard"]["description"] == "Ara."
    assert tools["createChart"]["inputSchema"]["properties"]["body"]["type"] == "object"


def test_05b_2_token_access_needs_tools_invoke(world, upstream, keys, client, pg):
    server = publish(world, upstream.url, access="token")
    params = {"name": "searchDashboards", "arguments": {"q": "(page:0)"}}
    denied = rpc(client, server["key"], "tools/call", params, headers=bearer(keys["agents"]))
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "scope_missing"
    before = len(upstream.hits)
    result = call_result(
        rpc(client, server["key"], "tools/call", params, headers=bearer(keys["invoke"]))
    )
    assert result["isError"] is False and "Yatak doluluk" in result["content"][0]["text"]
    hit = upstream.hits[before]
    assert (
        hit.method == "GET" and hit.path == "/api/v1/dashboard/" and hit.query == "q=%28page%3A0%29"
    )
    assert hit.headers["authorization"] == f"Bearer {UPSTREAM_TOKEN}"
    # The caller's own key never reaches the upstream.
    assert keys["invoke"] not in str(hit.headers)
    rows = calls(pg, server["id"])
    assert rows[-1][:4] == ("searchDashboards", "ok", None, "api_key")
    audits = audit_rows(pg, "mcp_server_call", project=world["project"])
    assert audits and "Yatak" not in str(audits) and UPSTREAM_TOKEN not in str(audits)


def test_05b_2_no_credentials_is_401_before_the_sdk(world, upstream, client):
    server = publish(world, upstream.url, access="token")
    # S4: the SDK Host check is off; identity is checked first, whatever the Host.
    response = rpc(client, server["key"], "tools/list", headers={"Host": "evil.example"})
    assert response.status_code == 401
    session = world["admin"]  # a console session is no MCP client
    response = rpc(session, server["key"], "tools/list")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "mcp_credentials_required"


def test_05b_2_internal_refuses_keys_accepts_the_runtime(world, upstream, keys, client, settings):
    server = publish(world, upstream.url, access="internal")
    refused = rpc(client, server["key"], "tools/list", headers=bearer(keys["invoke"]))
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "mcp_server_internal"
    runtime = _runtime(world, settings, server["key"])
    assert len(tool_names(rpc(client, server["key"], "tools/list", headers=runtime))) == 6


def test_05b_2_other_project_and_unknown_or_inactive_server_are_404(
    world, upstream, keys, client, make_project, make_user, client_factory
):
    server = publish(world, upstream.url, access="token")
    other = make_project()
    _, email = make_user(memberships={other: ("admin", "edit")})
    stranger = make_key(client_factory(email), other, scopes=["tools_invoke"])["key"]
    response = rpc(client, server["key"], "tools/list", headers=bearer(stranger))
    assert response.status_code == 404
    unknown = rpc(client, "no-such-server", "tools/list", headers=bearer(keys["invoke"]))
    assert unknown.status_code == 404
    world["admin"].patch(servers_url(world, server["id"]), json={"status": "disabled"})
    disabled = rpc(client, server["key"], "tools/list", headers=bearer(keys["invoke"]))
    assert disabled.status_code == 404


def test_05b_unexposed_operation_is_not_callable(world, upstream, keys, client, pg):
    server = publish(world, upstream.url, exposed=["searchDashboards"], access="token")
    before = len(upstream.hits)
    result = call_result(
        rpc(
            client,
            server["key"],
            "tools/call",
            {"name": "createChart", "arguments": {"body": BODY}},
            headers=bearer(keys["invoke"]),
        )
    )
    assert result["isError"] is True and "unknown_tool" in result["content"][0]["text"]
    assert len(upstream.hits) == before


def _policy(world, key, mode):
    rules = [
        {
            "type": "tool_args",
            "action": "block",
            "stages": ["tool.pre"],
            "params": {"tools": ["*"], "patterns": ["(?i)drop\\s+table"]},
        }
    ]
    response = world["admin"].post(
        f"{API}/projects/{world['project']}/guardrail-policies",
        json={"key": key, "name": key, "rules": rules, "mode": mode},
    )
    assert response.status_code == 201, response.text


def _create_chart(client, key, headers, name):
    body = {**BODY, "slice_name": name}
    return rpc(
        client,
        key,
        "tools/call",
        {"name": "createChart", "arguments": {"body": body}},
        headers=headers,
    )


def test_05b_3_monitor_logs_and_passes(world, upstream, keys, client, pg):
    _policy(world, "args-monitor", "monitor")
    server = publish(
        world,
        upstream.url,
        access="token",
        guardrail_policy_key="args-monitor",
        guardrail_mode="monitor",
    )
    before = len(upstream.hits)
    result = call_result(
        _create_chart(client, server["key"], bearer(keys["invoke"]), "x; DROP TABLE users")
    )
    assert result["isError"] is False
    assert len(upstream.hits) == before + 1
    events = pg.execute(
        "SELECT stage, action_taken, mode FROM guardrail_events WHERE project_id = %s"
        " AND policy_key = 'args-monitor'",
        (world["project"],),
    ).fetchall()
    assert ("tool.pre", "block", "monitor") in [tuple(e) for e in events]
    assert calls(pg, server["id"])[-1][1] == "ok"


def test_05b_3_enforce_blocks_and_records(world, upstream, keys, client, pg):
    _policy(world, "args-soft", "monitor")
    # The policy itself only monitors; the server's enforce makes it stricter (S1).
    server = publish(
        world,
        upstream.url,
        access="token",
        guardrail_policy_key="args-soft",
        guardrail_mode="enforce",
    )
    before = len(upstream.hits)
    result = call_result(
        _create_chart(client, server["key"], bearer(keys["invoke"]), "x; DROP TABLE users")
    )
    assert result["isError"] is True and "guardrail_blocked" in result["content"][0]["text"]
    assert len(upstream.hits) == before
    row = calls(pg, server["id"])[-1]
    assert row[1] == "blocked" and row[2] == "guardrail_blocked" and row[4] == "block"
    audits = audit_rows(pg, "mcp_server_call", project=world["project"])
    assert audits[-1][1] == "denied" and "DROP" not in str(audits[-1])
    clean = call_result(_create_chart(client, server["key"], bearer(keys["invoke"]), "Doluluk"))
    assert clean["isError"] is False and len(upstream.hits) == before + 1


def test_05b_3_server_mode_cannot_loosen_an_enforcing_policy(world, upstream, keys, client):
    _policy(world, "args-hard", "enforce")
    server = publish(
        world, upstream.url, access="token", guardrail_policy_key="args-hard", guardrail_mode="off"
    )
    result = call_result(
        _create_chart(client, server["key"], bearer(keys["invoke"]), "DROP TABLE x")
    )
    assert result["isError"] is True and "guardrail_blocked" in result["content"][0]["text"]


def test_05b_upstream_failures_are_coded_without_upstream_text(world, upstream, keys, client, pg):
    spec_text = (
        'openapi: "3.0.3"\ninfo: {title: t, version: "1"}\npaths:\n'
        "  /fail: {get: {operationId: failing, responses: {'500': {description: x}}}}\n"
        "  /redirect: {get: {operationId: moving, responses: {'302': {description: x}}}}\n"
        "  /big: {get: {operationId: huge, responses: {'200': {description: x}}}}\n"
    )
    server = publish(
        world, upstream.url, exposed=["failing", "moving", "huge"], access="token", spec=spec_text
    )
    texts = {}
    for name in ("failing", "moving", "huge"):
        result = call_result(
            rpc(
                client,
                server["key"],
                "tools/call",
                {"name": name, "arguments": {}},
                headers=bearer(keys["invoke"]),
            )
        )
        assert result["isError"] is True
        texts[name] = result["content"][0]["text"]
    assert "upstream_http_500" in texts["failing"] and "secret detail" not in texts["failing"]
    assert "egress_too_many_redirects" in texts["moving"]
    assert "upstream_response_too_large" in texts["huge"]
    assert {r[2] for r in calls(pg, server["id"])} == {
        "upstream_http_500",
        "egress_too_many_redirects",
        "upstream_response_too_large",
    }


def test_05b_invalid_arguments_never_reach_upstream(world, upstream, keys, client):
    server = publish(world, upstream.url, access="token")
    before = len(upstream.hits)
    result = call_result(
        rpc(
            client,
            server["key"],
            "tools/call",
            {"name": "getChartData", "arguments": {"pk": 1, "x": 2}},
            headers=bearer(keys["invoke"]),
        )
    )
    assert result["isError"] is True and "invalid_arguments" in result["content"][0]["text"]
    assert len(upstream.hits) == before


def test_05b_s2_request_quota_blocks_the_call(world, upstream, keys, client, pg):
    server = publish(world, upstream.url, access="token")
    quota = world["admin"].post(
        f"{API}/projects/{world['project']}/quotas",
        json={"scope_type": "project", "label": "mcp", "windows": {"rpm": 1}, "action": "block"},
    )
    assert quota.status_code == 201, quota.text
    params = {"name": "searchDashboards", "arguments": {}}
    first = call_result(
        rpc(client, server["key"], "tools/call", params, headers=bearer(keys["invoke"]))
    )
    assert first["isError"] is False
    second = call_result(
        rpc(client, server["key"], "tools/call", params, headers=bearer(keys["invoke"]))
    )
    assert second["isError"] is True and "quota_exceeded" in second["content"][0]["text"]
    assert calls(pg, server["id"])[-1][1:3] == ("denied", "quota_exceeded")


# --- D4: remote_mcp (a real MCP server on 127.0.0.1) ---


@pytest.fixture(scope="module")
def mcp_upstream():
    from tests import mcp_fixture

    fixture, uv = mcp_fixture.start()
    yield fixture
    uv.should_exit = True


def test_05b_5_remote_mcp_is_published_behind_our_endpoint(world, mcp_upstream, keys, client, pg):
    key = f"rm-{uuid.uuid4().hex[:8]}"
    body = {
        "key": key,
        "name": "Remote",
        "source_kind": "remote_mcp",
        "upstream_base_url": mcp_upstream.url,
        "upstream_auth": {"type": "header", "name": "X-Api-Token", "value": UPSTREAM_TOKEN},
        "access": "token",
    }
    created = world["admin"].post(servers_url(world), json=body)
    assert created.status_code == 201, created.text
    server = created.json()
    assert server["operations"] == []
    discovered = world["admin"].post(servers_url(world, server["id"], "/discover"))
    assert discovered.status_code == 200, discovered.text
    assert {"echo", "whoami", "big"} <= {op["name"] for op in discovered.json()["operations"]}
    world["admin"].patch(
        servers_url(world, server["id"]), json={"exposed_operations": ["echo"], "status": "active"}
    )
    assert tool_names(rpc(client, key, "tools/list", headers=bearer(keys["invoke"]))) == ["echo"]
    result = call_result(
        rpc(
            client,
            key,
            "tools/call",
            {"name": "echo", "arguments": {"text": "merhaba"}},
            headers=bearer(keys["invoke"]),
        )
    )
    assert result["isError"] is False and result["content"][0]["text"] == "merhaba"
    sent = mcp_upstream.calls()[-1]
    assert sent.arguments == {"text": "merhaba"}
    assert sent.headers["x-api-token"] == UPSTREAM_TOKEN
    assert keys["invoke"] not in str(sent.headers)
    assert calls(pg, server["id"])[-1][:2] == ("echo", "ok")


def test_05b_calls_summary_counts(world, upstream, keys, client):
    server = publish(world, upstream.url, access="token")
    for arguments in ({}, {"pk": 1, "x": 2}):
        name = "searchDashboards" if not arguments else "getChartData"
        rpc(
            client,
            server["key"],
            "tools/call",
            {"name": name, "arguments": arguments},
            headers=bearer(keys["invoke"]),
        )
    summary = world["analyst"].get(servers_url(world, server["id"], "/calls")).json()
    assert summary["requests"] == 2 and summary["errors"] == 1
    assert [c["operation"] for c in summary["recent"]] == ["getChartData", "searchDashboards"]
    assert summary["p50_ms"] is not None
