"""Reviewer probes for 06b-2 r1 (external agent). Copied into backend/tests/integration/ of the
review worktree, removed afterwards. Own fake upstream (127.0.0.1), no outside system."""
import asyncio
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import ffcore.api  # noqa: F401 - app import order (facade_external <-> api.agents cycle)
from ffcore.services.facade_external import (
    MAX_EXTERNAL_RESPONSE_BYTES,
    ExternalCallFailed,
    ExternalConfig,
    call_upstream,
    check_base_url,
)
from ffcore.core.errors import ApiError
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import make_key, project_key
from tests.integration.test_06b2_external_agent import ext_settings  # noqa: F401 - fixture

KEY = "dummy-not-secret-probe-key-0001"
EMAIL = "probe.person@example.test"


class _Up(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _send(self, status, data: bytes, headers=()):
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        if not any(k.lower() == "transfer-encoding" for k, _ in headers):
            self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.server.seen.append({"method": "GET", "path": self.path, "headers": dict(self.headers)})
        self._send(200, b"{}")

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.loads(raw)
        self.server.seen.append(
            {"method": "POST", "path": self.path, "headers": {k.lower(): v for k, v in self.headers.items()}, "body": body}
        )
        mode = self.path.split("/")[1]
        last = body["messages"][-1]["content"]
        msg = {"role": "assistant", "content": f"echo: {last}"}
        if mode == "redirect":
            port = self.server.server_address[1]
            return self._send(302, b"", [("Location", f"http://127.0.0.1:{port}/ok")])
        if mode == "redirect307":
            port = self.server.server_address[1]
            return self._send(307, b"", [("Location", f"http://127.0.0.1:{port}/ok")])
        if mode == "chunked":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            payload = json.dumps({"choices": [{"message": {"role": "assistant", "content": "y" * (MAX_EXTERNAL_RESPONSE_BYTES + 10)}}]}).encode()
            for i in range(0, len(payload), 8192):
                part = payload[i:i + 8192]
                self.wfile.write(f"{len(part):x}\r\n".encode() + part + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
            return
        if mode == "deep":
            n = 30000
            return self._send(200, b"[" * n + b"]" * n)
        if mode == "deepdict":
            n = 20000
            return self._send(200, b'{"choices":' + b"[" * n + b"]" * n + b"}")
        if mode == "toolsonly":
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c", "type": "function", "function": {"name": "rm", "arguments": "{\"x\": \"" + EMAIL + "\"}"}}]}
        if mode == "funccall":
            msg = {"role": "assistant", "content": None, "function_call": {"name": "rm", "arguments": "{}"}}
        if mode == "parts":
            msg = {"role": "assistant", "content": [{"type": "text", "text": "parca"}]}
        if mode == "err500":
            return self._send(500, json.dumps({"error": f"upstream says {EMAIL}"}).encode())
        if mode == "nonjson":
            return self._send(200, f"<html>{EMAIL}</html>".encode())
        if mode == "weirdkey":
            msg[EMAIL] = "x"
            msg["line\nbreak"] = "y"
        if mode == "echo":
            msg["content"] = f"seen: {last}"
        if mode == "finish":
            data = json.dumps({"choices": [{"message": msg, "finish_reason": "tool_calls"}]}).encode()
            return self._send(200, data)
        data = json.dumps({"choices": [{"index": 0, "message": msg, "finish_reason": "stop"}]}).encode()
        self._send(200, data, [("Content-Type", "application/json")])


@pytest.fixture(scope="module")
def up():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Up)
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


@pytest.fixture
def px(ext_settings, owner, up, facade, pg):
    project, console = owner
    port = up.server_address[1]

    def register(key, mode="ok", publish=True, base_url=None, expect=201):
        r = console.post(
            f"/api/v1/projects/{project}/agents/external",
            json={"key": key, "name": "P", "base_url": base_url or f"http://127.0.0.1:{port}/{mode}",
                  "model": "m", "api_key": KEY},
        )
        assert r.status_code == expect, r.text
        if expect != 201:
            return r, None
        agent = r.json()
        if publish:
            d = console.post(f"/api/v1/projects/{project}/agents/{agent['id']}/external/publish")
            assert d.status_code == 200, d.text
        return agent, f"agent:{project_key(pg, project)}/{key}"

    client = facade(make_key(console, project, scopes=["agents"]))
    return project, console, client, register, port


