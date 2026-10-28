"""Package 01: SafeOutboundClient.stream() follows the same policy as request() (C5).

The 03b policy cases are repeated through stream(): private addresses, OFFLINE, allowlist,
redirect re-checks, credential and cookie dropping. Plus what only a stream has: chunks arrive
before the body is complete, and the response is closed on exit.
"""

import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import pytest

from ffcore.core.egress import EgressDenied, EgressTimeout, EgressTimeoutError
from tests.unit import test_03b_egress as policy
from tests.unit.test_03b_egress import (
    CREDENTIALS,
    _client,
    _credential_client,
    _echo,
    _resolver,
)

# The 03b test servers, shared as fixtures (module scope there and here).
servers = policy.servers
server_port = policy.server_port


async def _stream_get(client, url, **kwargs):
    async with client:
        async with client.stream("GET", url, **kwargs) as response:
            await response.aread()
            return response


def _stream_denied(settings, url, code, resolver=None, **overrides):
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_stream_get, _client(settings, resolver or _resolver({}), **overrides), url)
    assert exc.value.code == code


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "169.254.169.254"])
def test_01_stream_private_address_rejected(settings, ip):
    resolver = _resolver({"evil.example": [ip]})
    _stream_denied(
        settings,
        "http://evil.example/x",
        "egress_private_address",
        resolver,
        egress_allowlist=["evil.example"],
    )


def test_01_stream_offline_and_allowlist(settings):
    _stream_denied(
        settings,
        "https://api.anthropic.com/v1/messages",
        "egress_offline",
        offline=True,
        egress_allowlist=["api.anthropic.com"],
    )
    _stream_denied(settings, "https://api.anthropic.com/v1/messages", "egress_not_allowlisted")


def test_01_stream_redirect_rechecked(settings, server_port):
    resolver = _resolver({"internal.test": ["127.0.0.1"]})
    _stream_denied(
        settings,
        f"http://internal.test:{server_port}/to-not-allowlisted",
        "egress_not_allowlisted",
        resolver,
        allowed_internal_hosts=["internal.test"],
    )
    client = _client(settings, resolver, allowed_internal_hosts=["internal.test"])
    response = anyio.run(_stream_get, client, f"http://internal.test:{server_port}/to-internal")
    assert (response.status_code, response.text) == (200, "ok")


@pytest.mark.parametrize("path", ["/to-other-host", "/to-other-port"])
def test_01_stream_redirect_drops_credentials(settings, server_port, path):
    client = _credential_client(settings)
    url = f"http://a.test:{server_port}{path}"
    seen = _echo(anyio.run(lambda: _stream_get(client, url, headers=CREDENTIALS)))
    assert "authorization" not in seen and "x-api-key" not in seen


def test_01_stream_redirect_same_origin_keeps_credentials(settings, server_port):
    client = _credential_client(settings)
    url = f"http://a.test:{server_port}/to-same"
    seen = _echo(anyio.run(lambda: _stream_get(client, url, headers=CREDENTIALS)))
    assert seen["authorization"] == CREDENTIALS["Authorization"]


def test_01_stream_post_303_drops_credentials(settings, server_port):
    client = _credential_client(settings)

    async def call():
        async with client:
            url = f"http://a.test:{server_port}/post-to-other-host"
            async with client.stream("POST", url, headers=CREDENTIALS, json={"x": 1}) as r:
                await r.aread()
                return r

    seen = _echo(anyio.run(call))
    assert "authorization" not in seen


def test_01_stream_set_cookie_not_carried(settings, server_port):
    client = _client(
        settings,
        _resolver({"a.example.com": ["127.0.0.1"], "b.example.com": ["127.0.0.1"]}),
        allowed_internal_hosts=["a.example.com", "b.example.com"],
    )
    url = f"http://a.example.com:{server_port}/set-cookie-other-host"
    assert "cookie" not in _echo(anyio.run(lambda: _stream_get(client, url)))


def test_01_stream_total_timeout_until_headers(settings, server_port):
    client = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])
    client._timeout = EgressTimeout(connect=0.3, read=0.4, total=0.5)
    with pytest.raises(EgressTimeoutError):
        anyio.run(_stream_get, client, f"http://127.0.0.1:{server_port}/slow")


# --- stream-only behaviour ---


class _Chunked(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for piece in (b"first", b"second"):
            self.wfile.write(f"{len(piece):x}\r\n".encode() + piece + b"\r\n")
            self.wfile.flush()
            time.sleep(0.6)
        self.wfile.write(b"0\r\n\r\n")


@pytest.fixture
def chunked_port():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Chunked)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def test_01_stream_chunks_arrive_before_body_ends(settings, chunked_port):
    client = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])
    client._timeout = EgressTimeout(connect=2, read=2, total=5)

    async def read():
        arrivals = []
        started = time.monotonic()
        async with client:
            async with client.stream("GET", f"http://127.0.0.1:{chunked_port}/") as response:
                async for chunk in response.aiter_raw():
                    arrivals.append((chunk, time.monotonic() - started))
            closed = response.is_closed
        return arrivals, closed

    arrivals, closed = anyio.run(read)
    assert arrivals[0][0] == b"first"
    assert arrivals[0][1] < 0.5  # before the server finished (it sleeps 1.2 s in total)
    assert closed


@pytest.mark.parametrize(
    "option",
    [
        {"follow_redirects": True},
        {"transport": object()},
        {"trust_env": True},
        {"verify": False},
        {"timeout": None},
        {"extensions": {"timeout": {}}},
    ],
)
def test_01_stream_policy_options_rejected(settings, option):
    client = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])

    async def call():
        async with client:
            async with client.stream("GET", "http://127.0.0.1:1/ok", **option):
                pass

    with pytest.raises(TypeError):
        anyio.run(call)
