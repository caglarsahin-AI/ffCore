"""Package 01 review r1: credentials never in URLs or logs, upstream text never trusted, a stream
is a success only when it completed (MAJOR-1..3).

A programmable stand-in for the LiteLLM proxy answers over real HTTP; the client goes through the
real SafeOutboundClient. SENTINEL marks text that must not reach logs, exceptions or callers.
"""

import asyncio
import hashlib
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest
from pydantic import SecretStr

from ffcore.services.litellm_client import (
    LiteLLMClient,
    LiteLLMError,
    ModelCallFailed,
    ModelTarget,
    ModelUnavailable,
)
from ffcore.services.litellm_reconcile import (
    LiteLLMAdmin,
    ReconcileScheduler,
    key_hash,
    litellm_settings,
)

SENTINEL = "dummy-not-secret-SENTINEL-4242"
INTERNAL = "sk-dummy-not-secret-internal-key"
MASTER = "sk-dummy-not-secret-master-key"
TARGET = ModelTarget("p.chat-default", "11111111-1111-1111-1111-111111111111")
MESSAGES = [{"role": "user", "content": "hi"}]


class _Stand(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    script: dict = {}
    seen: list = []

    def log_message(self, *args):
        pass

    def _record(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length) if length else b""
        type(self).seen.append({"method": self.command, "path": self.path, "body": body})

    def do_GET(self):
        self._record()
        self._answer()

    def do_POST(self):
        self._record()
        self._answer()

    def _answer(self):
        status, headers, chunks = type(self).script[self.path.split("?")[0]]
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        for data in chunks:
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n")
            self.wfile.flush()
        self.wfile.write(b"0\r\n\r\n")


@pytest.fixture
def stand(settings):
    _Stand.script, _Stand.seen = {}, []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Stand)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    settings.litellm_url = f"http://127.0.0.1:{server.server_address[1]}"
    settings.litellm_master_key = SecretStr(MASTER)
    settings.litellm_internal_key = SecretStr(INTERNAL)
    settings.allowed_internal_hosts = ["127.0.0.0/8"]
    yield _Stand
    server.shutdown()


def _json(status, body, headers=None):
    return (
        status,
        {"content-type": "application/json", **(headers or {})},
        [json.dumps(body).encode()],
    )


def _sse(*events, status=200):
    chunks = [
        f"data: {json.dumps(e) if not isinstance(e, str) else e}\n\n".encode() for e in events
    ]
    return status, {"content-type": "text/event-stream", "x-litellm-model-id": TARGET.id}, chunks


LEAKY_ERROR = {
    "error": {
        "message": f"upstream said Authorization: Bearer {SENTINEL} api_key='{SENTINEL}'",
        "type": "server_error",
        "code": "500",
    }
}


def _chat(settings, stream=False):
    async def go():
        async with LiteLLMClient(settings) as client:
            if not stream:
                return await client.chat(TARGET, MESSAGES, user="u", metadata={})
            async with client.chat_stream(TARGET, MESSAGES, user="u", metadata={}) as s:
                return [c async for c in s], s.result

    return anyio.run(go)


# --- MAJOR-1: the internal key never travels in a URL ---


def test_01_r1_1_internal_key_lookup_uses_hash(settings, stand):
    stand.script["/key/info"] = _json(404, {"error": {"message": "not found", "code": "404"}})
    stand.script["/key/generate"] = _json(200, {"key": "x"})

    async def go():
        async with LiteLLMAdmin(litellm_settings(settings), settings) as admin:
            return await admin.ensure_internal_key()

    assert anyio.run(go) is True
    (lookup, generate) = stand.seen
    assert lookup["path"] == f"/key/info?key={key_hash(INTERNAL)}"
    assert INTERNAL not in lookup["path"]
    assert all(INTERNAL not in r["path"] for r in stand.seen)
    assert json.loads(generate["body"])["key"] == INTERNAL  # body only


def test_01_r1_1_key_hash_is_litellm_token_hash():
    # LiteLLM stores sha256(token).hexdigest(); the reviewer measured /key/info 200 with it.
    assert key_hash("sk-abc") == hashlib.sha256(b"sk-abc").hexdigest()


# --- MAJOR-2: upstream and management error text never reaches logs or exceptions ---


@pytest.mark.parametrize("status", [500, 503, 429])
def test_01_r1_2_model_error_text_not_logged(settings, stand, caplog, status):
    stand.script["/v1/chat/completions"] = _json(
        status, LEAKY_ERROR, {"x-litellm-call-id": "c0ffee00-0000-4000-8000-000000000001"}
    )
    with caplog.at_level(logging.DEBUG), pytest.raises(ModelUnavailable) as err:
        _chat(settings)
    assert SENTINEL not in caplog.text and SENTINEL not in str(err.value)
    assert "c0ffee00-0000-4000-8000-000000000001" in caplog.text  # reference for LiteLLM's own log


