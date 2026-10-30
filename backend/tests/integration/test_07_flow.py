"""07 slices 3 and 6 end to end: the real graph, runner and run API with scripted ports.

A run stops at a tool call that needs approval; 07 opens the approval (masked arguments), the
decision routes resume the run through 06a's `runtime.resume.resume_run`, the same call is not
asked twice in a run (`approval_reused`), and an expired approval closes its waiting run.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from ffcore.core.auth import sign_on_behalf_of
from ffcore.runtime.state import GuardResult, ToolOutcome
from tests.dummy import SERVICE_TOKEN
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, get_stream, post_run, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedGuard,
    ScriptedModel,
    ScriptedTools,
    definition,
    events,
    run_row,
    turn,
)

SQL_TOOL = "mcp-sql__run_sql"
SECRET = "sk-ant-07SECRET07SECRET07SECRET"
ARGS = {"sql": f"select '{SECRET}'"}
MASKED = {"sql": "select '[MASKED]'"}
APPROVAL = definition(
    knowledge=[],
    tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
    approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
    limits={"max_tool_calls": 2},
)


class MaskingGuard(ScriptedGuard):
    async def check(self, stage, text, *, tool=None):
        if stage == "tool.pre":
            return GuardResult("allow", text.replace(SECRET, "[MASKED]"), None, None, 1)
        return await super().check(stage, text, tool=tool)


def _tools():
    return ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 1", False, 7, False, 5)},
    )


@pytest.fixture
def team(make_project, make_user, client_factory, settings):
    project_id = make_project()
    clients = {}
    for name, role, access in (
        ("owner", "user", "edit"),
        ("analyst", "analyst", "edit"),
        ("analyst_read", "analyst", "read"),
    ):
        _, email = make_user(memberships={project_id: (role, access)})
        clients[name] = client_factory(email)
    return project_id, clients


def _waiting(team, pg, harness, use_queue, *turns, run_now=True):
    project_id, c = team
    publish(pg, project_id, APPROVAL)
    model = ScriptedModel(*(turns or (turn(tools=[(SQL_TOOL, ARGS)]), turn("1."))))
    ports = Ports(model, tools=_tools(), guard=MaskingGuard())
    queue = use_queue(InlineQueue(harness, ports, run_now=run_now))
    streamed = post_run(c["owner"], project_id)
    run_id = streamed[0][2]["run_id"]
    return run_id, streamed, ports, queue


def _approvals(pg, run_id):
    return pg.execute(
        "SELECT id, status, arguments, tool_call_id FROM approvals WHERE run_id = %s"
        " ORDER BY requested_at",
        (run_id,),
    ).fetchall()


def _url(project_id, approval_id, verb):
    return f"/api/v1/projects/{project_id}/approvals/{approval_id}/{verb}"


def test_07_approval_opened_on_interrupt_with_masked_arguments(team, pg, harness, use_queue):
    run_id, streamed, ports, _ = _waiting(team, pg, harness, use_queue)
    assert run_row(pg, run_id)["status"] == "waiting_approval" and ports.tools.called == []
    [(approval_id, status, arguments, _)] = _approvals(pg, run_id)
    assert status == "pending" and arguments == MASKED
    required = streamed[-1]
    assert required[1] == "approval_required"
    assert required[2]["approval_id"] == str(approval_id) and "expires_at" in required[2]
    requested = [p for _, t, p in events(pg, run_id) if t == "approval_requested"][0]
    assert requested["approval_id"] == str(approval_id)
    assert SECRET not in str(_approvals(pg, run_id))


def test_07_sse_continues_after_approval(team, pg, harness, use_queue):
    project_id, c = team
    run_id, streamed, ports, _ = _waiting(team, pg, harness, use_queue)
    [(approval_id, *_)] = _approvals(pg, run_id)
    response = c["analyst"].post(_url(project_id, approval_id, "approve"), json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "approved" and body["can_decide"] is False
    assert run_row(pg, run_id)["status"] == "completed"
    assert ports.tools.called == [(SQL_TOOL, MASKED)]
    # The client follows from where its stream stopped: the rest of the run, ending in done.
    rest = get_stream(c["analyst"], project_id, run_id, last=body["stream_after"])
    names = [e for _, e, _ in rest]
    assert names[-1] == "done" and "approval_required" not in names
    assert rest[0][0] > streamed[-1][0]


def test_07_reject_reaches_model(team, pg, harness, use_queue):
    project_id, c = team
    run_id, _, ports, _ = _waiting(
        team, pg, harness, use_queue, turn(tools=[(SQL_TOOL, ARGS)]), turn("Reddedildi.")
    )
    [(approval_id, *_)] = _approvals(pg, run_id)
    response = c["analyst"].post(
        _url(project_id, approval_id, "reject"), json={"note": "too broad"}
    )
    assert response.status_code == 200, response.text
    assert ports.tools.called == []
    seen = ports.model.calls[-1][-1]["content"]
    assert "rejected" in seen and "too broad" in seen
    assert run_row(pg, run_id)["status"] == "completed"


def test_07_same_args_not_asked_twice_in_a_run(team, pg, harness, use_queue):
    project_id, c = team
    run_id, _, ports, _ = _waiting(
        team,
        pg,
        harness,
        use_queue,
        turn(tools=[(SQL_TOOL, ARGS)]),
        turn(tools=[(SQL_TOOL, ARGS)]),
        turn("2."),
    )
    [(approval_id, *_)] = _approvals(pg, run_id)
    assert c["analyst"].post(_url(project_id, approval_id, "approve"), json={}).status_code == 200
    assert run_row(pg, run_id)["status"] == "completed"
    assert ports.tools.called == [(SQL_TOOL, MASKED), (SQL_TOOL, MASKED)]
    types = [t for _, t, _ in events(pg, run_id)]
    assert types.count("approval_requested") == 1 and types.count("approval_reused") == 1
    reused = [p for _, t, p in events(pg, run_id) if t == "approval_reused"][0]
    assert reused["approval_id"] == str(approval_id)
    assert len(_approvals(pg, run_id)) == 1


def test_07_decision_route_requires_console_session(
    team, pg, harness, use_queue, client_factory, app_settings
):
    project_id, c = team
    run_id, *_ = _waiting(team, pg, harness, use_queue)
    [(approval_id, *_)] = _approvals(pg, run_id)
    analyst_id = pg.execute(
        "SELECT user_id FROM project_members WHERE project_id = %s AND role = 'analyst'"
        " AND access = 'edit'",
        (project_id,),
    ).fetchone()[0]
    token = sign_on_behalf_of(
        user_id=str(analyst_id),
        project_id=str(project_id),
        audience=app_settings.obo_audience,
        settings=app_settings,
    )
    service = client_factory()
    service.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}", "X-On-Behalf-Of": token})
    denied = service.post(_url(project_id, approval_id, "approve"), json={})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "approval_requires_user_session"
    plain = client_factory()
    plain.headers.update({"Authorization": f"Bearer {SERVICE_TOKEN}"})
    assert plain.post(_url(project_id, approval_id, "approve"), json={}).status_code == 403
    read_only = c["analyst_read"].post(_url(project_id, approval_id, "approve"), json={})
    assert (read_only.status_code, read_only.json()["error"]["code"]) == (
        403,
        "read_only_access",
    )
    assert c["owner"].post(_url(project_id, approval_id, "approve"), json={}).status_code == 403
    assert run_row(pg, run_id)["status"] == "waiting_approval"
    assert _approvals(pg, run_id)[0][1] == "pending"


def test_07_decision_on_cancelled_run_is_409(team, pg, harness, use_queue):
    project_id, c = team
    run_id, *_ = _waiting(team, pg, harness, use_queue)
    [(approval_id, *_)] = _approvals(pg, run_id)
    cancel = c["owner"].post(f"/api/v1/projects/{project_id}/runs/{run_id}/cancel")
    assert cancel.status_code == 200, cancel.text
    response = c["analyst"].post(_url(project_id, approval_id, "approve"), json={})
    assert (response.status_code, response.json()["error"]["code"]) == (409, "run_not_waiting")
    # Nothing half done: the approval stays pending and the TTL job closes it.
    assert _approvals(pg, run_id)[0][1] == "pending"


def test_07_ttl_expires_and_fails_run(team, pg, harness, use_queue, settings):
    from ffcore.core import db
    from ffcore.services import approvals

    run_id, *_ = _waiting(team, pg, harness, use_queue)
    later = datetime.now(UTC) + timedelta(minutes=settings.approval_ttl_min, seconds=1)

    async def tick():
        async with db.session_scope() as session:
            return await approvals.expire_due(
                session, now=later, close_run=approvals.run_closer(settings)
            )

    # The test database is shared: other tests' pending approvals expire too (their runs are
    # closed only if still waiting); this run is asserted.
    expired = asyncio.run(tick())
    assert run_id in {str(r.run_id) for r in expired}
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "approval_expired")
    assert _approvals(pg, run_id)[0][1] == "expired"
    types = [t for _, t, _ in events(pg, run_id)]
    assert types[-2:] == ["approval_expired", "error"]
    # A later tick finds nothing left for this run.
    assert run_id not in {str(r.run_id) for r in asyncio.run(tick())}
    assert run_row(pg, run_id)["status"] == "failed"


def test_07_run_without_gate_fails_loud(team, pg, harness, use_queue):
    project_id, c = team
    publish(pg, project_id, APPROVAL)
    model = ScriptedModel(turn(tools=[(SQL_TOOL, ARGS)]), turn("1."))
    ports = Ports(model, tools=_tools(), approval_gate=False)
    use_queue(InlineQueue(harness, ports))
    run_id = post_run(c["owner"], project_id)[0][2]["run_id"]
    row = run_row(pg, run_id)
    assert (row["status"], row["error_code"]) == ("failed", "approval_gate_missing")
    assert ports.tools.called == []


def test_07_unknown_approval_404(team):
    project_id, c = team
    response = c["analyst"].post(_url(project_id, uuid.uuid4(), "approve"), json={})
    assert (response.status_code, response.json()["error"]["code"]) == (404, "approval_not_found")
