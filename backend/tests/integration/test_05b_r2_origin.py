"""05b r1 (K-05B-0008): an upstream call never leaves the registered origin and base path.

MAJOR-1 `upstream-origin-kacagi`: a path key such as `:PORT/...`, `0:PORT/...` or `v1/...` is
refused at upload (422 openapi_path_invalid); if such an operation were in the catalog anyway
(older row, written straight into the table here), the call is refused before any request
(upstream_origin_mismatch). MINOR-1: a call-time URL or egress refusal is an error result with
its own code (not a JSON-RPC error, not internal_error), recorded as denied. MINOR-2: a path
value `..` is refused.
"""

import json

import pytest

from tests.integration.facade_support import make_key
from tests.integration.mcp_publish_support import *  # noqa: F403 - fixtures
from tests.integration.mcp_publish_support import (
    bearer,
    call_result,
    calls,
    create,
    openapi_body,
    publish,
    rpc,
    servers_url,
)

OK = {"200": {"description": "x"}}


def _spec(path: str) -> str:
    doc = {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1"},
        "paths": {
            "/fine": {"get": {"operationId": "fine", "responses": OK}},
            path: {"get": {"operationId": "escape", "responses": OK}},
        },
    }
    return json.dumps(doc)


@pytest.fixture
def key(world):
    return make_key(world["admin"], world["project"], scopes=["tools_invoke"])["key"]


def _p1_paths(upstream) -> list[str]:
    port = upstream.url.rsplit(":", 1)[1]
    return [f":{port}/api/v1/dashboard/", f"0:{port}/api/v1/dashboard/", "v1/dashboard/"]


def test_05b_r2_p1_paths_refused_at_upload(world, upstream):
    for path in _p1_paths(upstream):
        body = openapi_body("http://127.0.0.1") | {"spec": _spec(path)}
        response = world["admin"].post(servers_url(world), json=body)
        assert response.status_code == 422, (path, response.text)
        assert response.json()["error"]["code"] == "openapi_path_invalid"
    server = create(world, openapi_body("http://127.0.0.1") | {"spec": _spec("/also-fine")})
    reload = world["admin"].put(
        servers_url(world, server["id"], "/spec"), json={"spec": _spec("/a/../b")}
    )
    assert reload.status_code == 422 and reload.json()["error"]["code"] == "openapi_path_invalid"


@pytest.mark.parametrize("case", [0, 1, 2])
def test_05b_r2_p1_stored_escape_is_refused_before_any_request(world, upstream, key, pg, case):
    path = _p1_paths(upstream)[case]
    base = "http://127.0.0.1" if case < 2 else f"{upstream.url}/api"
    server = publish(world, base, exposed=["searchDashboards"], access="token")
    # An operation the upload check would refuse, written straight into the catalog.
    ops = server["operations"]
    for op in ops:
        op.pop("exposed")
        if op["name"] == "searchDashboards":
            op["path"] = path
    pg.execute(
        "UPDATE mcp_servers SET operations = %s WHERE id = %s", (json.dumps(ops), server["id"])
    )
    before = len(upstream.hits)
    response = rpc(
        world["anonymous"],
        server["key"],
        "tools/call",
        {"name": "searchDashboards", "arguments": {}},
        headers=bearer(key),
    )
    result = call_result(response)
    expected = "upstream_origin_mismatch" if case < 2 else "openapi_path_invalid"
    assert result["isError"] is True and expected in result["content"][0]["text"]
    assert len(upstream.hits) == before
    assert calls(pg, server["id"])[-1][1:3] == ("denied", expected)


def test_05b_r2_base_path_is_kept(world, upstream, key):
    server = publish(world, f"{upstream.url}/prefix", exposed=["searchDashboards"], access="token")
    before = len(upstream.hits)
    rpc(
        world["anonymous"],
        server["key"],
        "tools/call",
        {"name": "searchDashboards", "arguments": {}},
        headers=bearer(key),
    )
    assert [h.path for h in upstream.hits[before:]] == ["/prefix/api/v1/dashboard/"]


def test_05b_r2_p2_call_time_egress_refusal_is_a_coded_result(
    world, upstream, key, pg, app, settings
):
    from ffcore.core.config import get_settings

    server = publish(world, upstream.url, exposed=["searchDashboards"], access="token")
    # The egress policy narrows after registration: loopback is no longer internal.
    narrowed = settings.model_copy(
        update={
            "allowed_internal_hosts": [
                h for h in settings.allowed_internal_hosts if h != "127.0.0.0/8"
            ]
        }
    )
    app.dependency_overrides[get_settings] = lambda: narrowed
    before = len(upstream.hits)
    response = rpc(
        world["anonymous"],
        server["key"],
        "tools/call",
        {"name": "searchDashboards", "arguments": {}},
        headers=bearer(key),
    )
    assert "error" not in response.json()
    result = call_result(response)
    assert result["isError"] is True and "egress_not_allowlisted" in result["content"][0]["text"]
    assert len(upstream.hits) == before
    assert calls(pg, server["id"])[-1][1:3] == ("denied", "egress_not_allowlisted")


def test_05b_r2_dot_dot_path_value_is_refused(world, upstream, key, pg):
    server = publish(world, upstream.url, exposed=["getChartData"], access="token")
    before = len(upstream.hits)
    result = call_result(
        rpc(
            world["anonymous"],
            server["key"],
            "tools/call",
            {"name": "getChartData", "arguments": {"pk": ".."}},
            headers=bearer(key),
        )
    )
    assert result["isError"] is True and "invalid_arguments" in result["content"][0]["text"]
    assert len(upstream.hits) == before


# --- r3 (K-05B-0012): percent-encoded dots and slashes ---


def test_05b_r3_encoded_path_key_refused_at_upload(world):
    for path in ("/a/%2e%2e/b", "/a%2Fb", "/%252e%252e/x"):
        body = openapi_body("http://127.0.0.1") | {"spec": _spec(path)}
        response = world["admin"].post(servers_url(world), json=body)
        assert response.status_code == 422, (path, response.text)
        assert response.json()["error"]["code"] == "openapi_path_invalid"


def test_05b_r3_encoded_path_value_never_reaches_upstream(world, upstream, key):
    server = publish(world, upstream.url, exposed=["getChartData"], access="token")
    before = len(upstream.hits)
    for value in ("%2e%2e", "%252e%252e", "a%2Fb"):
        result = call_result(
            rpc(
                world["anonymous"],
                server["key"],
                "tools/call",
                {"name": "getChartData", "arguments": {"pk": value}},
                headers=bearer(key),
            )
        )
        assert result["isError"] is True and "invalid_arguments" in result["content"][0]["text"]
    assert len(upstream.hits) == before
