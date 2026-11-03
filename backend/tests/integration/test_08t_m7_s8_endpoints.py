"""08-tam-1a r1 MINOR-7: S8 at the endpoint and role level (K-08T1-0002 S8). A run's answer carries
a placeholder of its own scope. The run's user reads the value on `GET /runs/{id}/stream`; another
analyst who approves it (`POST /runs/{id}/resume`) and an admin who reads it see the
placeholder."""

import asyncio
import os

import redis.asyncio as aioredis

from ffcore.guardrails.masking import RedisTokenStore
from ffcore.runtime.state import ToolOutcome
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, get_stream, parse_sse, post_run
from tests.integration.runtime_support import Ports, ScriptedModel, ScriptedTools, turn
from tests.integration.test_06a_runs_api import SQL_TOOL, _approval_agent

NAME = "Ayşe Kaya"
ANSWER = "Kayıt sahibi <<PII_1>>."


def _ports():
    tools = ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 1", False, 7, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": "select 1"})]), turn(ANSWER))
    return Ports(model, tools=tools)


def _issue(run_id):
    async def go():
        client = aioredis.from_url(os.environ["REDIS_URL"])
        try:
            store = RedisTokenStore(client, 600)
            assert await store.token_for(str(run_id), "PERSON:" + NAME, NAME) == "<<PII_1>>"
        finally:
            await client.aclose()

    asyncio.run(go())


def _answer(events):
    # The scripted model streams word by word ("word "): compare without the last space.
    return "".join(d.get("text", "") for _, e, d in events if e == "token").strip()


def test_08t_m7_owner_sees_values_approver_and_admin_placeholders(
    analyst, pg, harness, use_queue, make_user, client_factory
):
    project_id, owner = analyst
    _approval_agent(pg, project_id)
    use_queue(InlineQueue(harness, _ports()))
    events = post_run(owner, project_id)
    assert events[-1][1] == "approval_required"
    run_id = events[0][2]["run_id"]
    _issue(run_id)

    _, approver_email = make_user(memberships={project_id: ("analyst", "edit")})
    approver = client_factory(approver_email)
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"
    with approver.stream("POST", url, json={"decision": "approved"}) as response:
        assert response.status_code == 200
        resumed = parse_sse(response.iter_lines())
    assert resumed[-1][1] == "done"
    assert _answer(resumed) == ANSWER  # the approver is not the run's user

    # Reconnect after the approval_required entry (a stream from the start ends there).
    after = events[-1][0]
    _, admin_email = make_user(memberships={project_id: ("admin", "edit")})
    admin = client_factory(admin_email)
    assert _answer(get_stream(admin, project_id, run_id, last=after)) == ANSWER
    owned = _answer(get_stream(owner, project_id, run_id, last=after))
    assert owned == f"Kayıt sahibi {NAME}."
