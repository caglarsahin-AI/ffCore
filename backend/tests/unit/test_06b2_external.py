"""06b-2 units: the external agent's call path (services/facade_external.py) against a local
server and a fake resolver: URL policy at registration, the SSRF matrix at call time, no
redirects, the 64 KiB answer limit, the timeout, `tool_calls` never executed, nothing but the
registered key leaves; and FOLLOWUP-142 (non-finite numbers refused)."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest

from ffcore.api.facade_schemas import ChatCompletionRequest
from ffcore.core.errors import ApiError
from ffcore.services import facade_external, facade_proxy
from ffcore.services.facade_external import (
    MAX_EXTERNAL_RESPONSE_BYTES,
    ExternalCallFailed,
    ExternalConfig,
)
from tests.unit.test_03b_egress import PUBLIC_IP, _RecordingBackend, _resolver

KEY = "dummy-not-secret-external-agent-key"


def _answer(content="Merhaba", **message) -> bytes:
    choice = {"index": 0, "message": {"role": "assistant", "content": content, **message}}
    return json.dumps({"id": "x", "object": "chat.completion", "choices": [choice]}).encode()


class _Agent(BaseHTTPRequestHandler):
    """A fake OpenAI-compatible agent; the base_url path picks the behaviour."""

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        self.server.seen.append(
            {
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": body,
            }
        )
        mode = self.path.split("/")[1]
        if mode == "ok":
            self._reply(200, _answer())
        elif mode == "tools":
            calls = [
                {"id": "c1", "type": "function", "function": {"name": "rm", "arguments": "{}"}}
            ]
            self._reply(200, _answer("Tamam", tool_calls=calls, function_call={"name": "rm"}))
        elif mode == "tools-only":
            calls = [
                {"id": "c1", "type": "function", "function": {"name": "rm", "arguments": "{}"}}
            ]
            self._reply(200, _answer(None, tool_calls=calls))
        elif mode == "big":
            self._reply(200, b"x" * (MAX_EXTERNAL_RESPONSE_BYTES + 1))
        elif mode == "big-chunked":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            piece = b"y" * 8192
            for _ in range(MAX_EXTERNAL_RESPONSE_BYTES // len(piece) + 2):
                self.wfile.write(b"%x\r\n%s\r\n" % (len(piece), piece))
            self.wfile.write(b"0\r\n\r\n")
        elif mode == "slow":
            time.sleep(2.5)
            self._reply(200, _answer())
        elif mode == "redirect":
            port = self.server.server_address[1]
            self.send_response(307)
            self.send_header("Location", f"http://agent.test:{port}/ok/chat/completions")
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif mode == "fail":
            self._reply(500, b'{"error": "dummy-not-secret-upstream-detail"}')
        elif mode == "not-json":
            self._reply(200, b"<html>hello</html>")
        elif mode == "deep":  # review r1 MAJOR-1: nesting the JSON parser cannot take
            self._reply(200, b"[" * 30_000 + b"]" * 30_000)
        elif mode == "deepdict":
            self._reply(200, b'{"choices": ' + b"[" * 30_000 + b"]" * 30_000 + b"}")
        elif mode == "no-content":
            self._reply(200, b'{"choices": [{"message": {"role": "assistant"}}]}')
        elif mode == "content-list":
            body = {"choices": [{"message": {"content": [{"type": "text", "text": "x"}]}}]}
            self._reply(200, json.dumps(body).encode())
        elif mode == "choice-text":
            self._reply(200, b'{"choices": ["x"]}')
        else:
            self._reply(404, b"no")

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def agent_port():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Agent)
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server
    server.shutdown()


@pytest.fixture
def local(settings):
    """Settings where `agent.test` is an internal host (the local fake agent)."""
    return settings.model_copy(update={"allowed_internal_hosts": ["agent.test"]})


def _config(base_url: str, model: str = "uzak-model") -> ExternalConfig:
    return ExternalConfig(base_url=base_url, model=model, api_key=KEY)


def _call(settings, config, resolver, **kw):
    messages = [{"role": "user", "content": "Soru"}]
    return anyio.run(
        lambda: facade_external.call_upstream(
            config, messages, {}, settings, resolver=resolver, **kw
        )
    )


def _local_resolver():
    return _resolver({"agent.test": ["127.0.0.1"]})


# --- FOLLOWUP-142: NaN and infinities are not numbers in OpenAI's ranges ---------------------


@pytest.mark.parametrize("name", ["temperature", "top_p", "presence_penalty", "frequency_penalty"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_06b2_15_numeric_non_finite(name, value):
    with pytest.raises(ApiError) as exc:
        facade_proxy.call_params(
            ChatCompletionRequest.model_construct(model="m", messages=[], **{name: value})
        )
    assert (exc.value.status_code, exc.value.code, exc.value.param) == (
        400,
        "invalid_parameter",
        name,
    )


# --- registration and publish: the base_url policy ----------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://agent.example/x",
        "ftp://agent.example/",
        "agent.example/v1",
        "https://user:dummy-not-secret@agent.example/v1",  # credentials in the URL
        "https://agent.example:99999/v1",  # no such port
        "https://agent.example:0/v1",
    ],
)
def test_06b2_4_register_url_scheme_refused(settings, url):
    allowed = settings.model_copy(update={"egress_allowlist": ["agent.example"]})
    with pytest.raises(ApiError) as exc:
        anyio.run(
            lambda: facade_external.check_base_url(
                url, allowed, resolver=_resolver({"agent.example": [PUBLIC_IP]})
            )
        )
    assert (exc.value.status_code, exc.value.code) == (422, "external_agent_url_refused")


def test_06b2_4_register_url_policy(settings):
    allowed = settings.model_copy(update={"egress_allowlist": ["agent.example"]})

    def check(s, url, table):
        return anyio.run(lambda: facade_external.check_base_url(url, s, resolver=_resolver(table)))

    # allowlisted, public address: accepted
    check(allowed, "https://agent.example/v1", {"agent.example": [PUBLIC_IP]})
    for s, url, table in [
        (settings, "https://agent.example/v1", {"agent.example": [PUBLIC_IP]}),  # not allowlisted
        (allowed, "https://agent.example/v1", {"agent.example": ["10.0.0.5"]}),  # private
        (allowed, "http://169.254.169.254/latest", {}),
        (allowed.model_copy(update={"offline": True}), "https://agent.example/v1", {}),
    ]:
        with pytest.raises(ApiError) as exc:
            check(s, url, table)
        assert exc.value.code == "external_agent_url_refused"
    # airgap: OFFLINE=true, only ALLOWED_INTERNAL_HOSTS
    airgap = settings.model_copy(update={"offline": True, "allowed_internal_hosts": ["agent.test"]})
    check(airgap, "http://agent.test:8080/v1", {"agent.test": ["10.0.0.7"]})


# --- review r1 MINOR-1: the platform's own services are not targets ----------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://litellm:4000/v1",
        "http://LiteLLM./v1",  # case and the root dot do not hide a name
        "http://langfuse-web:3000/api/public",
        "http://mcp-sql:8000/v1",
        "http://ollama:11434/v1",
        "http://host.docker.internal:11434/v1",
        "http://backend:8000/v1",
        "http://my-litellm:4000/v1",  # LITELLM_URL's host, whatever it is called
        "http://127.0.0.1:8000/v1",  # the backend itself, from inside its container
    ],
)
def test_06b2_r1_platform_hosts_reserved(settings, url):
    internal = settings.model_copy(
        update={
            "litellm_url": "http://my-litellm:4000",
            "allowed_internal_hosts": [
                "litellm",
                "langfuse-web",
                "mcp-sql",
                "ollama",
                "host.docker.internal",
                "backend",
                "my-litellm",
                "127.0.0.1",
            ],
        }
    )
    with pytest.raises(ApiError) as exc:
        anyio.run(lambda: facade_external.check_base_url(url, internal, resolver=_any_private()))
    assert (exc.value.status_code, exc.value.code, exc.value.param) == (
        422,
        "external_agent_host_reserved",
        "base_url",
    )


def test_06b2_r1_other_internal_hosts_stay(settings):
    """KARARLAR:172: an internal host the installation allows is still a valid target."""
    internal = settings.model_copy(update={"allowed_internal_hosts": ["agent.test", "127.0.0.1"]})
    for url in ("http://agent.test:8080/v1", "http://127.0.0.1:18080/v1"):
        anyio.run(
            lambda url=url: facade_external.check_base_url(url, internal, resolver=_any_private())
        )


@pytest.mark.parametrize(
    "url",
    [
        "https://agent.example/v1?api-key=dummy-not-secret-qs",
        "https://agent.example/v1?",
        "https://agent.example/v1#frag",
        "https://agent.example/v1/#",
    ],
)
def test_06b2_r1_base_url_query_refused(settings, url):
    """Review r1 MINOR-2: scheme, host, port and path only; a query or fragment would carry a
    credential into every place the URL is shown and choose the upstream path."""
    allowed = settings.model_copy(update={"egress_allowlist": ["agent.example"]})
    with pytest.raises(ApiError) as exc:
        anyio.run(
            lambda: facade_external.check_base_url(
                url, allowed, resolver=_resolver({"agent.example": [PUBLIC_IP]})
            )
        )
    assert (exc.value.status_code, exc.value.code, exc.value.param) == (
        422,
        "base_url_query_not_allowed",
        "base_url",
    )


def _any_private():
    async def resolve(host, port):
        return ["10.0.0.9"]

    return resolve


# --- the call: SSRF matrix -------------------------------------------------------------------


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.5", "169.254.169.254", "::1", "fd00::1", "192.168.1.10"]
)
def test_06b2_5_ssrf_matrix_private_address(settings, address):
    allowed = settings.model_copy(update={"egress_allowlist": ["agent.example"]})
    backend = _RecordingBackend()
    with pytest.raises(ExternalCallFailed) as exc:
        _call(
            allowed,
            _config("https://agent.example/v1"),
            _resolver({"agent.example": [address]}),
            inner_backend=backend,
        )
    assert (exc.value.status_code, exc.value.code) == (502, "external_agent_failed")
    assert exc.value.audit["error_code"] == "egress_private_address"
    assert backend.dialed == []  # nothing was dialed


def test_06b2_5_ssrf_dns_rebinding(settings):
    """Public at registration, private at call time: refused at the dial."""
    allowed = settings.model_copy(update={"egress_allowlist": ["agent.example"]})
    resolver = _resolver({"agent.example": [[PUBLIC_IP], ["10.0.0.5"]]})
    anyio.run(
        lambda: facade_external.check_base_url(
            "https://agent.example/v1", allowed, resolver=resolver
        )
    )
    backend = _RecordingBackend()
    with pytest.raises(ExternalCallFailed) as exc:
        _call(allowed, _config("https://agent.example/v1"), resolver, inner_backend=backend)
    assert exc.value.audit["error_code"] == "egress_private_address"
    assert backend.dialed == []


def test_06b2_7_offline_refuses_external(settings):
    offline = settings.model_copy(update={"offline": True, "egress_allowlist": ["agent.example"]})
    with pytest.raises(ExternalCallFailed) as exc:
        _call(offline, _config("https://agent.example/v1"), _resolver({}))
    assert exc.value.audit["error_code"] == "egress_offline"


def test_06b2_6_redirect_not_followed(local, agent_port):
    port = agent_port.server_address[1]
    before = len(agent_port.seen)
    with pytest.raises(ExternalCallFailed) as exc:
        _call(local, _config(f"http://agent.test:{port}/redirect"), _local_resolver())
    assert (exc.value.status_code, exc.value.code) == (502, "external_agent_failed")
    assert exc.value.audit["error_code"] == "egress_too_many_redirects"
    assert [s["path"] for s in agent_port.seen[before:]] == ["/redirect/chat/completions"]


# --- the call: answer limits and content -----------------------------------------------------


@pytest.mark.parametrize("mode", ["big", "big-chunked"])
def test_06b2_8_response_size_limit(local, agent_port, mode):
    port = agent_port.server_address[1]
    with pytest.raises(ExternalCallFailed) as exc:
        _call(local, _config(f"http://agent.test:{port}/{mode}"), _local_resolver())
    assert (exc.value.status_code, exc.value.code) == (502, "external_agent_response_too_large")
    assert exc.value.audit["response_bytes"] > MAX_EXTERNAL_RESPONSE_BYTES


def test_06b2_9_timeout(local, agent_port):
    port = agent_port.server_address[1]
    fast = local.model_copy(update={"llm_call_timeout_s": 1})
    with pytest.raises(ExternalCallFailed) as exc:
        _call(fast, _config(f"http://agent.test:{port}/slow"), _local_resolver())
    assert (exc.value.status_code, exc.value.code) == (504, "external_agent_timeout")


def test_06b2_10_tool_calls_ignored(local, agent_port):
    port = agent_port.server_address[1]
    result = _call(local, _config(f"http://agent.test:{port}/tools"), _local_resolver())
    assert result.content == "Tamam"
    assert result.ignored_fields == ["function_call", "tool_calls"]
    with pytest.raises(ExternalCallFailed) as exc:
        _call(local, _config(f"http://agent.test:{port}/tools-only"), _local_resolver())
    assert exc.value.code == "external_agent_failed"
    assert exc.value.audit["error_code"] == "invalid_answer"


@pytest.mark.parametrize("mode", ["fail", "not-json"])
def test_06b2_failed_answer_not_echoed(local, agent_port, mode):
    port = agent_port.server_address[1]
    with pytest.raises(ExternalCallFailed) as exc:
        _call(local, _config(f"http://agent.test:{port}/{mode}"), _local_resolver())
    assert exc.value.code == "external_agent_failed"
    assert "dummy-not-secret" not in exc.value.message and "html" not in exc.value.message


@pytest.mark.parametrize(
    "mode", ["deep", "deepdict", "not-json", "no-content", "content-list", "choice-text"]
)
def test_06b2_r1_unparsable_answer_is_a_coded_failure(local, agent_port, mode):
    """Review r1 MAJOR-1: every answer that cannot be read (too deep for the parser, not JSON,
    no text content) is one coded failure with its audit record, never an uncaught error."""
    port = agent_port.server_address[1]
    with pytest.raises(ExternalCallFailed) as exc:
        _call(local, _config(f"http://agent.test:{port}/{mode}"), _local_resolver())
    assert (exc.value.status_code, exc.value.code) == (502, "external_agent_failed")
    assert exc.value.audit["error_code"] == "invalid_answer"
    assert exc.value.audit["upstream_status"] == 200 and exc.value.audit["response_bytes"] > 0


def test_06b2_12_only_registered_key_leaves(local, agent_port):
    port = agent_port.server_address[1]
    before = len(agent_port.seen)
    result = _call(local, _config(f"http://agent.test:{port}/ok"), _local_resolver())
    assert result.content == "Merhaba" and result.upstream_status == 200
    assert result.host == "agent.test" and result.response_bytes > 0
    sent = agent_port.seen[before]
    assert sent["path"] == "/ok/chat/completions"
    assert sent["headers"]["authorization"] == f"Bearer {KEY}"
    assert not any(h.startswith("x-") for h in sent["headers"])  # no X-On-Behalf-Of, no x-*
    assert sent["body"] == {
        "model": "uzak-model",
        "messages": [{"role": "user", "content": "Soru"}],
        "stream": False,
    }


def test_06b2_3_config_secret_masked():
    config = _config("https://agent.example/v1")
    assert KEY not in repr(config) and KEY not in str(config.public())
    assert config.public() == {
        "base_url": "https://agent.example/v1",
        "model": "uzak-model",
        "api_key": "***",
    }
