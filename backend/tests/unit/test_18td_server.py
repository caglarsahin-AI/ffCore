"""18-ticket-desk slice 1: the fake ticket system (services/ticket-desk) on 127.0.0.1, called
through FFCore's own MCP client with auth `none`, as a registered external tool would be.

The service is test-only (compose `test` profile). Its tickets come from the 13a/18 samples;
`send_reply` only records, and the inspection endpoints show what was called and sent.
"""

import ast
import asyncio
import importlib.util
import json
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from ffcore.services import mcp_client
from ffcore.services.mcp_client import Caller, ToolTarget

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "services" / "ticket-desk" / "ticket_desk_server.py"
SAMPLES = ROOT / "data" / "samples"
TICKET_FILES = [
    SAMPLES / "tickets" / "tickets-20.jsonl",
    SAMPLES / "poison" / "tickets-poison.jsonl",
]
CALLER = Caller(user_id="td-test-user", project_id="00000000-0000-0000-0000-000000000000")
# What the module may import: the MCP SDK, its web stack and the standard library. Anything
# that can open an outbound connection (httpx, urllib.request, requests, socket) is not here.
ALLOWED_IMPORTS = {
    "json",
    "os",
    "threading",
    "time",
    "uuid",
    "pathlib",
    "typing",
    "uvicorn",
    "pydantic",
    "mcp.server.mcpserver",
    "mcp.server.mcpserver.exceptions",
    "mcp.server.transport_security",
    "starlette.responses",
}


def _module():
    spec = importlib.util.spec_from_file_location("ticket_desk_server", SERVER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tickets() -> dict[str, dict]:
    out = {}
    for path in TICKET_FILES:
        for line in path.read_text(encoding="utf-8").splitlines():
            ticket = json.loads(line)
            out[ticket["id"]] = ticket
    return out


@pytest.fixture(scope="module")
def desk():
    module = _module()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    app = module.build_app(module.load_tickets(TICKET_FILES), allowed_hosts=["127.0.0.1:*"])
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    deadline = time.monotonic() + 10
    while not server.started:
        assert time.monotonic() < deadline, "ticket-desk did not start"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True


@pytest.fixture
def base(desk):
    _post(desk, "/_reset")
    return desk


@pytest.fixture
def cfg(settings):
    settings.allowed_internal_hosts = ["127.0.0.0/8"]
    settings.mcp_call_timeout_s = 5
    settings.tool_result_max_chars = 100_000
    return settings


def _get(base: str, path: str):
    with urllib.request.urlopen(base + path, timeout=5) as response:
        return json.loads(response.read())


def _post(base: str, path: str):
    request = urllib.request.Request(base + path, method="POST", data=b"")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def _target(base: str) -> ToolTarget:
    return ToolTarget(key="ticket-desk", endpoint_url=base + "/mcp", auth_type="none", auth={})


def _call(base, cfg, action, arguments):
    return asyncio.run(mcp_client.call(_target(base), action, arguments, cfg, caller=CALLER))


def test_18td_1_discovery_lists_three_actions(base, cfg):
    found = asyncio.run(mcp_client.discover(_target(base), cfg, caller=CALLER))
    actions = {a.name: a for a in found}
    assert set(actions) == {"list_tickets", "get_ticket", "send_reply"}
    assert set(actions["send_reply"].input_schema["required"]) == {"ticket_id", "body"}
    assert actions["get_ticket"].input_schema["required"] == ["ticket_id"]


def test_18td_2_list_tickets_has_every_sample_without_body_or_pii(base, cfg):
    result = _call(base, cfg, "list_tickets", {"limit": 100})
    assert not result.is_error, result.text
    listed = json.loads(result.text)
    assert [t["id"] for t in listed] == sorted(_tickets())
    for ticket in listed:
        assert set(ticket) == {"id", "subject", "received_at"}


def test_18td_2b_list_tickets_limit(base, cfg):
    listed = json.loads(_call(base, cfg, "list_tickets", {"limit": 3}).text)
    assert [t["id"] for t in listed] == sorted(_tickets())[:3]


def test_18td_3_get_ticket_returns_body_without_test_labels(base, cfg):
    expected = _tickets()["tkt-002"]
    result = _call(base, cfg, "get_ticket", {"ticket_id": "tkt-002"})
    assert not result.is_error, result.text
    ticket = json.loads(result.text)
    # `pii` is the generator's answer key for the tests, never the system's data
    assert ticket == {k: v for k, v in expected.items() if k != "pii"}


def test_18td_3b_poison_ticket_is_served_like_any_other(base, cfg):
    ticket = json.loads(_call(base, cfg, "get_ticket", {"ticket_id": "tkt-p01"}).text)
    assert ticket["body"] == _tickets()["tkt-p01"]["body"]


def test_18td_4_unknown_ticket_is_a_coded_error(base, cfg):
    result = _call(base, cfg, "get_ticket", {"ticket_id": "tkt-999"})
    assert result.is_error
    assert "ticket_not_found" in result.text
    reply = _call(base, cfg, "send_reply", {"ticket_id": "tkt-999", "body": "x"})
    assert reply.is_error and "ticket_not_found" in reply.text
    assert _get(base, "/_sent") == []


def test_18td_5_send_reply_is_recorded_only(base, cfg):
    assert _get(base, "/_sent") == []
    result = _call(base, cfg, "send_reply", {"ticket_id": "tkt-001", "body": "Hesap açıldı."})
    assert not result.is_error, result.text
    sent = _get(base, "/_sent")
    assert len(sent) == 1
    assert sent[0]["ticket_id"] == "tkt-001" and sent[0]["body"] == "Hesap açıldı."
    assert sent[0]["reply_id"] in result.text


def test_18td_5b_calls_record_every_tool_call_and_reset_clears(base, cfg):
    _call(base, cfg, "list_tickets", {})
    _call(base, cfg, "get_ticket", {"ticket_id": "tkt-003"})
    calls = _get(base, "/_calls")
    assert [(c["tool"], c["arguments"]) for c in calls] == [
        ("list_tickets", {"limit": 20}),
        ("get_ticket", {"ticket_id": "tkt-003"}),
    ]
    _post(base, "/_reset")
    assert _get(base, "/_calls") == [] and _get(base, "/_sent") == []


def test_18td_6_no_identity_reaches_the_external_system(base, cfg):
    """auth `none` (K-SEN-0012): neither a credential nor the user's on-behalf-of token goes to
    the ticket system; the desk records the header names it received."""
    _call(base, cfg, "list_tickets", {})
    names = {name for call in _get(base, "/_calls") for name in call["header_names"]}
    assert names, "the desk recorded no headers"
    assert not names & {"authorization", "x-on-behalf-of", "cookie"}, names


def test_18td_7_no_outbound_client_in_the_module():
    """send_reply makes no outbound request: the module imports nothing that could open one."""
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert imported <= ALLOWED_IMPORTS, imported - ALLOWED_IMPORTS


def test_18td_8_healthz(base):
    assert _get(base, "/healthz") == {"status": "ok"}