def test_01_r1_2_client_4xx_error_text_not_in_exception(settings, stand, caplog):
    stand.script["/v1/chat/completions"] = _json(400, LEAKY_ERROR)
    with caplog.at_level(logging.DEBUG), pytest.raises(LiteLLMError) as err:
        _chat(settings)
    assert SENTINEL not in str(err.value) and SENTINEL not in caplog.text
    assert err.value.status == 400


def test_01_r1_2_management_error_text_not_in_exception(settings, stand):
    stand.script["/model/info"] = _json(500, LEAKY_ERROR)

    async def go():
        async with LiteLLMAdmin(litellm_settings(settings), settings) as admin:
            await admin.model_info()

    with pytest.raises(LiteLLMError) as err:
        anyio.run(go)
    assert SENTINEL not in str(err.value) and "500" in str(err.value)


def test_01_r1_2_scheduler_logs_no_exception_text(caplog):
    async def run():
        raise RuntimeError(f"something with {SENTINEL}")

    async def go():
        scheduler = ReconcileScheduler(run, retries=2, base_delay=0.01)
        scheduler.on_change()
        await scheduler.wait_idle()

    with caplog.at_level(logging.DEBUG):
        asyncio.run(go())
    assert "litellm_reconcile_failed" in caplog.text and "RuntimeError" in caplog.text
    assert SENTINEL not in caplog.text


# --- MAJOR-3: a stream counts only when it completed ---

CONTENT = {"choices": [{"index": 0, "delta": {"content": "par"}}]}
FINISH = {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
USAGE = {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}


def test_01_r1_3_eof_before_finish_is_incomplete(settings, stand):
    stand.script["/v1/chat/completions"] = _sse(CONTENT)
    with pytest.raises(ModelCallFailed) as err:
        _chat(settings, stream=True)
    assert err.value.code == "stream_incomplete"


def test_01_r1_3_in_band_error_is_typed_and_not_yielded(settings, stand, caplog):
    stand.script["/v1/chat/completions"] = _sse(CONTENT, LEAKY_ERROR)
    seen = []

    async def go():
        async with LiteLLMClient(settings) as client:
            async with client.chat_stream(TARGET, MESSAGES, user="u", metadata={}) as s:
                async for chunk in s:
                    seen.append(chunk)

    with caplog.at_level(logging.DEBUG), pytest.raises(ModelCallFailed) as err:
        anyio.run(go)
    assert err.value.code == "upstream_error"
    assert seen == [CONTENT]
    assert SENTINEL not in caplog.text and SENTINEL not in str(err.value)


def test_01_r1_3_complete_stream_ok(settings, stand):
    stand.script["/v1/chat/completions"] = _sse(CONTENT, FINISH, USAGE, "[DONE]")
    chunks, result = _chat(settings, stream=True)
    assert len(chunks) == 3 and result.finish_reason == "stop" and result.usage


def test_01_r1_3_finish_and_usage_without_done_ok(settings, stand):
    stand.script["/v1/chat/completions"] = _sse(CONTENT, FINISH, USAGE)
    _, result = _chat(settings, stream=True)
    assert result.usage["total_tokens"] == 2


def test_01_r1_3_finish_then_eof_without_done_or_usage_incomplete(settings, stand):
    stand.script["/v1/chat/completions"] = _sse(CONTENT, FINISH)
    with pytest.raises(ModelCallFailed):
        _chat(settings, stream=True)


def test_01_r1_3_tool_call_only_stream_ok(settings, stand):
    call = {
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "c1",
                            "type": "function",
                            "function": {"name": "run_sql", "arguments": "{}"},
                        }
                    ]
                },
            }
        ]
    }
    done = {"choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}]}
    stand.script["/v1/chat/completions"] = _sse(call, done, USAGE, "[DONE]")
    _, result = _chat(settings, stream=True)
    assert result.tool_calls and result.finish_reason == "tool_calls"


def test_01_r1_3_non_stream_error_body_is_upstream_error(settings, stand, caplog):
    stand.script["/v1/chat/completions"] = _json(
        200, LEAKY_ERROR, {"x-litellm-model-id": TARGET.id}
    )
    with caplog.at_level(logging.DEBUG), pytest.raises(ModelCallFailed) as err:
        _chat(settings)
    assert err.value.code == "upstream_error"
    assert SENTINEL not in caplog.text
