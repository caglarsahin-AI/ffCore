"""06b-2 external agent through the real app, Postgres, Redis and guardrail engine; the external
agent is a local fake OpenAI-compatible server (an internal host, ALLOWED_INTERNAL_HOSTS), never
a real outside system. Registration (admin + edit, key never readable, audit masked), publish,
/v1/models, the call (egress out, output.pre in, tool calls ignored, limits, one audit event per
call, nothing but the registered key leaves), stream shape, refusals."""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ffcore.api.facade_schemas import EXTERNAL_X_PLATFORM_EVENTS
from ffcore.services.facade_external import MAX_EXTERNAL_RESPONSE_BYTES
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import make_key, project_key

KEY = "dummy-not-secret-external-key-0001"
NEW_KEY = "dummy-not-secret-external-key-0002"
EMAIL = "ayse.yilmaz@example.test"
SECRET = "sk-ant-REDACTEDREDACTEDREDACTEDREDACTED00"


class _Agent(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
        self.server.seen.append(
            {
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body,
            }
        )
        mode = self.path.split("/")[1]
        message = {"role": "assistant", "content": f"Cevap: {body['messages'][-1]['content']}"}
        if mode == "tools":
            message["tool_calls"] = [
                {"id": "c", "type": "function", "function": {"name": "rm", "arguments": "{}"}}
            ]
        elif mode == "placeholder":
            message["content"] = "Kayit <<PII_1>> bulundu"
        elif mode == "secret":
            message["content"] = f"anahtar {SECRET}"
        elif mode == "big":
            message["content"] = "x" * (MAX_EXTERNAL_RESPONSE_BYTES + 1)
        elif mode == "slow":
            time.sleep(2.5)
        data = json.dumps(
            {"choices": [{"index": 0, "message": message, "finish_reason": "stop"}]}
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture(scope="module")
def fake_agent():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Agent)
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


@pytest.fixture
def ext_settings(app, app_settings, database_url):
    from pydantic import SecretStr

    from ffcore.core.config import get_settings

    s = app_settings.model_copy(
        update={
            # The installation's own internal hosts stay; the fake agent's address is added.
            "allowed_internal_hosts": [*app_settings.allowed_internal_hosts, "127.0.0.1"],
            "database_url": SecretStr(database_url),
            "redis_url": SecretStr(os.environ["REDIS_URL"]),
            "llm_call_timeout_s": 2,
        }
    )
    app.dependency_overrides[get_settings] = lambda: s
    return s


@pytest.fixture
def ext(ext_settings, owner, fake_agent, facade, pg):
    """A project, its admin console, a registered and published external agent `dis` whose base
    URL picks the fake's behaviour, and an `agents` key's facade client."""
    project, console = owner
    port = fake_agent.server_address[1]

    def register(key="dis", mode="ok", publish=True):
        response = console.post(
            f"/api/v1/projects/{project}/agents/external",
            json={
                "key": key,
                "name": "Dış",
                "base_url": f"http://127.0.0.1:{port}/{mode}",
                "model": "uzak-model",
                "api_key": KEY,
            },
        )
        assert response.status_code == 201, response.text
        agent = response.json()
        if publish:
            done = console.post(f"/api/v1/projects/{project}/agents/{agent['id']}/external/publish")
            assert done.status_code == 200, done.text
        return agent, f"agent:{project_key(pg, project)}/{key}"

    client = facade(make_key(console, project, scopes=["agents"]))
    return project, console, client, register


def _audit(pg, action, resource_id=None):
    rows = pg.execute(
        "SELECT outcome, before, after FROM audit_events WHERE action = %s"
        + (" AND resource_id = %s" if resource_id else "")
        + " ORDER BY ts",
        (action, resource_id) if resource_id else (action,),
    ).fetchall()
    return rows


# --- registration ---


@pytest.mark.parametrize(("role", "access"), [("analyst", "edit"), ("admin", "read")])
def test_06b2_2_register_requires_admin_edit(
    ext, make_user, client_factory, fake_agent, pg, role, access
):
    project, _, _, _ = ext
    _, email = make_user(memberships={project: (role, access)})
    response = client_factory(email).post(
        f"/api/v1/projects/{project}/agents/external",
        json={
            "key": "yetkisiz",
            "name": "x",
            "base_url": f"http://127.0.0.1:{fake_agent.server_address[1]}/ok",
            "model": "m",
            "api_key": KEY,
        },
    )
    assert response.status_code == 403
    assert ("denied",) in [(r[0],) for r in _audit(pg, "create_external_agent")]
    assert pg.execute("SELECT count(*) FROM agents WHERE key = 'yetkisiz'").fetchone() == (0,)


def test_06b2_3_api_key_never_readable(ext, pg):
    project, console, _, register = ext
    agent, _ = register(publish=False)
    assert agent["kind"] == "external" and agent["external"]["api_key"] == "***"
    got = console.get(f"/api/v1/projects/{project}/agents/{agent['id']}/external")
    assert got.status_code == 200 and KEY not in got.text
    updated = console.put(
        f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"api_key": NEW_KEY}
    )
    assert updated.status_code == 200 and NEW_KEY not in updated.text
    (stored,) = pg.execute(
        "SELECT external_config FROM agents WHERE id = %s", (agent["id"],)
    ).fetchone()
    assert KEY.encode() not in bytes(stored) and NEW_KEY.encode() not in bytes(stored)
    audit = json.dumps(
        _audit(pg, "create_external_agent") + _audit(pg, "update_external_agent"), default=str
    )
    assert KEY not in audit and NEW_KEY not in audit
    # the agent's own read and the manifest never carry it either
    assert KEY not in console.get(f"/api/v1/projects/{project}/agents/{agent['id']}").text


