"""06a run API: SSE stream, reconnect, replay after the live stream expired, resume and its
authority, cancel (acceptance 3, 11, 12, 17a, 17c, 17d). The queue runs the real runner in the
request with scripted ports; the worker process itself is tested in test_06a_worker."""

import asyncio
import os
import uuid

import redis.asyncio as aioredis

from ffcore.runtime.state import ToolOutcome
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import (
    InlineQueue,
    get_stream,
    parse_sse,
    post_run,
    publish,
)
from tests.integration.runtime_support import (
    Ports,
    ScriptedModel,
    ScriptedRetriever,
    ScriptedTools,
    definition,
    run_row,
    source,
    turn,
)

SQL_TOOL = "mcp-sql__run_sql"


def test_06a_11_sse_stream_and_replay(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    use_queue(
        InlineQueue(
            harness, Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([source()]))
        )
    )
    events = post_run(client, project_id)
    names = [e for _, e, _ in events]
    assert names[0] == "progress" and events[0][2]["status"] == "queued"
    assert names[-1] == "done" and "sources" in names and "token" in names
    run_id = events[0][2]["run_id"]
    # Reconnect after the sources event: the rest, in the same order, nothing missing.
    position = next(i for i, (_, e, _) in enumerate(events) if e == "sources")
    again = get_stream(client, project_id, run_id, events[position][0])
    assert again == events[position + 1 :]
    assert run_row(pg, run_id)["status"] == "completed"


def test_06a_17a_reconnect_completes(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    ports = Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()]))
    queue = use_queue(InlineQueue(harness, ports, run_now=False))
    with client.stream(
        "POST", f"/api/v1/projects/{project_id}/agents/asistan/runs", json={"input": "q"}
    ) as response:
        first = next(response.iter_lines())  # the client goes away after the first line
    assert first.startswith("id: ")
    run_id, _ = queue.jobs[0]
    # The worker runs while nobody listens (within the grace): the run is not lost.
    assert asyncio.run(harness.attempt(run_id, ports, listen=False)) == "completed"
    events = get_stream(client, project_id, run_id, first[4:])
    assert [e for _, e, _ in events][-1] == "done"


def test_06a_17d_replay_from_db_after_ttl(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    use_queue(
        InlineQueue(harness, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()])))
    )
    run_id = post_run(client, project_id)[0][2]["run_id"]

    async def expire():
        c = aioredis.from_url(os.environ["REDIS_URL"])
        await c.delete(f"run:{run_id}:events")
        await c.aclose()

    asyncio.run(expire())
    events = get_stream(client, project_id, run_id)
    names = [e for _, e, _ in events]
    assert events[0][2] == {"replay": "run_events", "run_id": run_id}  # said, not silent
    assert names[-1] == "done" and "sources" in names
    assert [d["text"] for _, e, d in events if e == "token"] == ["A [1]."]


def _approval_agent(pg, project_id):
    doc = definition(
        knowledge=[],
        tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
        approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
        limits={"max_tool_calls": 1},
    )
    publish(pg, project_id, doc)


def _sql_ports():
    tools = ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 3", False, 7, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": "select 1"})]), turn("3."))
    return Ports(model, tools=tools)


def test_06a_3_resume_needs_role_and_edit_then_409(
    analyst, pg, harness, use_queue, make_user, client_factory
):
    project_id, client = analyst
    _approval_agent(pg, project_id)
    use_queue(InlineQueue(harness, _sql_ports()))
    events = post_run(client, project_id)
    assert events[-1][1] == "approval_required"
    run_id = events[0][2]["run_id"]
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"

    _, reader = make_user(memberships={project_id: ("analyst", "read")})
    denied = client_factory(reader).post(url, json={"decision": "approved"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "read_only_access"
    wrong = client.post(url, json={"answer": "x"})
    assert wrong.status_code == 422 and wrong.json()["error"]["code"] == "decision_required"

    with client.stream("POST", url, json={"decision": "approved"}) as response:
        rest = parse_sse(response.iter_lines())
    names = [e for _, e, _ in rest]
    assert names[0] == "tool_result" and names[-1] == "done"
    assert run_row(pg, run_id)["output"] == "3."
    again = client.post(url, json={"decision": "approved"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "run_not_waiting"


def test_06a_12_resume_not_waiting_409(analyst, pg, harness, use_queue):
    project_id, client = analyst
    publish(pg, project_id, definition())
    use_queue(
        InlineQueue(harness, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()])))
    )
    run_id = post_run(client, project_id)[0][2]["run_id"]
    response = client.post(
        f"/api/v1/projects/{project_id}/runs/{run_id}/resume", json={"decision": "approved"}
    )
    assert response.status_code == 409 and response.json()["error"]["code"] == "run_not_waiting"


def test_06a_17c_cancel(analyst, pg, harness, use_queue, make_user, client_factory):
    project_id, client = analyst
    publish(pg, project_id, definition())
    queue = use_queue(InlineQueue(harness, Ports(ScriptedModel()), run_now=False))
    with client.stream(
        "POST", f"/api/v1/projects/{project_id}/agents/asistan/runs", json={"input": "q"}
    ) as response:
        next(response.iter_lines())
    run_id = queue.jobs[0][0]
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/cancel"

    _, other = make_user(memberships={project_id: ("analyst", "edit")})
    assert client_factory(other).post(url).status_code == 403  # not the owner, not an admin
    cancelled = client.post(url)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.post(url).json()["error"]["code"] == "run_finished"
    # The queued job finds a finished run and leaves it alone.
    assert asyncio.run(harness.attempt(run_id, Ports(ScriptedModel()))) == "cancelled"


def test_06a_runs_read_endpoints(analyst, pg, harness, use_queue):
    project_id, client = analyst
    agent_id = publish(pg, project_id, definition())
    use_queue(
        InlineQueue(harness, Ports(ScriptedModel(turn("A [1].")), ScriptedRetriever([source()])))
    )
    run_id = post_run(client, project_id)[0][2]["run_id"]
    base = f"/api/v1/projects/{project_id}/runs"
    run = client.get(f"{base}/{run_id}").json()
    assert run["status"] == "completed" and run["agent_id"] == str(agent_id)
    events = client.get(f"{base}/{run_id}/events").json()["items"]
    assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
    assert events[0]["type"] == "queued"
    listed = client.get(base, params={"agent_id": str(agent_id)}).json()["items"]
    assert [r["id"] for r in listed] == [run_id]


def test_06a_unpublished_agent_is_404(analyst, pg, use_queue, harness):
    project_id, client = analyst
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by)"
        " VALUES (%s, %s, 'draft', 'D', 't')",
        (uuid.uuid4(), project_id),
    )
    use_queue(InlineQueue(harness, Ports(ScriptedModel())))
    response = client.post(f"/api/v1/projects/{project_id}/agents/draft/runs", json={"input": "q"})
    assert response.status_code == 404 and response.json()["error"]["code"] == "agent_not_published"


def test_06a_superadmin_without_membership_cannot_start_a_run(
    pg, make_project, make_user, client_factory, harness, use_queue
):
    project_id = make_project()
    _, email = make_user(superadmin="edit")
    client = client_factory(email)
    publish(pg, project_id, definition())
    queue = use_queue(InlineQueue(harness, Ports(ScriptedModel())))
    response = client.post(
        f"/api/v1/projects/{project_id}/agents/asistan/runs", json={"input": "q"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "run_needs_membership"
    assert queue.jobs == []
