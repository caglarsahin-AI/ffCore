"""Reviewer probes for 06b-2 r2 (delta of r1 fixes). Copied into backend/tests/integration/ of the
review worktree, removed afterwards. Own fake upstream (127.0.0.1), no outside system.
No `import ffcore.api` first: MINOR-6 says the cycle is gone."""
import asyncio
import json
import logging
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from ffcore.services.external_config import ExternalConfig, check_base_url
from ffcore.services.facade_external import (
    MAX_EXTERNAL_RESPONSE_BYTES,
    ExternalCallFailed,
    call_upstream,
)
from ffcore.core.errors import ApiError
from tests.integration.facade_support import *  # noqa: F403 - fixtures
from tests.integration.facade_support import make_key, project_key
from tests.integration.test_06b2_external_agent import ext_settings  # noqa: F401 - fixture

KEY = "dummy-not-secret-probe-key-0001"
KEY2 = "dummy-not-secret-probe-key-0002"
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
        if mode == "deepmsg":  # deep inside a valid-looking message
            n = 20000
            return self._send(200, b'{"choices":[{"message":{"role":"assistant","content":"ok","x":' + b"[" * n + b"]" * n + b"}}]}")
        if mode == "nocontent":
            return self._send(200, json.dumps({"choices": [{"message": {"role": "assistant"}}]}).encode())
        if mode == "choicestr":
            return self._send(200, json.dumps({"choices": ["x"]}).encode())
        if mode == "toolsonly":
            msg = {"role": "assistant", "content": None, "tool_calls": [{"id": "c", "type": "function", "function": {"name": "rm", "arguments": "{}"}}]}
        if mode == "parts":
            msg = {"role": "assistant", "content": [{"type": "text", "text": "parca"}]}
        if mode == "err500":
            return self._send(500, json.dumps({"error": f"upstream says {EMAIL}"}).encode())
        if mode == "nonjson":
            return self._send(200, f"<html>{EMAIL}</html>".encode())
        if mode == "weirdkey":
            msg[EMAIL] = "x"
            msg["line\nbreak"] = "y"
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


def _audit(pg, agent_id, action="external_agent_call"):
    return pg.execute(
        "SELECT outcome, after FROM audit_events WHERE action=%s AND resource_id=%s ORDER BY ts",
        (action, agent_id),
    ).fetchall()


def _code(r):
    return r.json().get("error", {}).get("code") if r.status_code >= 400 else "-"


# --- MINOR-6: each module importable on its own, in a fresh interpreter ---
@pytest.mark.parametrize("mod", ["ffcore.services.facade_external", "ffcore.services.external_config", "ffcore.api.agents"])
def test_r2_m6_import_alone(mod):
    r = subprocess.run([sys.executable, "-c", f"import {mod}"], capture_output=True, text=True)
    print("M6 import", mod, r.returncode, r.stderr.strip().splitlines()[-1:] if r.returncode else "")
    assert r.returncode == 0


# --- r1 P1 URL matrix (regression) + MINOR-1 reserved + MINOR-2 query ---
URLS = [
    "http://127.0.0.2:80/v1", "http://[::1]/v1", "http://169.254.169.254/latest", "http://0.0.0.0/v1",
    "http://2130706433/v1", "http://0x7f000001/v1", "http://127.1/v1", "http://localhost/v1",
    "http://10.0.0.5./v1", "HTTP://10.0.0.5/v1", "http://[::ffff:10.0.0.5]/v1", "http://[::ffff:127.0.0.2]/v1",
    "http://[fe80::1]/v1", "http://100.64.0.1/v1", "http://192.168.1.1/v1", "http://172.17.0.1/v1",
    "ftp://example.com/v1", "http://user:pw@example.com/v1", "http://:pw@example.com/v1",
    "http://example.com:0/v1", "http://example.com:70000/v1", "http://example.com:-1/v1", "http:///v1", "http://",
    "javascript:alert(1)", "//example.com/v1", "http://example.com/v1",
    "http://metadata.google.internal/v1", "http://postgres:5432/x", "http://redis:6379/x", "http://qdrant:6333/x",
]


