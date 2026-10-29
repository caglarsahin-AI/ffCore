"""06a run endpoints, role and access matrix (review r1 MAJOR-1).

| Endpoint | user | analyst+ | read access |
|---|---|---|---|
| start a run (chat) | own run | own run | allowed (chat) |
| start a run (channel=test) | 403 | allowed | allowed |
| resume with an answer | own run only | own run only | allowed (own chat) |
| resume with a decision | never | `approval.assign_to` or above, edit | 403 |
| cancel | own run | own run; admin any run (edit) | own run |
| feedback | own run, edit | any run in the project, edit | 403 |
"""

import asyncio
import uuid

import pytest

from ffcore.core.auth import sign_on_behalf_of
from ffcore.runtime.state import ToolOutcome
from tests.dummy import SERVICE_TOKEN
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, parse_sse, post_run, publish
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

ASK = definition(knowledge=[{"kb_key": "sozlesmeler", "mode": "tool"}], ask_user=True)
SQL_TOOL = "mcp-sql__run_sql"
APPROVAL = definition(
    knowledge=[],
    tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
    approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
)


@pytest.fixture
def team(make_project, make_user, client_factory, settings):
    project_id = make_project()
    clients = {}
    for name, role, access in (
        ("owner", "user", "edit"),
        ("other", "user", "edit"),
        ("viewer", "user", "read"),
        ("analyst", "analyst", "edit"),
        ("analyst_read", "analyst", "read"),
        ("admin", "admin", "edit"),
    ):
        _, email = make_user(memberships={project_id: (role, access)})
        clients[name] = client_factory(email)
    return project_id, clients


def _answer_ports():
    return Ports(
        ScriptedModel(turn("30 gün [1]."), turn("30 gün [1]."), turn("30 gün [1].")),
        ScriptedRetriever([source()]),
    )


def _start(client, project_id, **body):
    return post_run(client, project_id, **body)[0][2]["run_id"]


def test_06a_r1_user_starts_own_chat_run_but_not_a_test_run(team, pg, harness, use_queue):
    project_id, c = team
    publish(pg, project_id, definition())
    use_queue(InlineQueue(harness, _answer_ports()))
    run_id = _start(c["owner"], project_id)
    assert run_row(pg, run_id)["status"] == "completed"
    # Chat is a read-only exception (brief 03), for user members too.
    assert run_row(pg, _start(c["viewer"], project_id))["status"] == "completed"
    denied = c["owner"].post(
        f"/api/v1/projects/{project_id}/agents/asistan/runs",
        json={"input": "q", "channel": "test"},
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "insufficient_role"


def _waiting_user_run(c, project_id, pg, harness, use_queue, who="owner", first=True):
    if first:
        publish(pg, project_id, ASK)
    model = ScriptedModel(
        turn(tools=[("ask_user_question", {"question": "Hangi sözleşme?"})]), turn("Tamam.")
    )
    use_queue(InlineQueue(harness, Ports(model, ScriptedRetriever([source()]))))
    events = post_run(c[who], project_id)
    assert events[-1][1] == "question"
    return events[0][2]["run_id"]


def test_06a_r1_user_answers_own_question_only(team, pg, harness, use_queue):
    project_id, c = team
    run_id = _waiting_user_run(c, project_id, pg, harness, use_queue)
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"
    for name in ("other", "analyst", "admin"):
        response = c[name].post(url, json={"answer": "Hizmet"})
        assert response.status_code == 403, name
        assert response.json()["error"]["code"] == "not_run_user"
    with c["owner"].stream("POST", url, json={"answer": "Hizmet"}) as response:
        assert response.status_code == 200
        rest = parse_sse(response.iter_lines())
    assert rest[-1][1] == "done" and run_row(pg, run_id)["status"] == "completed"


def test_06a_r1_user_never_decides_an_approval(team, pg, harness, use_queue):
    project_id, c = team
    publish(pg, project_id, APPROVAL)
    tools = ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 1", False, 7, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": "select 1"})]), turn("1."))
    use_queue(InlineQueue(harness, Ports(model, tools=tools)))
    run_id = post_run(c["owner"], project_id)[0][2]["run_id"]
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"
    # The run's own user is not an approver: the role rule applies, never ownership.
    for name in ("owner", "analyst_read"):
        assert c[name].post(url, json={"decision": "approved"}).status_code == 403, name
    with c["analyst"].stream("POST", url, json={"decision": "approved"}) as response:
        assert response.status_code == 200
        parse_sse(response.iter_lines())
    assert run_row(pg, run_id)["status"] == "completed"