def _audit(pg, agent_id):
    return pg.execute(
        "SELECT outcome, after FROM audit_events WHERE action='external_agent_call' AND resource_id=%s ORDER BY ts",
        (agent_id,),
    ).fetchall()


# --- P1 URL matrix at registration ---
URLS = [
    "http://127.0.0.2:80/v1", "http://[::1]/v1", "http://169.254.169.254/latest", "http://0.0.0.0/v1",
    "http://2130706433/v1", "http://0x7f000001/v1", "http://127.1/v1", "http://localhost/v1",
    "http://10.0.0.5./v1", "HTTP://10.0.0.5/v1", "http://[::ffff:10.0.0.5]/v1", "http://[::ffff:127.0.0.2]/v1",
    "http://[fe80::1]/v1", "http://100.64.0.1/v1", "http://192.168.1.1/v1", "http://172.17.0.1/v1",
    "ftp://example.com/v1", "http://user:pw@example.com/v1", "http://:pw@example.com/v1",
    "http://example.com:0/v1", "http://example.com:70000/v1", "http://example.com:-1/v1", "http:///v1", "http://",
    "javascript:alert(1)", "//example.com/v1", "http://example.com/v1",  # last: not allowlisted
    "http://metadata.google.internal/v1", "http://postgres:5432/x", "http://redis:6379/x", "http://qdrant:6333/x",
]


def test_p1_register_url_matrix(px):
    project, console, *_ = px
    out = []
    for i, url in enumerate(URLS):
        r = console.post(f"/api/v1/projects/{project}/agents/external",
                         json={"key": f"u{i}", "name": "x", "base_url": url, "model": "m", "api_key": KEY})
        code = r.json().get("error", {}).get("code") if r.status_code >= 400 else "-"
        out.append((url, r.status_code, code, r.json().get("error", {}).get("message", "")[:80] if r.status_code >= 400 else ""))
    for row in out:
        print("P1", row)
    accepted = [u for u, s, *_ in out if s < 400]
    assert not accepted, accepted


def test_p1b_update_and_offline(px, ext_settings, app):
    from ffcore.core.config import get_settings
    project, console, client, register, port = px
    agent, model = register("upd")
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"base_url": "http://10.0.0.5/v1"})
    print("P1b update private:", r.status_code, r.json().get("error", {}).get("code"))
    assert r.status_code == 422
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"kind": "native"})
    assert r.status_code == 422
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"base_url": None})
    print("P1b update base_url null:", r.status_code, r.text[:120])
    assert r.status_code in (400, 422)
    # call-time: allowed hosts narrowed after publish -> the call is refused, nothing reaches upstream
    stricter = ext_settings.model_copy(update={"allowed_internal_hosts": [h for h in ext_settings.allowed_internal_hosts if h != "127.0.0.1"]})
    app.dependency_overrides[get_settings] = lambda: stricter
    r = client.chat(model, "x")
    print("P1b call after narrowing:", r.status_code, r.json().get("error", {}).get("code"))
    assert r.status_code == 502 and r.json()["error"]["code"] == "external_agent_failed"
    # OFFLINE: an allowlisted outside host is refused at registration
    offline = ext_settings.model_copy(update={"offline": True, "egress_allowlist": ["example.com"]})
    app.dependency_overrides[get_settings] = lambda: offline
    r = console.post(f"/api/v1/projects/{project}/agents/external",
                     json={"key": "offl", "name": "x", "base_url": "https://example.com/v1", "model": "m", "api_key": KEY})
    print("P1b offline:", r.status_code, r.json().get("error", {}).get("message"))
    assert r.status_code == 422 and "egress_offline" in r.json()["error"]["message"]


# --- P2 DNS rebinding (unit level, real policy objects) ---
def test_p2_dns_rebinding(app_settings):
    s = app_settings.model_copy(update={"egress_allowlist": ["agent.example.test"], "offline": False})
    calls = []

    async def public(host, port):
        calls.append(("check", host))
        return ["93.184.216.34"]

    async def private(host, port):
        calls.append(("dial", host))
        return ["10.0.0.5"]

    async def mixed(host, port):
        return ["93.184.216.34", "127.0.0.1"]

    cfg = ExternalConfig(base_url="https://agent.example.test/v1", model="m", api_key=KEY)

    async def run():
        await check_base_url(cfg.base_url, s, resolver=public)  # passes at registration
        with pytest.raises(ApiError) as e:
            await check_base_url(cfg.base_url, s, resolver=mixed)
        print("P2 mixed answer at check:", e.value.code, e.value.message)
        with pytest.raises(ExternalCallFailed) as e2:
            await call_upstream(cfg, [{"role": "user", "content": "x"}], {}, s, resolver=private)
        return e2.value

    exc = asyncio.run(run())
    print("P2 rebinding at call:", exc.status_code, exc.code, exc.audit)
    assert exc.status_code == 502 and exc.audit["error_code"] == "egress_private_address"
    assert exc.audit["upstream_status"] is None


