"""06a slice 6: agents call 05a MCP tools (real MCP server on 127.0.0.1, real runner and graph).

The model is scripted; the tool port is the real one (adapters.AgentTools.load): tools and
actions from the project's 05a registry, calls through services/mcp_client (C7). Acceptance 3
(approval interrupt and resume) and 5d (tool_call/tool_result, truncated=true) with real calls.
"""

import json
import os
import uuid

import pytest
from pydantic import SecretStr

from ffcore.core.auth import verify_on_behalf_of
from ffcore.runtime.adapters import AgentTools
from ffcore.services.mcp_tools import encrypt_auth
from tests.dummy import SERVICE_TOKEN
from tests.integration.runtime_support import (
    Harness,
    Ports,
    ScriptedModel,
    definition,
    events,
    run_row,
    seed_run,
    setup,
    turn,
)

ECHO = "fixture__echo"
SCHEMAS = {
    "echo": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    "big": {"type": "object", "properties": {"size": {"type": "integer"}}, "required": ["size"]},
    "fail": {"type": "object", "properties": {}},
}


@pytest.fixture
def harness(database_url, app_settings):
    setup(database_url)
    settings = app_settings.model_copy(
        update={
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    return Harness(database_url, settings)


@pytest.fixture
def project(make_project):
    return make_project()


@pytest.fixture(scope="module")
def mcp_server():
    from tests import mcp_fixture

    fixture, uv = mcp_fixture.start()
    yield fixture
    uv.should_exit = True


@pytest.fixture
def loopback(harness):
    # The fixture MCP server is on 127.0.0.1: allowed as internal for these tests only.
    settings = harness.settings
    settings.allowed_internal_hosts = [*settings.allowed_internal_hosts, "127.0.0.0/8"]
    return settings


def register(
    pg, settings, project_id, url, actions, *, key="fixture", status="discovered", auth_type="none"
):
    """A registered, discovered 05a tool; `actions`: name -> column overrides."""
    tool_id = uuid.uuid4()
    pg.execute(
        "INSERT INTO tools (id, project_id, key, name, kind, endpoint_url, auth_type,"
        " auth_config_encrypted, status, created_by)"
        " VALUES (%s, %s, %s, 'Fixture', 'mcp', %s, %s, %s, %s, 't')",
        (tool_id, project_id, key, url, auth_type, encrypt_auth({}, settings), status),
    )
    for name, extra in actions.items():
        row = {
            "needs_approval": False,
            "enabled": True,
            "max_calls_per_run": None,
            "timeout_s": None,
            "status": "available",
            **extra,
        }
        pg.execute(
            "INSERT INTO tool_actions (id, tool_id, name, description, input_schema,"
            " needs_approval, enabled, max_calls_per_run, timeout_s, status)"
            " VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                tool_id,
                name,
                f"The {name} action.",
                json.dumps(SCHEMAS.get(name, {"type": "object"})),
                row["needs_approval"],
                row["enabled"],
                row["max_calls_per_run"],
                row["timeout_s"],
                row["status"],
            ),
        )
    return tool_id


def agent(actions, **overrides):
    return definition(
        knowledge=[],
        tools=[{"tool_key": "fixture", "actions": actions}],
        answer_rules={"cite_sources": False, "unknown_reply": "Yok."},
        **overrides,
    )


def real_tools(settings):
    async def build(*, session, run, definition):
        return await AgentTools.load(session, settings, definition, run)

    return build


def _payloads(pg, run_id, kind):
    return [p for _, t, p in events(pg, run_id) if t == kind]


def _calls(server, run_id):
    return [c for c in server.calls() if c.headers.get("x-run-id") == str(run_id)]


def test_06a_3_mcp_action_needs_approval_then_runs(harness, pg, project, mcp_server, loopback):
    register(pg, loopback, project, mcp_server.url, {"echo": {"needs_approval": True}})
    run_id = seed_run(pg, project, agent(["echo"]))
    model = ScriptedModel(turn(tools=[(ECHO, {"text": "merhaba"})]), turn("Tamam."))
    ports = Ports(model, tools_factory=real_tools(loopback))
    assert harness.run(run_id, ports) == "waiting_approval"
    # The model was offered `<tool_key>__<action>`; nothing reached the server before approval.
    assert model.tools_seen[0] == [ECHO]
    assert _calls(mcp_server, run_id) == []
    requested = _payloads(pg, run_id, "approval_requested")[0]
    # No `approval` block in the definition: the default approver role is analyst (brief 07).
    assert requested["action"] == ECHO and requested["assign_to"] == "analyst"

    assert harness.run(run_id, ports, {"decision": "approved", "comment": None}) == "completed"
    assert [c.arguments for c in _calls(mcp_server, run_id)] == [{"text": "merhaba"}]
    assert "merhaba" in model.calls[-1][-1]["content"]
    result = _payloads(pg, run_id, "tool_result")[0]
    assert result["name"] == ECHO and result["is_error"] is False and result["truncated"] is False


def test_06a_3_mcp_action_rejected_never_runs(harness, pg, project, mcp_server, loopback):
    register(pg, loopback, project, mcp_server.url, {"echo": {"needs_approval": True}})
    run_id = seed_run(pg, project, agent(["echo"]))
    model = ScriptedModel(turn(tools=[(ECHO, {"text": "x"})]), turn("Reddedildi."))
    ports = Ports(model, tools_factory=real_tools(loopback))
    harness.run(run_id, ports)
    assert harness.run(run_id, ports, {"decision": "rejected", "comment": "no"}) == "completed"
    assert _calls(mcp_server, run_id) == []
    assert "rejected" in model.calls[-1][-1]["content"]


def test_06a_3_definition_approval_list_applies(harness, pg, project, mcp_server, loopback):
    # The action itself needs no approval; the agent's `approval.actions` asks for one (brief:
    # joined with tool_actions.needs_approval).
    register(pg, loopback, project, mcp_server.url, {"echo": {"needs_approval": False}})
    doc = agent(["echo"], approval={"actions": ["fixture.echo"], "assign_to": "developer"})
    run_id = seed_run(pg, project, doc)
    model = ScriptedModel(turn(tools=[(ECHO, {"text": "x"})]), turn("Tamam."))
    assert (
        harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "waiting_approval"
    )
    assert _payloads(pg, run_id, "approval_requested")[0]["assign_to"] == "developer"
    assert _payloads(pg, run_id, "tool_call")[0]["needs_approval"] is True


def test_06a_5d_mcp_result_truncated(harness, pg, project, mcp_server, loopback):
    register(pg, loopback, project, mcp_server.url, {"big": {}})
    run_id = seed_run(pg, project, agent(["big"]))
    size = loopback.tool_result_max_chars + 500
    model = ScriptedModel(turn(tools=[("fixture__big", {"size": size})]), turn("Uzun."))
    assert harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "completed"
    call = _payloads(pg, run_id, "tool_call")[0]
    result = _payloads(pg, run_id, "tool_result")[0]
    assert call["name"] == "fixture__big" and result["truncated"] is True
    limit = loopback.tool_result_max_chars
    assert f"[truncated: {limit}/{size} chars]" in model.calls[-1][-1]["content"]


def test_06a_mcp_tool_errors_reach_the_model_with_a_code(
    harness, pg, project, mcp_server, loopback
):
    register(pg, loopback, project, mcp_server.url, {"fail": {}})
    register(pg, loopback, project, "http://127.0.0.1:9/mcp", {"echo": {}}, key="down")
    doc = definition(
        knowledge=[],
        tools=[
            {"tool_key": "fixture", "actions": ["fail"]},
            {"tool_key": "down", "actions": ["echo"]},
        ],
        answer_rules={"cite_sources": False, "unknown_reply": "Yok."},
    )
    run_id = seed_run(pg, project, doc)
    model = ScriptedModel(
        turn(tools=[("fixture__fail", {}), ("down__echo", {"text": "x"})]), turn("Araçlar hatalı.")
    )
    assert harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "completed"
    results = {p["name"]: p for p in _payloads(pg, run_id, "tool_result")}
    assert results["fixture__fail"]["is_error"] is True
    assert results["down__echo"]["is_error"] is True
    assert results["down__echo"]["error_code"] == "tool_unreachable"
    assert "tool_unreachable" in model.calls[-1][-1]["content"]


def test_06a_mcp_action_call_limit(harness, pg, project, mcp_server, loopback):
    register(pg, loopback, project, mcp_server.url, {"echo": {"max_calls_per_run": 1}})
    run_id = seed_run(pg, project, agent(["echo"], limits={"max_tool_calls": 5}))
    model = ScriptedModel(
        turn(tools=[(ECHO, {"text": "a"})]), turn(tools=[(ECHO, {"text": "b"})]), turn("x")
    )
    assert harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "failed"
    row = run_row(pg, run_id)
    assert row["error_code"] == "limit_reached"
    error = _payloads(pg, run_id, "error")[-1]
    assert error["limit"] == "max_calls_per_run" and error["detail"] == ECHO
    assert [c.arguments for c in _calls(mcp_server, run_id)] == [{"text": "a"}]


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ("missing_tool", "tool_not_found"),
        ("not_discovered", "tool_not_discovered"),
        ("disabled", "tool_action_unavailable"),
        ("gone", "tool_action_unavailable"),
        ("unknown_action", "tool_action_unavailable"),
    ],
)
def test_06a_mcp_set_up_refusals_end_the_run_with_a_code(
    harness,
    pg,
    project,
    mcp_server,
    loopback,
    setup,
    code,
):
    actions = {
        "missing_tool": None,
        "not_discovered": {"echo": {}},
        "disabled": {"echo": {"enabled": False}},
        "gone": {"echo": {"status": "missing"}},
        "unknown_action": {"big": {}},
    }[setup]
    if actions is not None:
        status = "registered" if setup == "not_discovered" else "discovered"
        register(pg, loopback, project, mcp_server.url, actions, status=status)
    run_id = seed_run(pg, project, agent(["echo"]))
    model = ScriptedModel()
    assert harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "failed"
    assert run_row(pg, run_id)["error_code"] == code
    assert model.calls == []


def test_06a_mcp_forward_user_signs_for_the_run_user(
    harness,
    pg,
    project,
    mcp_server,
    loopback,
    make_user,
):
    user_id, _ = make_user(memberships={project: ("user", "edit")})
    register(pg, loopback, project, mcp_server.url, {"echo": {}}, auth_type="forward_user")
    run_id = seed_run(pg, project, agent(["echo"]))
    pg.execute("UPDATE runs SET user_id = %s WHERE id = %s", (user_id, run_id))
    model = ScriptedModel(turn(tools=[(ECHO, {"text": "kim"})]), turn("Tamam."))
    assert harness.run(run_id, Ports(model, tools_factory=real_tools(loopback))) == "completed"
    (call,) = _calls(mcp_server, run_id)
    assert call.headers["authorization"] == f"Bearer {SERVICE_TOKEN}"
    token = call.headers["x-on-behalf-of"]
    # aud = [<tool_key>, OBO_AUDIENCE] (K-05a-0002 S3): the tool and the backend both accept it.
    for audience in ("fixture", loopback.obo_audience):
        claims = verify_on_behalf_of(token, audience=audience, settings=loopback)
        assert claims.sub == str(user_id) and claims.project_id == str(project)
