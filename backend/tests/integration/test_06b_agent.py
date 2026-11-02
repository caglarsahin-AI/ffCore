"""06b agent path: `agent:<project_key>/<agent_key>` through the facade. The run is the real 06a
runner with scripted model, retriever, tools and guard (as test_06a_runs_api), started and
followed by the facade: chunks, x_platform events, annotations, approval and resume, masked
arguments, X-Agent-Events: none, conversations (S3) and identity on the run row."""

import json

import pytest

from ffcore.runtime.graph import REDACTED_BLOCK
from ffcore.runtime.state import GuardResult, ToolOutcome
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import NET, make_key, project_key
from tests.integration.runs_fixtures import *  # noqa: F403 - fixtures
from tests.integration.runs_fixtures import InlineQueue, publish
from tests.integration.runtime_support import (
    Ports,
    ScriptedGuard,
    ScriptedModel,
    ScriptedRetriever,
    ScriptedTools,
    definition,
    run_row,
    source,
    turn,
)

SQL_TOOL = "mcp-sql__run_sql"
RAW = "WHERE tckn = 12345678901"


def _content(chunks):
    # The scripted model streams word by word, each followed by a space.
    text = "".join(ch["delta"].get("content") or "" for c in chunks for ch in c.get("choices", []))
    return text.strip()


def _platform(chunks):
    return [c["x_platform"] for c in chunks if "x_platform" in c]


@pytest.fixture
def agent(owner, pg, settings, harness, use_queue, facade):
    """A published contract assistant, a key with the agents scope, the facade client."""
    project, console = owner
    publish(pg, project, definition())
    key = make_key(console, project, scopes=["agents"])
    return project, console, key, facade(key), f"agent:{project_key(pg, project)}/asistan"


def _answer_ports():
    return Ports(ScriptedModel(turn("30 gün [1].")), ScriptedRetriever([source()]))


# --- 1: streaming answer with sources ---


def test_06b_1_stream_answer_with_sources(agent, harness, use_queue, pg):
    project, _, key, client, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))
    status, chunks, lines = client.stream(model, "Fesih süresi nedir?")
    assert status == 200
    assert lines[-1] == "data: [DONE]"
    assert {c["object"] for c in chunks} == {"chat.completion.chunk"}
    assert {c["model"] for c in chunks} == {model}
    assert _content(chunks) == "30 gün [1]."
    events = [p["event"] for p in _platform(chunks)]
    assert "sources" in events and events[0] == "progress"
    final = next(c for c in chunks if c["choices"] and c["choices"][0]["finish_reason"])
    assert final["choices"][0]["finish_reason"] == "stop"
    (citation,) = final["choices"][0]["delta"]["annotations"]
    assert citation["type"] == "url_citation"
    assert citation["url_citation"]["title"] == "hizmet-sozlesmesi.pdf"
    assert "30 gün [1]."[citation["url_citation"]["start_index"] :].startswith("[1]")
    assert chunks[-1]["usage"]["total_tokens"] == 15
    run_id = next(p["run_id"] for p in _platform(chunks) if p.get("run_id"))
    row = run_row(pg, run_id)
    assert (row["channel"], row["trigger_type"], row["status"]) == ("api", "api", "completed")
    assert row["user_id"] is None and str(row["api_key_id"]) == key["id"]


def test_06b_1_openai_client_streams_agent_answer(agent, harness, use_queue, app):
    """The official `openai` client, only base_url and api_key changed (brief acceptance)."""
    import openai
    from fastapi.testclient import TestClient

    from tests.integration.conftest import CONSOLE_ORIGIN
    from tests.integration.facade_support import CLIENT_IP

    _, _, key, _, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))
    with TestClient(app, base_url=CONSOLE_ORIGIN, client=(CLIENT_IP, 50000)) as http:
        client = openai.OpenAI(
            base_url=f"{CONSOLE_ORIGIN}/v1", api_key=key["key"], http_client=http
        )
        stream = client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Fesih süresi nedir?"}], stream=True
        )
        parts, annotations = [], []
        for chunk in stream:
            for choice in chunk.choices:
                parts.append(choice.delta.content or "")
                annotations += (choice.delta.model_extra or {}).get("annotations") or []
        listed = client.models.list()
    assert "".join(parts).strip() == "30 gün [1]."
    assert annotations and annotations[0]["url_citation"]["title"] == "hizmet-sozlesmesi.pdf"
    assert model in {m.id for m in listed.data}