def test_r2_p1_register_url_matrix(px):
    project, console, *_ = px
    out = []
    for i, url in enumerate(URLS):
        r = console.post(f"/api/v1/projects/{project}/agents/external",
                         json={"key": f"u{i}", "name": "x", "base_url": url, "model": "m", "api_key": KEY})
        out.append((url, r.status_code, _code(r)))
    for row in out:
        print("P1", row)
    assert not [u for u, s, _ in out if s < 400]


RESERVED = [
    "http://litellm:4000/v1", "http://LITELLM:4000/v1", "http://litellm.:4000/v1", "http://litellm/v1",
    "https://litellm:4000/v1",
    "http://langfuse-web:3000/api", "http://mcp-sql:8000/mcp", "http://mcp-search:8000/mcp",
    "http://ticket-desk:8000/v1", "http://ollama:11434/v1", "http://host.docker.internal:11434/v1",
    "http://HOST.DOCKER.INTERNAL:11434/v1", "http://backend:8000/api", "http://qdrant:6333/x",
    "http://127.0.0.1:8000/api/v1", "http://localhost:8000/api", "http://127.0.0.2:8000/api", "http://[::1]:8000/api",
    "http://[::ffff:127.0.0.1]:8000/api", "http://127.0.0.1:08000/api",
]


def test_r2_m1_reserved_hosts(px):
    project, console, *_ = px
    out = []
    for i, url in enumerate(RESERVED):
        r = console.post(f"/api/v1/projects/{project}/agents/external",
                         json={"key": f"rs{i}", "name": "x", "base_url": url, "model": "m", "api_key": KEY})
        out.append((url, r.status_code, _code(r)))
    for row in out:
        print("M1", row)
    assert not [u for u, s, _ in out if s < 400]


def test_r2_m1_reserved_on_update_and_other_internal_ok(px, up):
    project, console, client, register, port = px
    agent, model = register("rsu")
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"base_url": "http://litellm:4000/v1"})
    print("M1 update to litellm:", r.status_code, _code(r))
    assert r.status_code == 422 and _code(r) == "external_agent_host_reserved"
    # another internal host (127.0.0.1 on a non-backend port) stays a valid target
    r = client.chat(model, "x")
    print("M1 127.0.0.1:<fake port> still callable:", r.status_code)
    assert r.status_code == 200


QS = ["/ok?token=dummy-not-secret-qs", "/ok?", "/ok#frag", "/ok#", "/ok?a=1#b", "/ok%3Fx=1"]


def test_r2_m2_query_fragment(px, up):
    project, console, client, register, port = px
    out = []
    for i, tail in enumerate(QS):
        r = console.post(f"/api/v1/projects/{project}/agents/external",
                         json={"key": f"q{i}", "name": "x", "base_url": f"http://127.0.0.1:{port}{tail}", "model": "m", "api_key": KEY})
        out.append((tail, r.status_code, _code(r), "dummy-not-secret-qs" in r.text))
    for row in out:
        print("M2", row)
    assert all(s == 422 for t, s, *_ in out if "%3F" not in t)
    agent, _ = register("qput")
    r = console.put(f"/api/v1/projects/{project}/agents/{agent['id']}/external", json={"base_url": f"http://127.0.0.1:{port}/ok?x=1"})
    print("M2 PUT with query:", r.status_code, _code(r))
    assert r.status_code == 422


# --- MAJOR-1: deep JSON / invalid / no content -> 502, audit, stream error + [DONE] ---
@pytest.mark.parametrize("mode,code", [
    ("chunked", "external_agent_response_too_large"),
    ("deep", "external_agent_failed"),
    ("deepdict", "external_agent_failed"),
    ("deepmsg", "external_agent_failed"),
    ("nocontent", "external_agent_failed"),
    ("choicestr", "external_agent_failed"),
    ("toolsonly", "external_agent_failed"),
    ("parts", "external_agent_failed"),
    ("err500", "external_agent_failed"),
    ("nonjson", "external_agent_failed"),
])
def test_r2_major1_untrusted_answers(px, pg, mode, code):
    _, _, client, register, _ = px
    agent, model = register(f"a-{mode}", mode)
    try:
        r = client.chat(model, "x")
        got = (r.status_code, _code(r))
        leaked = EMAIL in r.text
    except Exception as exc:
        got, leaked = ("EXC", type(exc).__name__), False
    rows = _audit(pg, agent["id"])
    print(f"MAJ1 {mode}: got={got} leaked={leaked} audit={rows}")
    assert got == (502, code)
    assert not leaked
    assert len(rows) == 1 and rows[0][0] == "error"


