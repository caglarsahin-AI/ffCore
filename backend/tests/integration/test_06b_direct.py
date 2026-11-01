"""06b direct model path: an OpenAI request to `<project>.<model>` through the real LiteLLM and
the fake provider (01). Guardrail `input.pre`, `egress`, `output.pre` really run (K-06b-0001
item 2; S4, S9), the 03c quota answers 429, the answer and chunks keep OpenAI's shape with the
public model name, and nothing outside the OpenAI parameters is passed on."""

import json
import uuid

import pytest

from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import make_key, project_key
from tests.integration.litellm_support import fake_requests, run_reconcile

pytestmark = pytest.mark.usefixtures("clean_litellm")

SECRET = "sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00"
EMAIL = "ayse.yilmaz@example.test"
TOOL = {
    "type": "function",
    "function": {
        "name": "lookup",
        "description": "Look something up.",
        "parameters": {
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    },
}


@pytest.fixture
def facade_settings(app, llm_settings, database_url):
    import os

    from pydantic import SecretStr

    from ffcore.core.config import get_settings
    from tests.integration.conftest import CONSOLE_ORIGIN

    s = llm_settings.model_copy(
        update={
            "console_origins": [CONSOLE_ORIGIN],
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
        }
    )
    app.dependency_overrides[get_settings] = lambda: s
    return s


@pytest.fixture
def direct(database_url, pg, catalog, facade_settings, make_user, client_factory, facade):
    """A project with `chat-default` (fake `ok-model`) and `tooly` (fake `tool-model`), an admin
    console and a chat_direct key."""
    project = catalog.project()
    provider = catalog.provider([project])
    catalog.model(project, provider, key="chat-default", model_id="ok-model")
    catalog.model(project, provider, key="tooly", model_id="tool-model")
    run_reconcile(database_url, facade_settings)
    # run_reconcile resets the database module; the app uses the test database again.
    from ffcore.core import db

    db.configure(database_url, pooled=False)
    _, email = make_user(memberships={project: ("admin", "edit")})
    console = client_factory(email)
    key = make_key(console, project, scopes=["chat_direct"])
    return project, console, key, facade(key)


def _policy(console, project, rules, mode="enforce"):
    response = console.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={"key": "default", "name": "Facade", "mode": mode, "rules": rules},
    )
    assert response.status_code == 201, response.text


def _tool_turn(result_text):
    """A conversation whose last message is a tool result: the fake answers 'hello ' + it."""
    return [
        {"role": "user", "content": "look"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {"id": "c1", "type": "function", "function": {"name": "lookup", "arguments": "{}"}}
            ],
        },
        {"role": "tool", "tool_call_id": "c1", "content": result_text},
    ]


def _guard_events(pg, project, stage):
    return pg.execute(
        "SELECT action_taken, source FROM guardrail_events WHERE project_id = %s AND stage = %s",
        (project, stage),
    ).fetchall()


# --- 2 / 11: shape ---


def test_06b_11_non_stream_completion_shape(direct, pg):
    project, _, _, client = direct
    response = client.chat(f"{project_key(pg, project)}.chat-default")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == f"{project_key(pg, project)}.chat-default"
    assert data["choices"][0]["message"] == {"role": "assistant", "content": "hello"}
    assert data["choices"][0]["finish_reason"] == "stop"
    assert data["usage"]["total_tokens"] > 0


def test_06b_2_stream_chunks_openai_shape(direct, pg):
    project, _, _, client = direct
    status, chunks, lines = client.stream("chat-default")  # the short name: own project
    assert status == 200
    assert lines[-1] == "data: [DONE]"
    assert {c["object"] for c in chunks} == {"chat.completion.chunk"}
    assert {c["model"] for c in chunks} == {f"{project_key(pg, project)}.chat-default"}
    assert len({c["id"] for c in chunks}) == 1
    text = "".join(ch["delta"].get("content") or "" for c in chunks for ch in c["choices"])
    assert text == "hello"
    assert chunks[-1]["usage"]["total_tokens"] > 0
    # Only the internal key reaches LiteLLM: the provider sees no client credential.
    assert all(client.key not in json.dumps(r) for r in fake_requests())


def test_06b_2_other_projects_model_404(direct, catalog):
    _, _, _, client = direct
    other = catalog.project("other57")
    assert other
    response = client.chat("other57.chat-default")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


# --- 2: guardrails on the direct path ---


def test_06b_2_direct_model_runs_input_pre(direct, pg):
    project, console, _, client = direct
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["input.pre"]}])
    response = client.chat("chat-default", f"anahtar {SECRET}")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "guardrail_blocked"
    assert fake_requests() == []  # the model was never called
    assert ("block", "api") in _guard_events(pg, project, "input.pre")


def test_06b_2_direct_model_egress_masks_what_leaves(direct, pg):
    from ffcore.guardrails.settings import get_guardrail_settings

    project, _, _, client = direct
    # The built-in default policy: PII tokenized at egress, enforced in every profile.
    response = client.chat("chat-default", f"bana {EMAIL} adresinden yaz")
    assert response.status_code == 200, response.text
    sent = json.dumps(fake_requests()[-1]["messages"], ensure_ascii=False)
    if get_guardrail_settings().guardrail_egress_enabled:
        assert EMAIL not in sent
        assert _guard_events(pg, project, "egress")
    else:  # airgap: the stage does not exist, nothing leaves the network anyway
        assert EMAIL in sent