# --- 11: non-streaming ---


def test_06b_11_agent_non_stream(agent, harness, use_queue):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))
    response = client.chat(model, "Fesih süresi nedir?")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["object"] == "chat.completion" and data["model"] == model
    message = data["choices"][0]["message"]
    assert message["content"].strip() == "30 gün [1]." and message["annotations"]
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert data["x_platform"]["run_id"] == response.headers["X-Run-Id"]
    assert response.headers["X-Conversation-Id"]


# --- 4: unpublished ---


def test_06b_4_unpublished_agent_404(agent, pg):
    project, _, _, client, _ = agent
    pg.execute(
        "INSERT INTO agents (id, project_id, key, name, created_by)"
        " VALUES (gen_random_uuid(), %s, 'taslak', 'T', 't')",
        (project,),
    )
    response = client.chat(f"agent:{project_key(pg, project)}/taslak")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "agent_not_published"
    missing = client.chat(f"agent:{project_key(pg, project)}/yok")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "model_not_found"


# --- 8 / 9: approval, resume, masked arguments ---


def _approval_agent(pg, project):
    publish(
        pg,
        project,
        definition(
            knowledge=[],
            tools=[{"tool_key": "mcp-sql", "actions": ["run_sql"]}],
            approval={"actions": ["mcp-sql.run_sql"], "assign_to": "analyst"},
            limits={"max_tool_calls": 1},
        ),
        key="sql",
    )


class RedactingGuard(ScriptedGuard):
    """tool.pre redacts the identity number: what the events may carry is the guard's output."""

    async def check(self, stage, text, *, tool=None):
        self.seen.append((stage, text))
        return GuardResult("allow", text.replace("12345678901", "[TR_NATIONAL_ID]"), None, None, 0)


def _sql_ports(guard=None):
    tools = ScriptedTools(
        schema=[{"type": "function", "function": {"name": SQL_TOOL, "parameters": {}}}],
        approval={SQL_TOOL},
        results={SQL_TOOL: ToolOutcome("rows: 3", False, 7, False, 5)},
    )
    model = ScriptedModel(turn(tools=[(SQL_TOOL, {"sql": f"select 1 {RAW}"})]), turn("3."))
    return Ports(model, tools=tools, guard=guard or RedactingGuard())


def test_06b_8_approval_required_then_resume(
    agent, pg, harness, use_queue, make_user, client_factory
):
    project, console, _, client, _ = agent
    _approval_agent(pg, project)
    use_queue(InlineQueue(harness, _sql_ports()))
    model = f"agent:{project_key(pg, project)}/sql"
    status, chunks, lines = client.stream(model, "kaç kayıt var?")
    assert status == 200 and lines[-1] == "data: [DONE]"
    last = [c for c in chunks if c["choices"] and c["choices"][0]["finish_reason"]][-1]
    assert last["choices"][0]["finish_reason"] == "approval_required"
    approval = last["x_platform"]
    assert approval["event"] == "approval_required" and approval["approval_id"]
    run_id = approval["run_id"]

    # The client cannot approve (C4): the console resume refuses an API key.
    resume_url = f"/api/v1/projects/{project}/runs/{run_id}/resume"
    denied = client._client.post(
        resume_url, json={"decision": "approved"}, headers=client.headers()
    )
    assert denied.status_code in (403, 404)
    # Before a person decides, X-Resume-Run-Id says so.
    waiting = client.chat(model, "devam", headers={"X-Resume-Run-Id": run_id})
    assert waiting.status_code == 409
    assert waiting.json()["error"]["code"] == "run_still_waiting"

    _, email = make_user(memberships={project: ("analyst", "edit")})
    with client_factory(email).stream("POST", resume_url, json={"decision": "approved"}) as r:
        assert r.status_code == 200
        list(r.iter_lines())
    status, rest, _ = client.stream(model, "devam", headers={"X-Resume-Run-Id": run_id})
    assert status == 200
    assert "tool_result" in [p["event"] for p in _platform(rest)]
    assert _content(rest) == "3."
    assert rest[-2]["choices"][0]["finish_reason"] == "stop" or any(
        c["choices"] and c["choices"][0]["finish_reason"] == "stop" for c in rest
    )


