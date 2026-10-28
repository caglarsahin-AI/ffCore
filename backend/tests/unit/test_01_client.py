"""Package 01: litellm_client against a local stand-in for the LiteLLM proxy.

The stand-in answers like LiteLLM v1.80.0 did when measured (U3): `x-litellm-model-id` names the
deployment that answered; with no fallback a failed upstream is a 500. Requests are recorded so
the body the client sends (fallbacks, user, metadata, stream options) can be checked.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest
from pydantic import SecretStr

from ffcore.services.litellm_client import (
    EmptyCompletion,
    FallbackObserved,
    LiteLLMClient,
    ModelTarget,
    ModelUnavailable,
)

PRIMARY = "11111111-1111-1111-1111-111111111111"
BACKUP = "22222222-2222-2222-2222-222222222222"
USAGE = {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5}


class _Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    # Set per test: (status, answering model id, content)
    behaviour = (200, PRIMARY, "hello")
    seen: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["content-length"])))
        type(self).seen.append(
            {"path": self.path, "body": body, "auth": self.headers["authorization"]}
        )
        status, model_id, content = type(self).behaviour
        if status != 200:
            # 400 is what LiteLLM says for a name it does not serve (measured, v1.80.0).
            message = (
                f"Invalid model name passed in model={body['model']}"
                if status == 400
                else "upstream down"
            )
            data = json.dumps({"error": {"message": message, "code": str(status)}}).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if body.get("stream"):
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.send_header("x-litellm-model-id", model_id)
            self.send_header("transfer-encoding", "chunked")
            self.end_headers()
            chunks = [{"choices": [{"index": 0, "delta": {"content": c}}]} for c in content]
            chunks.append({"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]})
            chunks.append({"choices": [], "usage": USAGE})
            for c in chunks:
                self._chunk(f"data: {json.dumps(c)}\n\n".encode())
            self._chunk(b"data: [DONE]\n\n")
            self.wfile.write(b"0\r\n\r\n")
            return
        data = json.dumps(
            {
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": USAGE,
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("x-litellm-model-id", model_id)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _chunk(self, data):
        self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
        self.wfile.flush()


@pytest.fixture
def proxy(settings):
    _Proxy.seen = []
    _Proxy.behaviour = (200, PRIMARY, "hello")
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Proxy)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.litellm_url = f"http://127.0.0.1:{server.server_address[1]}"
    settings.litellm_master_key = SecretStr("sk-dummy-not-secret-master")
    settings.litellm_internal_key = SecretStr("sk-dummy-not-secret-internal")
    settings.allowed_internal_hosts = ["127.0.0.0/8"]
    yield _Proxy
    server.shutdown()


WITH_FALLBACK = ModelTarget("hastane.chat-default", PRIMARY, "hastane.chat-fallback", BACKUP)
ALONE = ModelTarget("hastane.chat-default", PRIMARY)
MESSAGES = [{"role": "user", "content": "hi"}]
META = {"project_id": "p1", "agent_key": "a", "run_id": "r1", "channel": "web", "api_key_id": None}


def _chat(settings, target, **kw):
    async def go():
        async with LiteLLMClient(settings) as client:
            return await client.chat(target, MESSAGES, user="u1", metadata=META, **kw)

    return anyio.run(go)


def _stream(settings, target):
    async def go():
        async with LiteLLMClient(settings) as client:
            async with client.chat_stream(target, MESSAGES, user="u1", metadata=META) as s:
                pieces = [
                    choice["delta"].get("content", "")
                    async for chunk in s
                    for choice in chunk.get("choices", [])
                ]
            return pieces, s.result

    return anyio.run(go)


def test_01_12_metadata_and_internal_key_sent(settings, proxy):
    _chat(settings, ALONE)
    (request,) = proxy.seen
    assert request["path"] == "/v1/chat/completions"
    assert request["auth"] == "Bearer sk-dummy-not-secret-internal"
    assert request["body"]["user"] == "u1"
    assert request["body"]["metadata"] == META
    assert request["body"]["model"] == "hastane.chat-default"


def test_01_2_fallbacks_only_with_record(settings, proxy):
    _chat(settings, ALONE)
    _chat(settings, WITH_FALLBACK)
    first, second = proxy.seen
    assert "fallbacks" not in first["body"]
    assert second["body"]["fallbacks"] == ["hastane.chat-fallback"]


def test_01_2_fallback_detection_header(settings, proxy):
    assert _chat(settings, WITH_FALLBACK).fallback is None
    proxy.behaviour = (200, BACKUP, "hello")
    result = _chat(settings, WITH_FALLBACK)
    assert result.fallback == FallbackObserved(
        "hastane.chat-default", "hastane.chat-fallback", "primary_failed"
    )
    assert result.content == "hello" and result.usage == USAGE


def test_01_2_fallback_detection_stream(settings, proxy):
    proxy.behaviour = (200, BACKUP, "hey")
    pieces, result = _stream(settings, WITH_FALLBACK)
    assert result.fallback.target_model == "hastane.chat-fallback"
    assert "".join(pieces) == "hey"


def test_01_2_unknown_deployment_is_loud(settings, proxy):
    proxy.behaviour = (200, "33333333-3333-3333-3333-333333333333", "hello")
    with pytest.raises(ModelUnavailable) as err:
        _chat(settings, WITH_FALLBACK)
    assert err.value.code == "model_unavailable"
    assert "unexpected deployment" in err.value.reason


@pytest.mark.parametrize("status", [500, 502, 503])
def test_01_2_upstream_error_is_503(settings, proxy, status):
    proxy.behaviour = (status, PRIMARY, "")
    with pytest.raises(ModelUnavailable) as err:
        _chat(settings, ALONE)
    assert err.value.status_code == 503
    assert "upstream down" not in err.value.message  # provider text is logged, not returned


def test_01_2_unreachable_litellm_is_503(settings, proxy):
    settings.litellm_url = "http://127.0.0.1:1"
    with pytest.raises(ModelUnavailable):
        _chat(settings, ALONE)


def test_01_4_stream_usage_and_options(settings, proxy):
    pieces, result = _stream(settings, ALONE)
    assert "".join(pieces) == "hello"
    assert result.usage == USAGE
    assert proxy.seen[0]["body"]["stream_options"] == {"include_usage": True}


def test_01_10_empty_completion_raises(settings, proxy, caplog):
    proxy.behaviour = (200, PRIMARY, "")
    with pytest.raises(EmptyCompletion):
        _chat(settings, ALONE)
    with pytest.raises(EmptyCompletion):
        _stream(settings, ALONE)
    assert "empty_completion" in caplog.text


def test_01_parallel_tool_calls_off_with_tools(settings, proxy):
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    _chat(settings, ALONE, tools=tools)
    assert proxy.seen[0]["body"]["parallel_tool_calls"] is False


def test_01_7_client_never_calls_config_update(settings, proxy):
    _chat(settings, WITH_FALLBACK)
    _stream(settings, WITH_FALLBACK)
    assert all(not r["path"].startswith("/config") for r in proxy.seen)


def test_01_not_registered_in_litellm_is_503(settings, proxy, caplog):
    # The table has the model but LiteLLM does not (reconcile pending or failed).
    proxy.behaviour = (400, PRIMARY, "")
    with pytest.raises(ModelUnavailable) as err:
        _chat(settings, ALONE)
    assert err.value.reason == "not_registered"
    assert "litellm_model_not_registered" in caplog.text