def test_06a_r1_cancel_own_run_or_admin(team, pg, harness, use_queue):
    project_id, c = team
    run_id = _waiting_user_run(c, project_id, pg, harness, use_queue)
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/cancel"
    for name in ("other", "analyst"):
        response = c[name].post(url)
        assert response.status_code == 403, name
    assert c["owner"].post(url).json()["status"] == "cancelled"

    second = _waiting_user_run(c, project_id, pg, harness, use_queue, who="other", first=False)
    response = c["admin"].post(f"/api/v1/projects/{project_id}/runs/{second}/cancel")
    assert response.status_code == 200 and response.json()["status"] == "cancelled"


def test_06a_r1_feedback_user_own_run_with_edit(team, pg, harness, use_queue):
    project_id, c = team
    publish(pg, project_id, definition())
    use_queue(InlineQueue(harness, _answer_ports()))
    own = _start(c["owner"], project_id)
    others = _start(c["other"], project_id)
    base = f"/api/v1/projects/{project_id}/runs"
    assert c["owner"].post(f"{base}/{own}/feedback", json={"vote": "correct"}).status_code == 200
    denied = c["owner"].post(f"{base}/{others}/feedback", json={"vote": "wrong"})
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "not_run_user"
    read_only = c["viewer"].post(f"{base}/{own}/feedback", json={"vote": "wrong"})
    assert read_only.status_code == 403
    assert read_only.json()["error"]["code"] == "read_only_access"
    # Experts (analyst and above, edit) review any run of the project.
    assert (
        c["analyst"].post(f"{base}/{others}/feedback", json={"vote": "partial"}).status_code == 200
    )


def _waiting_approval(c, project_id, pg, harness, use_queue):
    publish(pg, project_id, APPROVAL)
    tools = ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 1", False, 7, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": "select 1"})]), turn("1."))
    queue = use_queue(InlineQueue(harness, Ports(model, tools=tools)))
    return post_run(c["owner"], project_id)[0][2]["run_id"], queue


def test_06a_r2_approval_needs_a_user_session(
    team, pg, harness, use_queue, make_user, client_factory, app_settings
):
    # K-06a-0016 item 2 (07 S2): a service account acting on behalf of an approver is 403,
    # even when that user may approve with their own console session.
    project_id, c = team
    run_id, _ = _waiting_approval(c, project_id, pg, harness, use_queue)
    approver, _ = make_user(memberships={project_id: ("admin", "edit")})
    token = sign_on_behalf_of(
        user_id=str(approver),
        project_id=str(project_id),
        audience=app_settings.obo_audience,
        settings=app_settings,
    )
    service = client_factory()
    service.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
    url = f"/api/v1/projects/{project_id}/runs/{run_id}/resume"
    denied = service.post(url, json={"decision": "approved"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "approval_requires_user_session"
    assert run_row(pg, run_id)["status"] == "waiting_approval"


def test_06a_r2_resume_service_function(team, pg, harness, use_queue):
    # K-06a-0016 item 6: 07's approval endpoints call the same function as /resume.
    from ffcore.core import db
    from ffcore.core.auth import SERVICE_ACTOR, Actor
    from ffcore.core.errors import ApiError
    from ffcore.runtime.resume import resume_run

    project_id, c = team
    run_id, queue = _waiting_approval(c, project_id, pg, harness, use_queue)
    approver = Actor(actor_type="user", actor_id=str(uuid.uuid4()), project_id=str(project_id))

    async def call(actor):
        async with db.session_scope() as session:
            return await resume_run(
                session,
                queue,
                harness.settings,
                project_id=project_id,
                run_id=uuid.UUID(run_id),
                actor=actor,
                decision="approved",
                comment="ok",
            )

    with pytest.raises(ApiError) as refused:
        asyncio.run(call(SERVICE_ACTOR))
    assert refused.value.code == "approval_requires_user_session"
    asyncio.run(call(approver))
    assert run_row(pg, run_id)["status"] == "completed"
    assert queue.jobs[-1][1]["decision"] == "approved"
    with pytest.raises(ApiError) as again:
        asyncio.run(call(approver))
    assert again.value.code == "run_not_waiting"