@pytest.mark.parametrize("events", ["all", "none"])
def test_06b_9_approval_required_carries_no_raw_args(events, agent, pg, harness, use_queue):
    project, _, _, client, _ = agent
    _approval_agent(pg, project)
    use_queue(InlineQueue(harness, _sql_ports()))
    model = f"agent:{project_key(pg, project)}/sql"
    status, chunks, lines = client.stream(model, "kaç?", headers={"X-Agent-Events": events})
    assert status == 200
    body = "\n".join(lines)
    assert "12345678901" not in body
    approval = _platform(chunks)[-1]
    assert approval["event"] == "approval_required"
    if events == "none":
        assert set(approval) == {"event", "run_id", "approval_id", "expires_at"}
        assert [p["event"] for p in _platform(chunks)] == ["approval_required"]
    else:
        assert "[TR_NATIONAL_ID]" in json.dumps(approval["arguments"])
    use_queue(InlineQueue(harness, _sql_ports()))
    non_stream = client.chat(model, "kaç?", headers={"X-Agent-Events": events})
    assert "12345678901" not in non_stream.text


@pytest.mark.parametrize("events", ["all", "none"])
def test_06b_9_blocked_tool_call_never_shows_arguments(events, agent, pg, harness, use_queue):
    project, _, _, client, _ = agent
    _approval_agent(pg, project)
    use_queue(InlineQueue(harness, _sql_ports(ScriptedGuard(block={"tool.pre": "tckn"}))))
    model = f"agent:{project_key(pg, project)}/sql"
    status, chunks, lines = client.stream(model, "kaç?", headers={"X-Agent-Events": events})
    assert status == 200
    assert "12345678901" not in "\n".join(lines) and "tckn" not in "\n".join(lines)
    calls = [p for p in _platform(chunks) if p["event"] == "tool_call"]
    if events == "all":
        assert calls and calls[0]["arguments"] == REDACTED_BLOCK
    else:
        assert calls == []


# --- 10: X-Agent-Events: none ---