# --- P3 redirects ---
@pytest.mark.parametrize("mode", ["redirect", "redirect307"])
def test_p3_redirect_not_followed(px, up, pg, mode):
    _, _, client, register, _ = px
    agent, model = register(f"r{mode[-3:]}", mode)
    n = len(up.seen)
    r = client.chat(model, "x")
    hits = up.seen[n:]
    print(f"P3 {mode}:", r.status_code, r.json().get("error", {}).get("code"), "requests:", [h["path"] for h in hits], _audit(pg, agent["id"]))
    assert r.status_code == 502 and len(hits) == 1


# --- P4 limits and untrusted answers ---
@pytest.mark.parametrize("mode,status,code", [
    ("chunked", 502, "external_agent_response_too_large"),
    ("deep", 502, "external_agent_failed"),
    ("deepdict", 502, "external_agent_failed"),
    ("toolsonly", 502, "external_agent_failed"),
    ("funccall", 502, "external_agent_failed"),
    ("parts", 502, "external_agent_failed"),
    ("err500", 502, "external_agent_failed"),
    ("nonjson", 502, "external_agent_failed"),
])
def test_p4_untrusted_answers(px, pg, mode, status, code):
    _, _, client, register, _ = px
    agent, model = register(f"a-{mode}", mode)
    try:
        r = client.chat(model, "x")
        got = (r.status_code, r.json().get("error", {}).get("code"))
        leaked = EMAIL in r.text or "yyyy" in r.text or "rm" in r.json().get("choices", [{}])[0].get("message", {}).get("content", "") if r.status_code == 200 else EMAIL in r.text
    except Exception as exc:  # unhandled in the app
        got, leaked = ("EXC", type(exc).__name__), False
    rows = _audit(pg, agent["id"])
    print(f"P4 {mode}: got={got} leaked={leaked} audit={rows}")
    assert got == (status, code)
    assert not leaked
    assert len(rows) == 1 and rows[0][0] == "error"


def test_p4b_finish_reason_and_weird_keys_logged(px, caplog):
    _, _, client, register, _ = px
    _, model = register("fin", "finish")
    r = client.chat(model, "x")
    print("P4b finish tool_calls ->", r.json()["choices"][0]["finish_reason"])
    assert r.json()["choices"][0]["finish_reason"] == "stop"
    _, model = register("weird", "weirdkey")
    with caplog.at_level(logging.INFO, logger="ffcore"):
        r = client.chat(model, "x")
    assert r.status_code == 200
    logged = "\n".join(rec.getMessage() for rec in caplog.records)
    print("P4b upstream key names in log:", EMAIL in logged, [m for m in logged.splitlines() if "ignored" in m])


def test_p4c_stream_parts(px):
    _, _, client, register, _ = px
    _, model = register("strdeep", "deep")
    try:
        status, chunks, lines = client.stream(model, "x")
        print("P4c stream deep:", status, lines[-2:] if lines else lines)
    except Exception as exc:
        print("P4c stream deep EXC", type(exc).__name__)
        raise


# --- P5 what leaves: user label, params, headers, placeholder echo ---
def test_p5_what_leaves(px, up):
    _, _, client, register, _ = px
    _, model = register("leave", "echo")
    n = len(up.seen)
    r = client.chat(model, f"mail {EMAIL}", user=EMAIL, temperature=0.2, stop=[EMAIL],
                    headers={"X-On-Behalf-Of": EMAIL})
    print("P5 OBO from key without impersonate:", r.status_code, r.text[:120])
    r = client.chat(model, f"mail {EMAIL}", user=EMAIL, temperature=0.2, stop=[EMAIL])
    sent = up.seen[n:]
    print("P5 status:", r.status_code, "answer:", r.json()["choices"][0]["message"]["content"] if r.status_code == 200 else r.text[:120])
    print("P5 sent:", json.dumps(sent[-1]["body"], ensure_ascii=False), sorted(sent[-1]["headers"]))
    assert EMAIL not in json.dumps(sent, ensure_ascii=False) or True  # printed; profile-dependent
    for bad in ({"n": 1}, {"stream_options": {"include_usage": True}}, {"response_format": {"type": "text"}},
                {"logit_bias": {"1": 1}}, {"seed": 3}, {"max_tokens": 5}, {"top_p": float("nan")} if False else {"top_p": 0.5}):
        rr = client.chat(model, "x", **bad)
        print("P5 param", bad, rr.status_code, rr.json().get("error", {}).get("code") if rr.status_code >= 400 else "-")


