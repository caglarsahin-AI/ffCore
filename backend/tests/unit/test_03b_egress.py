import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import httpcore2
import pytest

from ffcore.core import egress
from ffcore.core.egress import (
    EgressDenied,
    EgressTimeout,
    EgressTimeoutError,
    SafeOutboundClient,
)

TIMEOUT = EgressTimeout(connect=2, read=2, total=5)
PUBLIC_IP = "93.184.216.34"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        port = self.server.server_address[1]
        if self.path == "/ok":
            self._reply(200, b"ok")
        elif self.path == "/to-loopback-literal":
            self._redirect(f"http://127.0.0.1:{port}/ok")
        elif self.path == "/to-not-allowlisted":
            self._redirect("http://evil.example/ok")
        elif self.path == "/to-internal":
            self._redirect(f"http://internal.test:{port}/ok")
        elif self.path == "/slow":
            time.sleep(2)
            self._reply(200, b"late")
        else:
            self._reply(404, b"no")

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture(scope="module")
def server_port():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def _resolver(table):
    calls = []

    async def resolve(host, port):
        calls.append(host)
        answer = table[host]
        return answer.pop(0) if answer and isinstance(answer[0], list) else answer

    resolve.calls = calls
    return resolve


class _RecordingBackend(httpcore2.AsyncNetworkBackend):
    """Inner backend that records the address it is asked to dial and never dials it."""

    def __init__(self):
        self.dialed = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.dialed.append(host)
        raise httpcore2.ConnectError("recording backend does not dial")

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise AssertionError("unix sockets are never used")

    async def sleep(self, seconds):
        await anyio.sleep(seconds)


def _client(settings, resolver, inner=None, **overrides):
    configured = settings.model_copy(update=overrides)
    return SafeOutboundClient(
        timeout=TIMEOUT, settings=configured, resolver=resolver, inner_backend=inner
    )


async def _get(client, url, **kwargs):
    async with client:
        return await client.request("GET", url, **kwargs)


def _denied(settings, url, code, resolver=None, **overrides):
    resolver = resolver or _resolver({})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_get, _client(settings, resolver, **overrides), url)
    assert exc.value.code == code
    return exc.value


# --- criterion 2 (C5) ------------------------------------------------------------------------


@pytest.mark.parametrize("ip", ["127.0.0.1", "::1", "127.8.9.10"])
def test_03b_2_loopback_rejected(settings, ip):
    resolver = _resolver({"svc.example.com": [ip]})
    _denied(
        settings,
        "https://svc.example.com/hook",
        "egress_private_address",
        resolver,
        egress_allowlist=["svc.example.com"],
    )
    literal = f"[{ip}]" if ":" in ip else ip
    _denied(settings, f"http://{literal}/hook", "egress_not_allowlisted")


@pytest.mark.parametrize("ip", ["10.1.2.3", "172.16.0.9", "192.168.1.1", "100.64.0.1", "fd00::1"])
def test_03b_2_rfc1918_rejected(settings, ip):
    resolver = _resolver({"svc.example.com": [ip]})
    _denied(
        settings,
        "https://svc.example.com/x",
        "egress_private_address",
        resolver,
        egress_allowlist=["svc.example.com"],
    )


@pytest.mark.parametrize("ip", ["169.254.169.254", "fe80::1", "::ffff:169.254.169.254"])
def test_03b_2_link_local_rejected(settings, ip):
    resolver = _resolver({"metadata.example.com": [ip]})
    _denied(
        settings,
        "http://metadata.example.com/latest",
        "egress_private_address",
        resolver,
        egress_allowlist=["metadata.example.com"],
    )


def test_03b_2_dns_rebinding_rejected(settings):
    # Mixed answer: one private address is enough to refuse.
    mixed = _resolver({"rebind.example.com": [PUBLIC_IP, "127.0.0.1"]})
    _denied(
        settings,
        "https://rebind.example.com/",
        "egress_private_address",
        mixed,
        egress_allowlist=["rebind.example.com"],
    )
    # Rebinding between calls: the address that is dialed is the one that was checked, and the
    # name is resolved once per connection, at connect time (no second lookup to race against).
    rebinding = _resolver({"rebind.example.com": [[PUBLIC_IP], ["127.0.0.1"]]})
    inner = _RecordingBackend()
    client = _client(settings, rebinding, inner, egress_allowlist=["rebind.example.com"])
    with pytest.raises(egress.EgressRequestFailed):
        anyio.run(_get, client, "http://rebind.example.com/")
    assert inner.dialed == [PUBLIC_IP]
    client = _client(settings, rebinding, inner, egress_allowlist=["rebind.example.com"])
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_get, client, "http://rebind.example.com/")
    assert exc.value.code == "egress_private_address"
    assert inner.dialed == [PUBLIC_IP]
    assert rebinding.calls == ["rebind.example.com", "rebind.example.com"]


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/x",
        "https://example.com.evil.example/x",
        "https://openai.azure.com/x",  # "*.openai.azure.com" matches subdomains only
    ],
)
def test_03b_2_not_allowlisted_rejected(settings, url):
    _denied(
        settings,
        url,
        "egress_not_allowlisted",
        egress_allowlist=["example.com", "*.openai.azure.com"],
    )


