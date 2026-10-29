"""18-ticket-desk slice 2: the compose service ticket-desk registered and discovered through the
05a tool registry API, with the stack's own settings (`ALLOWED_INTERNAL_HOSTS` from .env.test,
K-SEN-0012), as F2 and F11 will use it.

The documented test stack starts the service (`--profile test`). ticket-desk stands for an
external ticket system: auth `none`, no identity is forwarded (the 05a rule that forward_user
to a host outside the internal list is 400 is test_05a_forward_user_external_host_400).
"""

import json
import urllib.request

import pytest

API = "/api/v1"
DESK = "http://ticket-desk:8000"
ACTIONS = {"list_tickets", "get_ticket", "send_reply"}


@pytest.fixture
def world(make_user, make_project, client_factory, app_settings):
    project = make_project()
    _, admin = make_user(memberships={project: ("admin", "edit")})
    _, analyst = make_user(memberships={project: ("analyst", "edit")})
    return {
        "project": str(project),
        "admin": client_factory(admin),
        "analyst": client_factory(analyst),
    }


@pytest.fixture
def desk():
    request = urllib.request.Request(DESK + "/_reset", method="POST", data=b"")
    urllib.request.urlopen(request, timeout=5).close()
    return DESK


def _desk_get(path: str):
    with urllib.request.urlopen(DESK + path, timeout=5) as response:
        return json.loads(response.read())


def _tools(world, suffix=""):
    return f"{API}/projects/{world['project']}/tools{suffix}"


def _register(world) -> dict:
    response = world["admin"].post(
        _tools(world),
        json={
            "key": "ticket-desk",
            "name": "Ticket desk",
            "kind": "mcp",
            "endpoint_url": DESK + "/mcp",
            "auth": {"type": "none"},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _discover(world, tool) -> dict:
    response = world["admin"].post(_tools(world, f"/{tool['id']}/discover"))
    assert response.status_code == 200, response.text
    return response.json()


def test_18td_9_register_and_discover_through_the_registry(world, desk):
    tool = _discover(world, _register(world))
    assert tool["status"] == "discovered", tool
    actions = {a["name"]: a for a in tool["actions"]}
    assert set(actions) == ACTIONS
    # K-05a-0002 S8: new actions start off and needing approval
    assert all(not a["enabled"] and a["needs_approval"] for a in actions.values())


def test_18td_10_reads_opened_send_reply_keeps_approval(world, desk):
    tool = _discover(world, _register(world))
    for name in ("list_tickets", "get_ticket"):
        response = world["admin"].patch(
            _tools(world, f"/{tool['id']}/actions/{name}"),
            json={"enabled": True, "needs_approval": False},
        )
        assert response.status_code == 200, response.text
    response = world["admin"].patch(
        _tools(world, f"/{tool['id']}/actions/send_reply"), json={"enabled": True}
    )
    assert response.status_code == 200, response.text
    listed = world["admin"].get(_tools(world, f"/{tool['id']}"))
    actions = {a["name"]: a for a in listed.json()["actions"]}
    assert all(a["enabled"] for a in actions.values())
    assert not actions["list_tickets"]["needs_approval"]
    assert not actions["get_ticket"]["needs_approval"]
    assert actions["send_reply"]["needs_approval"] is True


def test_18td_11_invoke_reaches_the_desk_without_identity(world, desk):
    tool = _discover(world, _register(world))
    response = world["admin"].post(
        _tools(world, f"/{tool['id']}/actions/get_ticket/invoke"),
        json={"arguments": {"ticket_id": "tkt-001"}},
    )
    assert response.status_code == 200, response.text
    assert json.loads(response.json()["text"])["id"] == "tkt-001"
    calls = _desk_get("/_calls")
    assert [c["tool"] for c in calls] == ["get_ticket"]
    # F2: no credential and no on-behalf-of token goes to the external system
    assert not set(calls[0]["header_names"]) & {"authorization", "x-on-behalf-of", "cookie"}
    assert _desk_get("/_sent") == []
