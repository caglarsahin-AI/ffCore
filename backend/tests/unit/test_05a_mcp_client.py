"""05a slice 3: the MCP client against a real MCP server on 127.0.0.1 (official SDK).

U5 regression (forward_user never shares a session), call-time egress (C5), truncation
marker (C13), structured call log, timeouts, upstream identities.
"""

import asyncio
import base64
import logging

import jwt
import pytest
from pydantic import SecretStr

from ffcore.core.auth import verify_on_behalf_of
from ffcore.services import mcp_client
from ffcore.services.mcp_client import Caller, ToolCallError, ToolTarget
from tests import mcp_fixture

SERVICE = "dummy-not-secret-service-token-05a-0123456789"
OBO = "dummy-not-secret-obo-secret-05a-0123456789abcd"
PASSWORD = "dummy-not-secret-basic-password-05a"


@pytest.fixture(scope="module")
def server():
    fixture, uv = mcp_fixture.start()
    yield fixture
    uv.should_exit = True


@pytest.fixture
def mcp(server):
    server.seen.clear()
    return server


@pytest.fixture
def cfg(settings):
    settings.allowed_internal_hosts = ["127.0.0.0/8"]
    settings.service_token = SecretStr(SERVICE)
    settings.obo_jwt_secret = SecretStr(OBO)
    settings.tool_result_max_chars = 100
    settings.mcp_call_timeout_s = 5
    return settings


def target(mcp, auth_type="none", **auth):
    return ToolTarget(key="test-tool", endpoint_url=mcp.url, auth_type=auth_type, auth=auth)


ALICE = Caller(user_id="user-alice", project_id="project-1")


def run(coro):
    return asyncio.run(coro)


def test_05a_discover_lists_actions(mcp, cfg):
    actions = run(mcp_client.discover(target(mcp), cfg, caller=ALICE))
    names = {a.name for a in actions}
    assert {"echo", "whoami", "big", "slow", "fail"} <= names
    echo = next(a for a in actions if a.name == "echo")
    assert echo.input_schema["properties"]["text"]["type"] == "string"
    assert echo.description == "Returns the text."


def test_05a_call_returns_text(mcp, cfg):
    result = run(mcp_client.call(target(mcp), "echo", {"text": "hello"}, cfg, caller=ALICE))
    assert result.text == "hello" and not result.truncated and not result.is_error


def test_05a_9_result_truncation_marked(mcp, cfg, caplog):
    with caplog.at_level(logging.INFO, logger="ffcore.tools"):
        result = run(mcp_client.call(target(mcp), "big", {"size": 250}, cfg, caller=ALICE))
    assert result.truncated and result.total_chars == 250
    assert result.text == "x" * 100 + "\n[truncated: 100/250 chars]"
    record = next(r for r in caplog.records if r.getMessage().startswith("tool_call"))
    assert record.truncated is True


def test_05a_5_call_log_fields(mcp, cfg, caplog):
    with caplog.at_level(logging.INFO, logger="ffcore.tools"):
        run(mcp_client.call(target(mcp), "echo", {"text": "hi"}, cfg, caller=ALICE))
    record = next(r for r in caplog.records if r.getMessage().startswith("tool_call"))
    assert (record.tool, record.action, record.status, record.truncated) == (
        "test-tool",
        "echo",
        "ok",
        False,
    )
    assert isinstance(record.latency_ms, int) and record.latency_ms >= 0


def test_05a_tool_error_is_reported(mcp, cfg):
    result = run(mcp_client.call(target(mcp), "fail", {}, cfg, caller=ALICE))
    assert result.is_error


def test_05a_call_timeout_is_coded(mcp, cfg):
    with pytest.raises(ToolCallError) as err:
        run(mcp_client.call(target(mcp), "slow", {"seconds": 3}, cfg, caller=ALICE, timeout_s=1))
    assert err.value.code == "tool_timeout"


def test_05a_8_call_time_egress_refuses_loopback(mcp, cfg):
    # Registered while 127.0.0.0/8 was allowed; the call checks again at connect time (C5).
    cfg.allowed_internal_hosts = []
    with pytest.raises(ToolCallError) as err:
        run(mcp_client.call(target(mcp), "echo", {"text": "x"}, cfg, caller=ALICE))
    assert err.value.code.startswith("egress_")
    assert mcp.calls() == []