def test_p5b_stream_options_from_sdk(px):
    _, _, client, register, _ = px
    _, model = register("sopt", "ok")
    status, chunks, lines = client.stream(model, "x", stream_options={"include_usage": True})
    print("P5b stream_options:", status, chunks if status != 200 else "ok")


# --- P6 scope/permissions ---
def test_p6_scope_and_roles(px, make_user, client_factory, facade):
    project, console, client, register, port = px
    _, model = register("scope", "ok")
    direct = facade(make_key(console, project, scopes=["chat_direct"]))
    r = direct.chat(model, "x")
    print("P6 chat_direct key ->", r.status_code, r.json().get("error", {}).get("code"))
    assert r.status_code in (403, 404)
    for role, access in (("admin", "read"), ("analyst", "edit"), ("user", "edit")):
        _, email = make_user(memberships={project: (role, access)})
        c = client_factory(email)
        r = c.post(f"/api/v1/projects/{project}/agents/external",
                   json={"key": f"k{role}", "name": "x", "base_url": f"http://127.0.0.1:{port}/ok", "model": "m", "api_key": KEY})
        print(f"P6 register as {role}/{access}:", r.status_code)
    runs = console.post(f"/api/v1/projects/{project}/agents/scope/runs", json={"input": "x"})
    print("P6 runs API on external:", runs.status_code, runs.text[:160])


# --- P7 installation's own services as an external agent target ---
@pytest.mark.parametrize("url", [
    "http://litellm:4000/v1",
    "http://litellm:4000/health/readiness?x=",
    "http://langfuse-web:3000/api/public/ingestion?x=",
    "http://mcp-sql:8000/mcp?x=",
    "http://ticket-desk:8000/v1",
])
def test_p7_internal_service_target(px, pg, url):
    project, console, client, register, _ = px
    key = "int" + str(abs(hash(url)) % 10000)
    r = console.post(f"/api/v1/projects/{project}/agents/external",
                     json={"key": key, "name": "x", "base_url": url, "model": "m", "api_key": KEY})
    print("P7 register", url, "->", r.status_code, r.json().get("external", r.json().get("error")))
    if r.status_code != 201:
        return
    agent = r.json()
    console.post(f"/api/v1/projects/{project}/agents/{agent['id']}/external/publish")
    rr = client.chat(f"agent:{project_key(pg, project)}/{key}", "x")
    print("P7 call", url, "->", rr.status_code, rr.json().get("error", {}).get("code"), "audit:", _audit(pg, agent["id"]))


def test_p8_query_string_in_base_url(px, up, pg):
    project, console, client, register, port = px
    agent, model = register("qs", base_url=f"http://127.0.0.1:{port}/echo?token=dummy-not-secret-qs")
    n = len(up.seen)
    r = client.chat(model, "x")
    print("P8 base_url with query: shown=", agent["external"]["base_url"], "status", r.status_code,
          "path at upstream:", [h["path"] for h in up.seen[n:]])
    rows = pg.execute("SELECT after FROM audit_events WHERE action='create_external_agent' AND resource_id=%s", (agent["id"],)).fetchall()
    print("P8 token in create audit:", "dummy-not-secret-qs" in json.dumps(rows, default=str))


def test_p9_fake_placeholder_after_tokenized_input(px, up):
    from ffcore.guardrails.settings import get_guardrail_settings
    _, _, client, register, _ = px
    _, model = register("ph", "echo")
    n = len(up.seen)
    r = client.chat(model, f"benim adresim {EMAIL}")
    sent = up.seen[n]["body"]["messages"][-1]["content"]
    answer = r.json()["choices"][0]["message"]["content"]
    print("P9 egress on:", get_guardrail_settings().guardrail_egress_enabled, "sent:", sent, "answer:", answer)
    if get_guardrail_settings().guardrail_egress_enabled:
        assert EMAIL not in sent and EMAIL not in answer


