"""05b D6, acceptance 4: the Superset sample end to end.

The backend runs for real on 127.0.0.1 (uvicorn), so the 05a MCP client reaches `/mcp/{key}/`
over HTTP exactly as the worker would reach `http://backend:8000/mcp/{key}/`:
spec -> published server (6 tools) -> "add to tools" (self-consumption, forward_user) ->
discover through our own endpoint -> an agent run calls createChart -> 07 approval ->
approved -> the fake upstream receives the call with the server's upstream identity.
"""

import os
import socket
import threading
import time
import uuid

import pytest
import uvicorn
from pydantic import SecretStr

from ffcore.runtime.adapters import AgentTools
from tests.integration.mcp_publish_support import *  # noqa: F403 - fixtures
from tests.integration.mcp_publish_support import (
    SIX,
    UPSTREAM_TOKEN,
    calls,
    publish,
    servers_url,
)
from tests.integration.runtime_support import (
    Harness,
    Ports,
    ScriptedModel,
    definition,
    events,
    seed_run,
    setup,
    turn,
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live(app, settings):
    """The application on a real port; settings point INTERNAL_API_URL at it."""
    from ffcore.core.config import get_settings

    port = _free_port()
    value = settings.model_copy(update={"internal_api_url": f"http://127.0.0.1:{port}"})
    app.dependency_overrides[get_settings] = lambda: value
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", lifespan="off")
    )
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("live backend did not start")
        time.sleep(0.05)
    yield value
    server.should_exit = True


@pytest.fixture
def harness(database_url, live):
    setup(database_url)
    settings = live.model_copy(
        update={
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    return Harness(database_url, settings)


def _tools(settings):
    async def build(*, session, run, definition):
        return await AgentTools.load(session, settings, definition, run)

    return build


def test_05b_4_superset_sample_end_to_end(world, upstream, live, harness, pg):
    server = publish(world, upstream.url, access="internal")
    key = server["key"]
    tool = world["admin"].post(servers_url(world, server["id"], "/tools"))
    assert tool.status_code == 201, tool.text
    tool_id = tool.json()["id"]
    tools_url = f"/api/v1/projects/{world['project']}/tools/{tool_id}"

    discovered = world["admin"].post(tools_url + "/discover")
    assert discovered.status_code == 200, discovered.text
    body = discovered.json()
    assert body["status"] == "discovered", body
    actions = {a["name"]: a for a in body["actions"]}
    assert sorted(actions) == SIX
    # 05a rule: discovered actions start disabled and needing approval (S6: 07 on the agent side).
    assert all(a["needs_approval"] and not a["enabled"] for a in actions.values())
    for name in ("createChart", "searchDashboards"):
        response = world["admin"].patch(f"{tools_url}/actions/{name}", json={"enabled": True})
        assert response.status_code == 200, response.text
    world["admin"].patch(f"{tools_url}/actions/searchDashboards", json={"needs_approval": False})

    doc = definition(
        knowledge=[],
        tools=[{"tool_key": key, "actions": ["createChart", "searchDashboards"]}],
        answer_rules={"cite_sources": False, "unknown_reply": "Yok."},
    )
    run_id = seed_run(pg, uuid.UUID(world["project"]), doc)
    # forward_user carries the run's user (the admin here) to the published endpoint.
    pg.execute("UPDATE runs SET user_id = %s WHERE id = %s", (world["admin_id"], run_id))
    chart = {
        "slice_name": "Doluluk",
        "viz_type": "table",
        "datasource_id": 1,
        "datasource_type": "table",
    }
    model = ScriptedModel(
        turn(tools=[(f"{key}__searchDashboards", {"q": "(page:0)"})]),
        turn(tools=[(f"{key}__createChart", {"body": chart})]),
        turn("Chart oluşturuldu."),
    )
    ports = Ports(model, tools_factory=_tools(harness.settings))
    before = len(upstream.hits)
    assert harness.run(run_id, ports) == "waiting_approval"
    # The read-only search ran; the chart waits for a person.
    assert [h.path for h in upstream.hits[before:]] == ["/api/v1/dashboard/"]
    requested = [p for _, t, p in events(pg, run_id) if t == "approval_requested"]
    assert requested and requested[0]["action"] == f"{key}__createChart"

    assert harness.run(run_id, ports, {"decision": "approved", "comment": None}) == "completed"
    created = upstream.hits[-1]
    assert created.method == "POST" and created.path == "/api/v1/chart/"
    assert created.body == chart
    assert created.headers["authorization"] == f"Bearer {UPSTREAM_TOKEN}"
    rows = calls(pg, server["id"])
    assert [r[0] for r in rows[-2:]] == ["searchDashboards", "createChart"]
    assert all(r[1] == "ok" and r[3] == "user" for r in rows[-2:])
    actors = pg.execute(
        "SELECT DISTINCT actor_id FROM mcp_server_calls WHERE server_id = %s", (server["id"],)
    ).fetchall()
    assert actors == [(world["admin_id"],)]