def test_05a_basic_header_sent_never_logged(mcp, cfg, caplog):
    with caplog.at_level(logging.DEBUG):
        run(
            mcp_client.call(
                target(mcp, "basic", username="tool-user", password=PASSWORD),
                "echo",
                {"text": "x"},
                cfg,
                caller=ALICE,
            )
        )
    sent = mcp.calls()[0].headers["authorization"]
    assert sent == "Basic " + base64.b64encode(f"tool-user:{PASSWORD}".encode()).decode()
    assert PASSWORD not in caplog.text


def test_05a_bearer_and_header_types(mcp, cfg):
    run(
        mcp_client.call(
            target(mcp, "bearer", token="tok-123456"), "echo", {"text": "a"}, cfg, caller=ALICE
        )
    )
    run(
        mcp_client.call(
            target(mcp, "header", name="X-Api-Key", value="key-123456"),
            "echo",
            {"text": "b"},
            cfg,
            caller=ALICE,
        )
    )
    first, second = mcp.calls()
    assert first.headers["authorization"] == "Bearer tok-123456"
    assert second.headers["x-api-key"] == "key-123456"


def test_05a_forward_user_token_per_call_with_aud_list(mcp, cfg):
    tool = target(mcp, "forward_user")
    run(mcp_client.call(tool, "echo", {"text": "a"}, cfg, caller=ALICE))
    run(mcp_client.call(tool, "echo", {"text": "b"}, cfg, caller=ALICE))
    tokens = [c.headers["x-on-behalf-of"] for c in mcp.calls()]
    claims = [jwt.decode(t, options={"verify_signature": False}) for t in tokens]
    assert claims[0]["jti"] != claims[1]["jti"]  # a new token for every call (C3)
    assert claims[0]["aud"] == ["test-tool", cfg.obo_audience]
    assert claims[0]["sub"] == "user-alice" and claims[0]["project_id"] == "project-1"
    assert claims[0]["exp"] - claims[0]["iat"] <= 60
    assert mcp.calls()[0].headers["authorization"] == f"Bearer {SERVICE}"
    # The backend accepts it, and so does the tool it was cut for; another tool does not.
    verify_on_behalf_of(tokens[0], audience=cfg.obo_audience, settings=cfg)
    verify_on_behalf_of(tokens[0], audience="test-tool", settings=cfg)
    with pytest.raises(Exception) as err:
        verify_on_behalf_of(tokens[0], audience="other-tool", settings=cfg)
    assert err.value.code == "audience_mismatch"


def test_05a_u5_forward_user_session_per_call(mcp, cfg):
    """M2 of the U5 measurement: two users at once must each go with their own identity."""
    tool = target(mcp, "forward_user")

    async def both():
        await asyncio.gather(
            *(
                mcp_client.call(
                    tool, "whoami", {"caller": user}, cfg, caller=Caller(user, "project-1")
                )
                for user in ("user-carol", "user-dave", "user-erin", "user-frank")
            )
        )

    run(both())
    calls = mcp.calls()
    assert len(calls) == 4
    for call in calls:
        claims = jwt.decode(call.headers["x-on-behalf-of"], options={"verify_signature": False})
        assert claims["sub"] == call.arguments["caller"]


def test_05a_run_id_header(mcp, cfg):
    run(mcp_client.call(target(mcp), "echo", {"text": "x"}, cfg, caller=ALICE, run_id="run-7"))
    assert mcp.calls()[0].headers["x-run-id"] == "run-7"


def test_05a_guard_hooks_called(mcp, cfg):
    seen = []

    class Guard:
        async def pre(self, action, arguments):
            seen.append(("pre", action, arguments))
            return {"text": "guarded"}

        async def post(self, action, text):
            seen.append(("post", action, text))
            return text.upper()

    result = run(
        mcp_client.call(target(mcp), "echo", {"text": "raw"}, cfg, caller=ALICE, guard=Guard())
    )
    assert result.text == "GUARDED"
    assert seen == [("pre", "echo", {"text": "raw"}), ("post", "echo", "guarded")]