def test_06b_2_tool_message_goes_through_egress(direct, pg):
    from ffcore.guardrails.settings import get_guardrail_settings

    project, _, _, client = direct
    if not get_guardrail_settings().guardrail_egress_enabled:
        pytest.skip("NOT_RUN: GUARDRAIL_EGRESS_ENABLED=false in this environment")
    response = client._client.post(
        "/v1/chat/completions",
        json={"model": "tooly", "messages": _tool_turn(f"kayit {EMAIL}"), "tools": [TOOL]},
        headers=client.headers(),
    )
    assert response.status_code == 200, response.text
    assert EMAIL not in json.dumps(fake_requests()[-1], ensure_ascii=False)


def test_06b_2_direct_model_output_pre_blocks_400(direct, pg):
    project, console, _, client = direct
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["output.pre"]}])
    response = client._client.post(
        "/v1/chat/completions",
        json={"model": "tooly", "messages": _tool_turn(SECRET), "tools": [TOOL]},
        headers=client.headers(),
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "guardrail_blocked"
    assert SECRET not in response.text
    assert ("block", "api") in _guard_events(pg, project, "output.pre")


def test_06b_4_stream_output_buffered_then_checked(direct, pg):
    project, console, _, client = direct
    _policy(
        console,
        project,
        [{"type": "pii", "stages": ["output.pre"], "pii_policy_key": "default"}],
    )
    status, chunks, lines = client.stream(
        "tooly", messages=_tool_turn(f"kayit {EMAIL}"), tools=[TOOL]
    )
    assert status == 200
    assert chunks[0]["x_platform"] == {"event": "progress", "kind": "output_buffered"}
    text = "".join(ch["delta"].get("content") or "" for c in chunks for ch in c["choices"])
    assert text.startswith("hello") and EMAIL not in text
    assert EMAIL not in "\n".join(lines)
    assert lines[-1] == "data: [DONE]"


def test_06b_4_stream_block_is_an_error_event(direct, pg):
    project, console, _, client = direct
    _policy(console, project, [{"type": "secrets", "action": "block", "stages": ["output.pre"]}])
    status, chunks, lines = client.stream("tooly", messages=_tool_turn(SECRET), tools=[TOOL])
    assert status == 200  # headers went out with the output_buffered progress
    errors = [json.loads(line[6:]) for line in lines if line.startswith('data: {"error"')]
    assert errors and errors[0]["error"]["code"] == "guardrail_blocked"
    assert SECRET not in "\n".join(lines)
    assert lines[-1] == "data: [DONE]"


# --- S9: the client's own tools ---


def test_06b_9_client_tools_pass_and_calls_come_back(direct):
    _, _, _, client = direct
    response = client._client.post(
        "/v1/chat/completions",
        json={"model": "tooly", "messages": [{"role": "user", "content": "x"}], "tools": [TOOL]},
        headers=client.headers(),
    )
    assert response.status_code == 200, response.text
    choice = response.json()["choices"][0]
    assert choice["finish_reason"] == "tool_calls"
    call = choice["message"]["tool_calls"][0]
    assert call["function"]["name"] == "lookup"
    assert json.loads(call["function"]["arguments"])["q"]
    assert fake_requests()[-1]["tools"][0]["function"]["name"] == "lookup"


# --- 6: quota and usage ---


def test_06b_6_quota_exceeded_429_openai_shape(direct, pg):
    project, _, _, client = direct
    pg.execute(
        "INSERT INTO quotas (id, project_id, scope_type, scope_id, label, windows, tokens, budget,"
        " action, created_by) VALUES (%s, %s, 'project', %s, 't', '{\"rpm\": 1}', '{}', '{}',"
        " 'block', 'test')",
        (uuid.uuid4(), project, project),
    )
    assert client.chat("chat-default").status_code == 200
    second = client.chat("chat-default")
    assert second.status_code == 429
    assert second.json()["error"] == {
        "message": "A quota of this project is exhausted.",
        "type": "rate_limit_error",
        "code": "quota_exceeded",
    }
    assert len(fake_requests()) == 1


def test_06b_6_usage_row_has_api_key(direct, pg):
    project, _, key, client = direct
    assert client.chat("chat-default").status_code == 200
    row = pg.execute(
        "SELECT api_key_id, input_tokens FROM usage_daily WHERE project_id = %s", (project,)
    ).fetchone()
    assert str(row[0]) == key["id"] and row[1] > 0


# --- 7: what the facade refuses ---


def test_06b_7_unknown_parameter_400(direct):
    _, _, _, client = direct
    response = client.chat("chat-default", api_base="http://elsewhere/v1")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "parameter_not_supported"
    assert fake_requests() == []


def test_06b_7_image_parts_400(direct):
    _, _, _, client = direct
    response = client._client.post(
        "/v1/chat/completions",
        json={
            "model": "chat-default",
            "messages": [
                {
                    "role": "user",
                    "content": [{"type": "image_url", "image_url": {"url": "http://x/y.png"}}],
                }
            ],
        },
        headers=client.headers(),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "content_type_not_supported"