@pytest.mark.parametrize("mode", ["deep", "deepdict", "deepmsg", "nonjson"])
def test_r2_major1_stream(px, pg, mode):
    _, _, client, register, _ = px
    agent, model = register(f"s-{mode}", mode)
    status, chunks, lines = client.stream(model, "x")
    rows = _audit(pg, agent["id"])
    print(f"MAJ1 stream {mode}:", status, lines[-2:], "audit:", rows)
    assert lines and lines[-1].strip() == "data: [DONE]"
    assert any("external_agent_failed" in line for line in lines)
    assert len(rows) == 1 and rows[0][0] == "error"


# --- MAJOR-2: import onto external key (and dry run) 422; runs on external 422 ---
def test_r2_major2_import_and_runs(px, ext_settings, make_user, client_factory, pg):
    from tests.integration.test_06b2_external_agent import _model
    project, console, client, register, port = px
    _model(pg, project, ext_settings)
    agent, model = register("imp")
    _, email = make_user(memberships={project: ("analyst", "edit")})
    analyst = client_factory(email)
    manifest = {"manifest_version": 1, "agent": {"key": "imp", "name": "N", "kind": "native"},
                "definition": {"model": "chat-default", "system_prompt": "x"}}
    out = {}
    for who, c in (("analyst", analyst), ("admin", console)):
        for dry in (False, True):
            url = f"/api/v1/projects/{project}/agents/import" + ("?dry_run=true" if dry else "")
            r = c.post(url, json=manifest)
            out[(who, dry)] = (r.status_code, _code(r))
    print("MAJ2 import onto external key:", out)
    assert all(v == (422, "external_agent_not_available") for v in out.values())
    # a bad definition must not change which error wins (target check comes first)
    bad = {**manifest, "definition": {"model": "no-such-model", "system_prompt": "x"}}
    r = analyst.post(f"/api/v1/projects/{project}/agents/import", json=bad)
    print("MAJ2 import onto external with unknown model:", r.status_code, _code(r))
    versions = pg.execute("SELECT count(*) FROM agent_versions WHERE agent_id=%s", (agent["id"],)).fetchone()[0]
    print("MAJ2 versions under external:", versions)
    assert versions == 0
    # a version row planted under the external key (as r1 could) is still not runnable
    pg.execute(
        "INSERT INTO agent_versions (id, agent_id, version, definition, created_by) "
        "SELECT gen_random_uuid(), %s, 1, definition, 'probe' FROM agent_versions LIMIT 1",
        (agent["id"],),
    )
    res = {}
    for body in ({"input": "x"}, {"input": "x", "channel": "test", "version": 1}, {"input": "x", "channel": "test"}):
        r = analyst.post(f"/api/v1/projects/{project}/agents/imp/runs", json=body)
        res[json.dumps(body)] = (r.status_code, _code(r))
    print("MAJ2 runs on external:", res)
    runs = pg.execute("SELECT count(*) FROM runs r JOIN agent_versions v ON v.id=r.agent_version_id WHERE v.agent_id=%s", (agent["id"],)).fetchone()[0]
    print("MAJ2 runs rows for external:", runs)
    assert runs == 0
    assert all(v == (422, "external_agent_not_runnable") for v in res.values())
    # native import still works on a fresh key
    r = analyst.post(f"/api/v1/projects/{project}/agents/import", json={**manifest, "agent": {**manifest["agent"], "key": "impnative"}})
    print("MAJ2 native import fresh key:", r.status_code)
    assert r.status_code in (200, 201)