def test_06b2_4_register_url_policy(ext):
    project, console, _, _ = ext
    for url in ("file:///etc/passwd", "gopher://127.0.0.1/x", "http://10.0.0.5/v1"):
        response = console.post(
            f"/api/v1/projects/{project}/agents/external",
            json={"key": "kotu", "name": "x", "base_url": url, "model": "m", "api_key": KEY},
        )
        assert response.status_code == 422, url
        assert response.json()["error"]["code"] == "external_agent_url_refused", url


def test_06b2_4_publish_checks_url_again(ext, ext_settings, app):
    from ffcore.core.config import get_settings

    project, console, _, register = ext
    agent, _ = register(publish=False)
    # The installation's internal hosts changed after registration: publishing refuses.
    stricter = ext_settings.model_copy(
        update={
            "allowed_internal_hosts": [
                h for h in ext_settings.allowed_internal_hosts if h != "127.0.0.1"
            ]
        }
    )
    app.dependency_overrides[get_settings] = lambda: stricter
    done = console.post(f"/api/v1/projects/{project}/agents/{agent['id']}/external/publish")
    assert done.status_code == 422
    assert done.json()["error"]["code"] == "external_agent_url_refused"


def test_06b2_17_no_versions_no_manifest_no_kind_change(ext):
    project, console, _, register = ext
    agent, _ = register()
    base = f"/api/v1/projects/{project}/agents/{agent['id']}"
    for method, path, body in (
        ("get", "/versions", None),
        ("post", "/versions", {}),
        ("post", "/publish", {"version": 1}),
        ("post", "/rollback", {"version": 1}),
    ):
        kwargs = {} if body is None else {"json": body}
        response = getattr(console, method)(base + path, **kwargs)
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "external_agent_has_no_versions"
    exported = console.get(base + "/manifest")
    assert exported.status_code == 422
    assert exported.json()["error"]["code"] == "external_agent_not_available"
    assert console.patch(base, json={"kind": "native"}).status_code == 422
    assert console.put(base + "/external", json={"kind": "native"}).status_code == 422


# --- the facade ---


def test_06b2_13_models_lists_published_external(ext):
    _, _, client, register = ext
    _, draft = register(key="taslak", publish=False)
    _, published = register(key="yayinda")
    listed = {m["id"] for m in client.models().json()["data"]}
    assert published in listed and draft not in listed
    assert client.chat(draft, "x").status_code == 404