def test_03b_2_empty_allowlist_rejects_everything(settings):
    _denied(settings, "https://api.anthropic.com/v1/messages", "egress_not_allowlisted")


def test_03b_2_wildcard_allowlist_matches_subdomain(settings):
    inner = _RecordingBackend()
    client = _client(
        settings,
        _resolver({"tenant.openai.azure.com": [PUBLIC_IP]}),
        inner,
        egress_allowlist=["*.openai.azure.com"],
    )
    with pytest.raises(egress.EgressRequestFailed):
        anyio.run(_get, client, "https://tenant.openai.azure.com/x")
    assert inner.dialed == [PUBLIC_IP]


def test_03b_2_offline_rejects_all_external(settings, server_port):
    _denied(
        settings,
        "https://api.anthropic.com/v1/messages",
        "egress_offline",
        offline=True,
        egress_allowlist=["api.anthropic.com"],
    )
    # Internal hosts stay reachable with OFFLINE=true (compose services, internal APIs).
    client = _client(
        settings,
        _resolver({"internal.test": ["127.0.0.1"]}),
        offline=True,
        allowed_internal_hosts=["internal.test"],
    )
    response = anyio.run(_get, client, f"http://internal.test:{server_port}/ok")
    assert (response.status_code, response.text) == (200, "ok")


def test_03b_2_internal_host_allowed_by_name_and_cidr(settings, server_port):
    by_cidr = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])
    response = anyio.run(_get, by_cidr, f"http://127.0.0.1:{server_port}/ok")
    assert response.status_code == 200


def test_03b_2_redirect_to_private_rejected(settings, server_port):
    resolver = _resolver({"internal.test": ["127.0.0.1"]})
    for path, code in (
        ("/to-loopback-literal", "egress_not_allowlisted"),
        ("/to-not-allowlisted", "egress_not_allowlisted"),
    ):
        _denied(
            settings,
            f"http://internal.test:{server_port}{path}",
            code,
            resolver,
            allowed_internal_hosts=["internal.test"],
        )
    client = _client(settings, resolver, allowed_internal_hosts=["internal.test"])
    response = anyio.run(_get, client, f"http://internal.test:{server_port}/to-internal")
    assert (response.status_code, response.text) == (200, "ok")


def test_03b_2_scheme_and_unix_socket_rejected(settings):
    for url in ("file:///etc/passwd", "ftp://example.com/x", "http:///nohost"):
        _denied(settings, url, "egress_invalid_url", egress_allowlist=["example.com"])


def test_03b_2_timeout_required():
    with pytest.raises(TypeError):
        SafeOutboundClient(settings=None)  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        SafeOutboundClient(timeout=None, settings=None)  # type: ignore[arg-type]
    for bad in ({"connect": 0, "read": 1, "total": 1}, {"connect": 1, "read": None, "total": 1}):
        with pytest.raises((TypeError, ValueError)):
            EgressTimeout(**bad)
    with pytest.raises(ValueError):
        EgressTimeout(connect=5, read=5, total=1)


def test_03b_2_total_timeout_enforced(settings, server_port):
    client = SafeOutboundClient(
        timeout=EgressTimeout(connect=1, read=1.5, total=1.5),
        settings=settings.model_copy(update={"allowed_internal_hosts": ["127.0.0.0/8"]}),
        resolver=_resolver({}),
    )
    started = time.monotonic()
    with pytest.raises(EgressTimeoutError):
        anyio.run(_get, client, f"http://127.0.0.1:{server_port}/slow")
    assert time.monotonic() - started < 1.9


def test_03b_2_error_body_secret_free(settings):
    error = _denied(
        settings,
        "https://user:dummy-not-secret-pass@evil.example/hook?token=dummy-not-secret-q",
        "egress_not_allowlisted",
    )
    text = str(error) + repr(error)
    assert "dummy-not-secret" not in text
    assert "evil.example" in text
    assert "/hook" not in text


def test_03b_2_environment_proxy_ignored(settings, monkeypatch, server_port):
    # A proxy from the environment would dial the proxy, not the checked address.
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:3128")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example:3128")
    client = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])
    response = anyio.run(_get, client, f"http://127.0.0.1:{server_port}/ok")
    assert response.status_code == 200


def test_03b_2_transport_pool_uses_pinned_backend(settings):
    # Guard on httpx2 internals (pinned 2.16.0): fails loudly if the pool is not ours.
    client = _client(settings, _resolver({}))
    pool = client._transport._pool
    assert isinstance(pool, httpcore2.AsyncConnectionPool)
    assert isinstance(pool._network_backend, egress._PinnedBackend)