# --- MINOR-3: lifecycle admin-only ---
def test_r2_m3_admin_only(px, ext_settings, make_user, client_factory, pg):
    from tests.integration.test_06b2_external_agent import _model
    project, console, client, register, port = px
    _model(pg, project, ext_settings)
    agent, model = register("support")
    res = {}
    for role, access in (("analyst", "edit"), ("admin", "read"), ("user", "edit")):
        _, email = make_user(memberships={project: (role, access)})
        c = client_factory(email)
        aid = agent["id"]
        res[(role, access)] = {
            "patch": c.patch(f"/api/v1/projects/{project}/agents/{aid}", json={"name": "renamed"}).status_code,
            "put": c.put(f"/api/v1/projects/{project}/agents/{aid}/external", json={"model": "m2"}).status_code,
            "publish": c.post(f"/api/v1/projects/{project}/agents/{aid}/external/publish").status_code,
            "delete": c.delete(f"/api/v1/projects/{project}/agents/{aid}").status_code,
            "get": c.get(f"/api/v1/projects/{project}/agents/{aid}/external").status_code,
        }
    print("M3 non-admin lifecycle:", res)
    for k, v in res.items():
        assert v["patch"] == v["put"] == v["publish"] == v["delete"] == 403, (k, v)
    alive = pg.execute("SELECT deleted_at IS NULL, name FROM agents WHERE id=%s", (agent["id"],)).fetchone()
    print("M3 agent after attempts:", alive)
    assert alive == (True, "P")
    # admin/edit can still rename and delete
    assert console.patch(f"/api/v1/projects/{project}/agents/{agent['id']}", json={"name": "R"}).status_code == 200
    # native agent: analyst rename still allowed (no regression)
    _, email = make_user(memberships={project: ("analyst", "edit")})
    analyst = client_factory(email)
    c = analyst.post(f"/api/v1/projects/{project}/agents", json={"key": "nat1", "name": "native", "model": "chat-default"})
    print("M3 analyst creates native:", c.status_code)
    if c.status_code == 201:
        p = analyst.patch(f"/api/v1/projects/{project}/agents/{c.json()['id']}", json={"name": "native2"})
        print("M3 analyst renames native:", p.status_code)
        assert p.status_code == 200
    d = console.delete(f"/api/v1/projects/{project}/agents/{agent['id']}")
    print("M3 admin delete external:", d.status_code)
    assert d.status_code in (200, 204)


# --- MINOR-4: origin change drops the key ---
def test_r2_m4_origin_change(px, up, pg):
    project, console, client, register, port = px
    agent, model = register("mv", "ok")
    base = f"/api/v1/projects/{project}/agents/{agent['id']}/external"
    # same origin, other path: key kept
    r = console.put(base, json={"base_url": f"http://127.0.0.1:{port}/ok2"})
    print("M4 same origin path change:", r.status_code, r.json().get("external"))
    assert r.json()["external"]["api_key"] == "***"
    n = len(up.seen)
    assert client.chat(model, "x").status_code == 200
    assert up.seen[n]["headers"].get("authorization") == f"Bearer {KEY}"
    # scheme+host spelled differently, same origin (case, trailing dot, explicit :port) -> kept
    r = console.put(base, json={"base_url": f"HTTP://127.0.0.1:{port}/ok"})
    print("M4 case-only change:", r.status_code, r.json().get("external", r.json().get("error")))
    # other origin (localhost name for the same address would be another host; use a second fake port)
    other = ThreadingHTTPServer(("127.0.0.1", 0), _Up)
    other.seen = []
    threading.Thread(target=other.serve_forever, daemon=True).start()
    try:
        oport = other.server_address[1]
        r = console.put(base, json={"base_url": f"http://127.0.0.1:{oport}/ok"})
        print("M4 other origin no key:", r.status_code, r.json().get("external"))
        assert r.json()["external"]["api_key"] is None
        rows = _audit(pg, agent["id"], "reset_external_agent_key")
        print("M4 reset audit:", rows)
        assert len(rows) == 1 and KEY not in json.dumps(rows, default=str)
        g = console.get(base)
        print("M4 GET after reset:", g.json().get("external"))
        c = client.chat(model, "x")
        print("M4 call after reset:", c.status_code, _code(c), "requests at new origin:", len(other.seen))
        assert c.status_code == 501 and not other.seen
        s = client.stream(model, "x")
        print("M4 stream after reset:", s[0], s[2][-2:] if s[2] else s)
        p = console.post(f"{base}/publish")
        print("M4 publish after reset:", p.status_code, _code(p))
        assert p.status_code == 409
        # moving back does not resurrect the old key
        r = console.put(base, json={"base_url": f"http://127.0.0.1:{port}/ok"})
        print("M4 move back:", r.json()["external"])
        assert r.json()["external"]["api_key"] is None
        # other origin with a new key in the same PUT: new key kept and sent there
        r = console.put(base, json={"base_url": f"http://127.0.0.1:{oport}/ok", "api_key": KEY2})
        print("M4 other origin + new key:", r.status_code, r.json()["external"], "reset rows:", len(_audit(pg, agent["id"], "reset_external_agent_key")))
        assert r.json()["external"]["api_key"] == "***"
        c = client.chat(model, "x")
        print("M4 call with new key:", c.status_code, other.seen[-1]["headers"].get("authorization") == f"Bearer {KEY2}" if other.seen else None)
        assert c.status_code == 200 and other.seen[-1]["headers"]["authorization"] == f"Bearer {KEY2}"
        # explicit null key
        r = console.put(base, json={"api_key": None})
        print("M4 api_key null:", r.status_code, _code(r))
    finally:
        other.shutdown()