def test_06b2_12_answer_and_what_leaves(ext, fake_agent, pg):
    _, _, client, register = ext
    agent, model = register()
    before = len(fake_agent.seen)
    # The client's own headers never travel (an X-On-Behalf-Of from a key without
    # `impersonate` is refused before this point, C2).
    response = client.chat(model, "Merhaba", headers={"X-Trace-Me": "dummy-not-secret"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["model"] == model and data["object"] == "chat.completion"
    assert data["choices"][0]["message"] == {"role": "assistant", "content": "Cevap: Merhaba"}
    sent = fake_agent.seen[before]
    assert sent["headers"]["authorization"] == f"Bearer {KEY}"
    assert not any(h.startswith("x-") for h in sent["headers"])
    assert sent["body"] == {
        "model": "uzak-model",
        "messages": [{"role": "user", "content": "Merhaba"}],
        "stream": False,
    }
    # one audit event per call: host, status, time, bytes; no content
    ((outcome, _, after),) = _audit(pg, "external_agent_call", agent["id"])
    assert outcome == "success"
    assert after["host"] == "127.0.0.1" and after["upstream_status"] == 200
    assert after["response_bytes"] > 0 and "duration_ms" in after
    assert "Merhaba" not in json.dumps(after)


def test_06b2_11_egress_masks_what_leaves(ext, fake_agent, pg):
    from ffcore.guardrails.settings import get_guardrail_settings

    project, _, client, register = ext
    _, model = register()
    before = len(fake_agent.seen)
    assert client.chat(model, f"bana {EMAIL} adresinden yaz").status_code == 200
    sent = json.dumps(fake_agent.seen[before]["body"], ensure_ascii=False)
    if get_guardrail_settings().guardrail_egress_enabled:
        assert EMAIL not in sent
        events = pg.execute(
            "SELECT source FROM guardrail_events WHERE project_id = %s AND stage = 'egress'",
            (project,),
        ).fetchall()
        assert ("api",) in events
    else:  # airgap: the stage does not exist (08 S3)
        assert EMAIL in sent


def test_06b2_11_output_pre_checks_the_answer(ext):
    project, console, client, register = ext
    response = console.post(
        f"/api/v1/projects/{project}/guardrail-policies",
        json={
            "key": "default",
            "name": "Dış",
            "mode": "enforce",
            "rules": [{"type": "secrets", "action": "block", "stages": ["output.pre"]}],
        },
    )
    assert response.status_code == 201, response.text
    _, model = register(mode="secret")
    answer = client.chat(model, "x")
    assert answer.status_code == 400 and SECRET not in answer.text
    assert answer.json()["error"]["code"] == "guardrail_blocked"


def test_06b2_11_placeholder_in_answer_is_not_opened(ext):
    """A token-like string from outside never maps to this request's tokens (fresh scope)."""
    _, _, client, register = ext
    _, model = register(mode="placeholder")
    response = client.chat(model, "x")
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Kayit <<PII_1>> bulundu"


def test_06b2_10_tool_calls_ignored(ext):
    _, _, client, register = ext
    _, model = register(mode="tools")
    message = client.chat(model, "Sil").json()["choices"][0]["message"]
    assert message == {"role": "assistant", "content": "Cevap: Sil"}


def test_06b2_8_and_9_limits_fail_with_codes(ext, pg):
    _, _, client, register = ext
    big, big_model = register(key="buyuk", mode="big")
    response = client.chat(big_model, "x")
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "external_agent_response_too_large"
    assert "xxxx" not in response.text
    slow, slow_model = register(key="yavas", mode="slow")
    response = client.chat(slow_model, "x")
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "external_agent_timeout"
    for agent, code in ((big, "too_large"), (slow, "egress_timeout")):
        ((outcome, _, after),) = _audit(pg, "external_agent_call", agent["id"])
        assert outcome == "error" and after["error_code"] == code


def test_06b2_14_stream_shape(ext):
    _, _, client, register = ext
    _, model = register()
    status, chunks, lines = client.stream(model, "Merhaba")
    assert status == 200 and lines[-1] == "data: [DONE]"
    events = [c["x_platform"]["event"] for c in chunks if "x_platform" in c]
    assert events == ["progress"] and set(events) <= set(EXTERNAL_X_PLATFORM_EVENTS)
    text = "".join(ch["delta"].get("content") or "" for c in chunks for ch in c["choices"])
    assert text == "Cevap: Merhaba"
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    _, quiet, _ = client.stream(model, "Merhaba", headers={"X-Agent-Events": "none"})
    assert not any("x_platform" in c for c in quiet)


def test_06b2_14_stream_failure_is_an_error_event(ext):
    _, _, client, register = ext
    _, model = register(mode="big")
    status, chunks, lines = client.stream(model, "x")
    assert status == 200 and lines[-1] == "data: [DONE]"
    assert chunks[-1]["error"]["code"] == "external_agent_response_too_large"


def test_06b2_19_refused_fields(ext, fake_agent):
    _, _, client, register = ext
    _, model = register()
    before = len(fake_agent.seen)
    tools = client.chat(model, "x", tools=[{"type": "function", "function": {"name": "f"}}])
    assert tools.status_code == 400 and tools.json()["error"]["code"] == "unsupported_field"
    system = client._client.post(
        "/v1/chat/completions",
        json={"model": model, "messages": [{"role": "system", "content": "x"}]},
        headers=client.headers(),
    )
    assert system.status_code == 400
    assert len(fake_agent.seen) == before  # nothing reached the external agent


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_06b2_15_numeric_non_finite_over_http(ext, literal):
    _, _, client, register = ext
    _, model = register()
    raw = (
        f'{{"model": "{model}", "messages": [{{"role": "user", "content": "x"}}],'
        f' "temperature": {literal}}}'
    )
    response = client._client.post(
        "/v1/chat/completions",
        content=raw,
        headers=client.headers({"Content-Type": "application/json"}),
    )
    assert response.status_code == 400, response.text
    assert response.json()["error"]["code"] == "invalid_parameter"
    assert response.json()["error"]["param"] == "temperature"