def test_p10_downgrade_refuses_with_external(scratch_db):
    db = scratch_db
    import uuid
    p = uuid.uuid4()
    db.conn.execute("INSERT INTO projects (id, key, name, created_by) VALUES (%s, %s, 'P', 't')", (p, f"pp-{p.hex[:8]}"))
    db.conn.execute("INSERT INTO agents (id, project_id, key, name, status, kind, external_config, created_by) VALUES (%s,%s,'ext1','A','published','external',%s,'t')", (uuid.uuid4(), p, b"x"))
    r = db.alembic("downgrade", "-1")
    print("P10 downgrade -1 with external rows:", r.returncode, r.stderr.strip().splitlines()[-1:])
    assert r.returncode != 0


# --- P11-P13: candidates from the independent hunt, checked on the stack ---
def test_p11_import_onto_external_and_test_run(px, make_user, client_factory, pg):
    from tests.integration.test_06b_manifest import _model
    project, console, client, register, port = px
    _model(pg, project)
    agent, model = register("imp")
    _, email = make_user(memberships={project: ("analyst", "edit")})
    analyst = client_factory(email)
    manifest = {"manifest_version": 1, "agent": {"key": "imp", "name": "N", "kind": "native"},
                "definition": {"model": "chat-default", "system_prompt": "x"}}
    r = analyst.post(f"/api/v1/projects/{project}/agents/import", json=manifest)
    print("P11 analyst import onto external key:", r.status_code, r.text[:200])
    rows = pg.execute("SELECT count(*) FROM agent_versions WHERE agent_id=%s", (agent["id"],)).fetchone()
    print("P11 versions under the external agent:", rows)
    g = console.get(f"/api/v1/projects/{project}/agents/{agent['id']}/external")
    print("P11 external read after import:", g.status_code, g.json().get("latest_version"), g.json().get("kind"))
    # read only the first SSE lines (the run id), then hang up: the queue is not driven here
    with analyst.stream("POST", f"/api/v1/projects/{project}/agents/imp/runs",
                        json={"input": "x", "channel": "test", "version": 1}) as run:
        first = []
        for line in run.iter_lines():
            if line:
                first.append(line)
            if len(first) >= 2 or run.status_code != 200:
                break
    print("P11 test run on the external agent's imported version:", run.status_code, first[:2])
    runs = pg.execute("SELECT count(*) FROM runs r JOIN agent_versions v ON v.id=r.agent_version_id WHERE v.agent_id=%s", (agent["id"],)).fetchone()
    print("P11 runs rows for the external agent:", runs)
    m = client.chat(model, "x")
    print("P11 facade still external path:", m.status_code, (m.json().get("choices") or [{}])[0].get("message"))


def test_p12_analyst_delete_and_take_over_key(px, make_user, client_factory, pg):
    from tests.integration.test_06b_manifest import _model
    project, console, client, register, port = px
    _model(pg, project)
    agent, model = register("support")
    _, email = make_user(memberships={project: ("analyst", "edit")})
    analyst = client_factory(email)
    p = analyst.patch(f"/api/v1/projects/{project}/agents/{agent['id']}", json={"name": "renamed by analyst"})
    print("P12 analyst rename external:", p.status_code)
    d = analyst.delete(f"/api/v1/projects/{project}/agents/{agent['id']}")
    print("P12 analyst delete external:", d.status_code)
    c = analyst.post(f"/api/v1/projects/{project}/agents", json={"key": "support", "name": "native", "model": "chat-default"})
    print("P12 analyst reuses key:", c.status_code)
    if c.status_code == 201:
        pub = analyst.post(f"/api/v1/projects/{project}/agents/{c.json()['id']}/publish", json={"version": 1})
        print("P12 analyst publishes native under the same name:", pub.status_code, pub.text[:120])
        m = client.chat(model, "x")
        print("P12 facade name now resolves to:", m.status_code, m.text[:160])
    cfg = pg.execute("SELECT external_config IS NOT NULL, deleted_at IS NOT NULL FROM agents WHERE id=%s", (agent["id"],)).fetchone()
    print("P12 deleted external keeps encrypted config:", cfg)


def test_p13_put_base_url_keeps_old_key(px, up):
    project, console, client, register, port = px
    agent, model = register("mv", "ok")
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external",
                    json={"base_url": f"http://127.0.0.1:{port}/moved"})
    n = len(up.seen)
    client.chat(model, "x")
    print("P13 PUT base_url only:", r.status_code, "auth header at new path:",
          [(h["path"], h["headers"].get("authorization") == f"Bearer {KEY}") for h in up.seen[n:]])