# --- MINOR-5: names of ignored fields not in log ---
def test_r2_m5_log(px, caplog):
    _, _, client, register, _ = px
    _, model = register("weird", "weirdkey")
    with caplog.at_level(logging.INFO, logger="ffcore"):
        r = client.chat(model, "x")
    assert r.status_code == 200
    logged = "\n".join(rec.getMessage() for rec in caplog.records)
    print("M5 log lines:", [m for m in logged.splitlines() if "ignored" in m])
    assert EMAIL not in logged and "line\nbreak" not in logged


# --- r1 regressions: redirect, DNS rebinding ---
def test_r2_redirect_not_followed(px, up, pg):
    _, _, client, register, _ = px
    agent, model = register("redir", "redirect")
    n = len(up.seen)
    r = client.chat(model, "x")
    print("REG redirect:", r.status_code, _code(r), len(up.seen) - n, _audit(pg, agent["id"]))
    assert r.status_code == 502 and len(up.seen) - n == 1


def test_r2_dns_rebinding(app_settings):
    s = app_settings.model_copy(update={"egress_allowlist": ["agent.example.test"], "offline": False})

    async def public(host, port):
        return ["93.184.216.34"]

    async def private(host, port):
        return ["10.0.0.5"]

    async def mixed(host, port):
        return ["93.184.216.34", "127.0.0.1"]

    cfg = ExternalConfig(base_url="https://agent.example.test/v1", model="m", api_key=KEY)

    async def run():
        await check_base_url(cfg.base_url, s, resolver=public)
        with pytest.raises(ApiError):
            await check_base_url(cfg.base_url, s, resolver=mixed)
        with pytest.raises(ExternalCallFailed) as e2:
            await call_upstream(cfg, [{"role": "user", "content": "x"}], {}, s, resolver=private)
        return e2.value

    exc = asyncio.run(run())
    print("REG rebinding at call:", exc.status_code, exc.audit)
    assert exc.status_code == 502 and exc.audit["error_code"] == "egress_private_address"


def test_r2_secret_not_in_api_audit(px, pg):
    project, console, client, register, port = px
    agent, model = register("sec")
    g = console.get(f"/api/v1/projects/{project}/agents/{agent['id']}/external")
    rows = pg.execute("SELECT action, after::text FROM audit_events WHERE resource_id=%s", (agent["id"],)).fetchall()
    client.chat(model, "x")
    print("SEC key in GET:", KEY in g.text, "key in audit:", any(KEY in (a or "") for _, a in rows))
    assert KEY not in g.text and not any(KEY in (a or "") for _, a in rows)