def test_06b_10_agent_events_none(agent, harness, use_queue):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))
    status, chunks, _ = client.stream(model, "Fesih?", headers={"X-Agent-Events": "none"})
    assert status == 200
    assert _platform(chunks) == []
    assert _content(chunks) == "30 gün [1]."
    final = next(c for c in chunks if c["choices"] and c["choices"][0]["finish_reason"])
    assert final["choices"][0]["delta"]["annotations"]  # OpenAI's own field stays
    bad = client.chat(model, "x", headers={"X-Agent-Events": "some"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "agent_events_invalid"


# --- 13: conversations ---


def test_06b_13_messages_one_shot_context(agent, harness, use_queue, pg):
    _, _, _, client, model = agent
    ports = _answer_ports()
    use_queue(InlineQueue(harness, ports))
    history = [
        {"role": "user", "content": "Sözleşme hangisi?"},
        {"role": "assistant", "content": "Hizmet sözleşmesi."},
        {"role": "user", "content": "Fesih süresi nedir?"},
    ]
    response = client.chat(model, messages=history)
    assert response.status_code == 200, response.text
    conversation = response.headers["X-Conversation-Id"]
    rows = pg.execute(
        "SELECT role, content, run_id FROM messages WHERE conversation_id = %s ORDER BY created_at",
        (conversation,),
    ).fetchall()
    assert [(r[0], r[1]) for r in rows[:3]] == [(m["role"], m["content"]) for m in history]
    assert rows[0][2] is None and rows[2][2] is not None
    # The question is the run's input; the earlier turns are history rows, which 06a's
    # context_factory reads (`_history`; the scripted harness here does not wire history).
    assert ports.model.calls[0][-1]["content"].endswith("Fesih süresi nedir?")


def test_06b_13_conversation_header_persists(agent, harness, use_queue, pg, facade, owner):
    project, console, _, client, model = agent
    use_queue(InlineQueue(harness, Ports(ScriptedModel(turn("A."), turn("B.")))))
    first = client.chat(model, "ilk")
    conversation = first.headers["X-Conversation-Id"]
    second = client.chat(model, "ikinci", headers={"X-Conversation-Id": conversation})
    assert second.status_code == 200, second.text
    assert second.headers["X-Conversation-Id"] == conversation
    runs = pg.execute(
        "SELECT count(*) FROM runs WHERE conversation_id = %s", (conversation,)
    ).fetchone()[0]
    assert runs == 2
    # History and header together: refused, not merged.
    both = client.chat(
        model,
        messages=[{"role": "user", "content": "a"}, {"role": "user", "content": "b"}],
        headers={"X-Conversation-Id": conversation},
    )
    assert both.status_code == 400
    # Another key of the project does not continue this key's conversation.
    other = facade(make_key(console, project, scopes=["agents"]))
    foreign = other.chat(model, "x", headers={"X-Conversation-Id": conversation})
    assert foreign.status_code == 404


def test_06b_13_history_goes_through_input_guard(agent, harness, use_queue, pg):
    project, console, _, client, model = agent
    response = console.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={
            "key": "default",
            "name": "Strict",
            "mode": "enforce",
            "rules": [{"type": "secrets", "action": "block", "stages": ["input.pre"]}],
        },
    )
    assert response.status_code == 201, response.text
    use_queue(InlineQueue(harness, _answer_ports()))
    before = pg.execute("SELECT count(*) FROM runs WHERE project_id = %s", (project,)).fetchone()[0]
    blocked = client.chat(
        model,
        messages=[
            {"role": "user", "content": "anahtar sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00"},
            {"role": "assistant", "content": "tamam"},
            {"role": "user", "content": "Fesih?"},
        ],
    )
    assert blocked.status_code == 400 and blocked.json()["error"]["code"] == "guardrail_blocked"
    after = pg.execute("SELECT count(*) FROM runs WHERE project_id = %s", (project,)).fetchone()[0]
    assert after == before


def test_06b_13_system_messages_refused_on_agent_path(agent):
    _, _, _, client, model = agent
    response = client.chat(
        model, messages=[{"role": "system", "content": "x"}, {"role": "user", "content": "y"}]
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "role_not_supported"


# --- 3: the user a key acts for ---


def test_06b_3_impersonate_user_field_runs_as_user(
    owner, pg, settings, harness, use_queue, facade, make_user
):
    project, console = owner
    publish(pg, project, definition())
    user_id, email = make_user(memberships={project: ("analyst", "edit")})
    key = make_key(console, project, scopes=["agents", "impersonate"], allowed_cidrs=NET)
    use_queue(InlineQueue(harness, _answer_ports()))
    response = facade(key).chat(f"agent:{project_key(pg, project)}/asistan", "Fesih?", user=email)
    assert response.status_code == 200, response.text
    row = run_row(pg, response.headers["X-Run-Id"])
    assert row["user_id"] == user_id and str(row["api_key_id"]) == key["id"]
    audit = pg.execute(
        "SELECT actor_type, actor_id FROM audit_events WHERE action = 'start_run'"
        " AND resource_id = %s",
        (response.headers["X-Run-Id"],),
    ).fetchone()
    assert audit == ("user", str(user_id))


def test_06b_3_no_scope_key_runs_as_key(owner, pg, settings, harness, use_queue, facade, make_user):
    project, console = owner
    publish(pg, project, definition())
    _, email = make_user(memberships={project: ("analyst", "edit")})
    key = make_key(console, project, scopes=["agents"])
    use_queue(InlineQueue(harness, _answer_ports()))
    response = facade(key).chat(f"agent:{project_key(pg, project)}/asistan", "Fesih?", user=email)
    assert response.status_code == 200, response.text
    row = run_row(pg, response.headers["X-Run-Id"])
    assert row["user_id"] is None and str(row["api_key_id"]) == key["id"]
    audit = pg.execute(
        "SELECT actor_type FROM audit_events WHERE action = 'start_run' AND resource_id = %s",
        (response.headers["X-Run-Id"],),
    ).fetchone()
    assert audit == ("api_key",)


def test_06b_15_external_agent_fails_loud_until_06b_2(agent, pg):
    project, _, _, client, _ = agent
    publish(pg, project, definition(), key="uzak")
    pg.execute(
        "UPDATE agents SET kind = 'external' WHERE project_id = %s AND key = 'uzak'", (project,)
    )
    response = client.chat(f"agent:{project_key(pg, project)}/uzak", "x")
    assert response.status_code == 501
    assert response.json()["error"] == {
        "message": "External agents cannot be called through the facade yet.",
        "type": "api_error",
        "code": "external_agent_not_available",
    }
    # Not offered in the model list either (K-06b-0004).
    listed = {m["id"] for m in client.models().json()["data"]}
    assert f"agent:{project_key(pg, project)}/uzak" not in listed
    assert f"agent:{project_key(pg, project)}/asistan" in listed


def test_06b_15_console_cannot_create_external_agent(agent):
    project, console, _, _, _ = agent
    response = console.post(
        f"/api/v1/projects/{project}/agents",
        json={"key": "dis", "name": "Dış", "model": "chat-default", "kind": "external"},
    )
    assert response.status_code == 422


# --- review r2 MINOR-A: the SDK echo of an earlier answer ---


def test_06b_13_previous_agent_answer_sent_back_200(agent, harness, use_queue, pg):
    _, _, _, client, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))
    first = client.chat(model, "Fesih süresi nedir?")
    assert first.status_code == 200, first.text
    answer = first.json()["choices"][0]["message"]
    assert answer["annotations"]  # what an OpenAI SDK puts back into the history
    use_queue(InlineQueue(harness, _answer_ports()))  # the scripted model answers once per run
    response = client.chat(
        model,
        messages=[
            {"role": "user", "content": "Fesih süresi nedir?"},
            answer,
            {"role": "user", "content": "Peki ihbar?"},
        ],
    )
    assert response.status_code == 200, response.text
    run_id = response.headers["X-Run-Id"]
    after = pg.execute(
        "SELECT after FROM audit_events WHERE action = 'start_run' AND resource_id = %s",
        (run_id,),
    ).fetchone()[0]
    assert after["dropped_fields"] == ["messages[1].annotations"]


@pytest.mark.parametrize("name", ["temperature", "top_p", "seed", "max_tokens"])
def test_06b_7_agent_numeric_parameter_with_text_400(agent, harness, use_queue, pg, name):
    """K-06b-0018: the agent path checks the same parameter table, fail-loud; no run starts."""
    project, _, _, client, model = agent
    use_queue(InlineQueue(harness, _answer_ports()))  # a run that did start would finish (200)
    response = client.chat(model, "Fesih süresi nedir?", **{name: "ayse@example.test"})
    assert response.status_code == 400, response.text
    assert (response.json()["error"]["code"], response.json()["error"]["param"]) == (
        "invalid_parameter",
        name,
    )
    assert (
        pg.execute("SELECT count(*) FROM runs WHERE project_id = %s", (project,)).fetchone()[0] == 0
    )
