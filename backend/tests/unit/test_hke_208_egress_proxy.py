"""FOLLOWUP-208 (K-HKE-0002 K2 A): EGRESS_PROXY_URL sends the backend's external calls through
the egress forward proxy.

Host rules (scheme, OFFLINE, EGRESS_ALLOWLIST, each redirect hop) stay in the backend and run
before the proxy is reached; the address rules (private address, DNS rebinding) belong to the
proxy, which resolves and dials (deploy/egress/squid.conf `to_private`). Internal hosts keep the
direct pinned path. The proxy transport dials the proxy origin and nothing else. Empty setting:
the direct pinned path for every host, as before.
"""

import socket
import socketserver
import threading

import anyio
import httpcore2
import pytest
from pydantic import ValidationError

from ffcore.core import egress
from ffcore.core.config import Settings
from ffcore.core.egress import (
    EgressDenied,
    EgressRequestFailed,
    EgressTimeout,
    SafeOutboundClient,
    check_http_destination,
    policy_http_client,
)

TIMEOUT = EgressTimeout(connect=2, read=2, total=5)


class _ProxyHandler(socketserver.StreamRequestHandler):
    """A tiny forward proxy: records the request line and answers like Squid would."""

    def handle(self):
        line = self.rfile.readline().decode("latin-1").strip()
        while self.rfile.readline() not in (b"\r\n", b"\n", b""):
            pass
        self.server.seen.append(line)
        method, target, _ = line.split(" ", 2)
        if method == "CONNECT":
            self._reply(403, "Forbidden", denied=True)
        elif "denied.example" in target:
            self._reply(403, "Forbidden", denied=True)
        elif "redirect.example" in target:
            self._reply(302, "Found", location="http://elsewhere.example/x")
        else:
            self._reply(200, "OK", body=b"via-proxy")

    def _reply(self, status, reason, body=b"", denied=False, location=None):
        head = [f"HTTP/1.1 {status} {reason}", f"Content-Length: {len(body)}"]
        if denied:
            head.append("X-Squid-Error: ERR_ACCESS_DENIED 0")
        if location:
            head.append(f"Location: {location}")
        self.wfile.write(("\r\n".join(head) + "\r\n\r\n").encode() + body)


class _OriginHandler(socketserver.StreamRequestHandler):
    def handle(self):
        while self.rfile.readline() not in (b"\r\n", b"\n", b""):
            pass
        self.wfile.write(b"HTTP/1.1 200 OK\r\nContent-Length: 6\r\n\r\ndirect")


def _serve(handler):
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    server.seen = []
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture(scope="module")
def proxy():
    server = _serve(_ProxyHandler)
    yield server
    server.shutdown()


@pytest.fixture(scope="module")
def origin():
    server = _serve(_OriginHandler)
    yield server
    server.shutdown()


@pytest.fixture(autouse=True)
def _clear(proxy):
    proxy.seen.clear()


def _resolver(table):
    calls = []

    async def resolve(host, port):
        calls.append(host)
        if host not in table:
            raise socket.gaierror("no such name in the test table")
        return list(table[host])

    resolve.calls = calls
    return resolve


def _proxied(settings, proxy, **overrides):
    values = {
        "egress_proxy_url": f"http://proxy.test:{proxy.server_address[1]}",
        "egress_allowlist": ["svc.example.com", "denied.example", "redirect.example"],
    }
    values.update(overrides)
    return settings.model_copy(update=values)


async def _get(client, url):
    async with client:
        return await client.request("GET", url)


def _client(settings, resolver):
    return SafeOutboundClient(timeout=TIMEOUT, settings=settings, resolver=resolver)


# --- setting -------------------------------------------------------------------------------


def test_hke_208_setting_defaults_to_empty(settings):
    assert settings.egress_proxy_url == ""


@pytest.mark.parametrize(
    "value",
    [
        "https://egress-proxy:3128",
        "http://user:pass@egress-proxy:3128",
        "http://egress-proxy:3128/path",
        "http://egress-proxy:3128?x=1",
        "http://egress-proxy",
        "socks5://egress-proxy:1080",
        "egress-proxy:3128",
    ],
)
def test_hke_208_setting_refuses_anything_but_http_host_port(settings, value):
    with pytest.raises(ValidationError, match="egress_proxy_url_invalid"):
        Settings(**{**settings.model_dump(), "egress_proxy_url": value})


def test_hke_208_setting_accepts_http_host_port(settings):
    configured = Settings(
        **{**settings.model_dump(), "egress_proxy_url": "http://egress-proxy:3128"}
    )
    assert configured.egress_proxy_url == "http://egress-proxy:3128"


# --- routing -------------------------------------------------------------------------------


def test_hke_208_external_host_goes_through_the_proxy_by_name(settings, proxy):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    response = anyio.run(
        _get, _client(_proxied(settings, proxy), resolver), "http://svc.example.com/v1/models"
    )
    assert response.status_code == 200 and response.content == b"via-proxy"
    assert proxy.seen == ["GET http://svc.example.com/v1/models HTTP/1.1"]
    # the backend never resolves the target: the proxy does (address rules live there)
    assert resolver.calls == ["proxy.test"]


def test_hke_208_https_target_is_a_connect_tunnel_by_name(settings, proxy):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(
            _get, _client(_proxied(settings, proxy), resolver), "https://svc.example.com/v1/x"
        )
    assert exc.value.code == "egress_proxy_denied"
    assert proxy.seen == ["CONNECT svc.example.com:443 HTTP/1.1"]


def test_hke_208_proxy_refusal_of_a_plain_request_is_an_error(settings, proxy):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_get, _client(_proxied(settings, proxy), resolver), "http://denied.example/v1/x")
    assert exc.value.code == "egress_proxy_denied"
    assert "ERR_ACCESS_DENIED" in str(exc.value)


@pytest.mark.parametrize(
    ("overrides", "url", "code"),
    [
        ({}, "http://not-listed.example/x", "egress_not_allowlisted"),
        ({"offline": True}, "http://svc.example.com/x", "egress_offline"),
        ({}, "ftp://svc.example.com/x", "egress_invalid_url"),
    ],
)
def test_hke_208_host_rules_run_before_the_proxy(settings, proxy, overrides, url, code):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_get, _client(_proxied(settings, proxy, **overrides), resolver), url)
    assert exc.value.code == code
    assert proxy.seen == []


def test_hke_208_redirect_hop_is_checked_before_the_proxy(settings, proxy):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(
            _get, _client(_proxied(settings, proxy), resolver), "http://redirect.example/start"
        )
    assert exc.value.code == "egress_not_allowlisted"
    assert proxy.seen == ["GET http://redirect.example/start HTTP/1.1"]


def test_hke_208_internal_host_goes_direct(settings, proxy, origin):
    resolver = _resolver({"proxy.test": ["127.0.0.1"], "internal.test": ["127.0.0.1"]})
    configured = _proxied(settings, proxy, allowed_internal_hosts=["internal.test"])
    response = anyio.run(
        _get, _client(configured, resolver), f"http://internal.test:{origin.server_address[1]}/x"
    )
    assert response.content == b"direct"
    assert proxy.seen == []


def test_hke_208_unreachable_proxy_fails_without_a_direct_fallback(settings):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    resolver = _resolver({"proxy.test": ["127.0.0.1"], "svc.example.com": ["93.184.216.34"]})
    configured = settings.model_copy(
        update={
            "egress_proxy_url": f"http://proxy.test:{closed_port}",
            "egress_allowlist": ["svc.example.com"],
        }
    )
    with pytest.raises(EgressRequestFailed):
        anyio.run(_get, _client(configured, resolver), "http://svc.example.com/x")
    assert resolver.calls == ["proxy.test"]


def test_hke_208_refused_proxy_connection_is_egress_proxy_unreachable(settings):
    # r1 NOTE-2: a proxy that refuses the connection (port closed, service down) has the same
    # code as a proxy name that does not resolve, for the operator's diagnosis.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        closed_port = sock.getsockname()[1]
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})
    configured = settings.model_copy(
        update={
            "egress_proxy_url": f"http://proxy.test:{closed_port}",
            "egress_allowlist": ["svc.example.com"],
        }
    )
    for url in ("http://svc.example.com/x", "https://svc.example.com/x"):
        with pytest.raises(EgressRequestFailed) as exc:
            anyio.run(_get, _client(configured, resolver), url)
        assert exc.value.code == "egress_proxy_unreachable", url


def test_hke_208_empty_setting_keeps_the_direct_pinned_path(settings):
    # unchanged behaviour: the backend resolves and checks the target itself
    resolver = _resolver({"svc.example.com": ["10.0.0.5"]})
    configured = settings.model_copy(update={"egress_allowlist": ["svc.example.com"]})
    with pytest.raises(EgressDenied) as exc:
        anyio.run(_get, _client(configured, resolver), "http://svc.example.com/x")
    assert exc.value.code == "egress_private_address"
    assert resolver.calls == ["svc.example.com"]


def test_hke_208_proxy_backend_dials_only_the_proxy_origin():
    class _Inner(httpcore2.AsyncNetworkBackend):
        dialed = []

        async def connect_tcp(self, host, port, **_):
            self.dialed.append((host, port))
            raise httpcore2.ConnectError("not dialing in this test")

        async def connect_unix_socket(self, *a, **k):
            raise AssertionError

        async def sleep(self, seconds):
            await anyio.sleep(seconds)

    inner = _Inner()
    backend = egress._ProxyOnlyBackend(
        "egress-proxy", 3128, _resolver({"egress-proxy": ["172.18.0.9"]}), inner
    )

    async def dial(host, port):
        await backend.connect_tcp(host, port)

    with pytest.raises(EgressDenied) as exc:
        anyio.run(dial, "svc.example.com", 443)
    assert exc.value.code == "egress_proxy_only"
    with pytest.raises(EgressDenied):
        anyio.run(dial, "egress-proxy", 3129)
    assert inner.dialed == []
    with pytest.raises(httpcore2.ConnectError):
        anyio.run(dial, "egress-proxy", 3128)
    assert inner.dialed == [("172.18.0.9", 3128)]


def test_hke_208_policy_http_client_uses_the_proxy(settings, proxy):
    resolver = _resolver({"proxy.test": ["127.0.0.1"]})

    async def call():
        async with policy_http_client(
            timeout=TIMEOUT, settings=_proxied(settings, proxy), resolver=resolver
        ) as client:
            return await client.get("http://svc.example.com/mcp")

    assert anyio.run(call).content == b"via-proxy"
    assert proxy.seen == ["GET http://svc.example.com/mcp HTTP/1.1"]


def test_hke_208_check_http_destination_leaves_addresses_to_the_proxy(settings, proxy):
    resolver = _resolver({})
    configured = _proxied(settings, proxy)
    assert (
        anyio.run(
            lambda: check_http_destination(
                configured, "https://svc.example.com/x", resolver=resolver
            )
        )
        == []
    )
    assert resolver.calls == []
    with pytest.raises(EgressDenied) as exc:
        anyio.run(
            lambda: check_http_destination(configured, "https://nope.example/x", resolver=resolver)
        )
    assert exc.value.code == "egress_not_allowlisted"


def test_hke_208_check_http_destination_still_resolves_internal_hosts(settings, proxy):
    resolver = _resolver({"internal.test": ["10.0.0.7"]})
    configured = _proxied(settings, proxy, allowed_internal_hosts=["internal.test"])
    addresses = anyio.run(
        lambda: check_http_destination(configured, "http://internal.test/x", resolver=resolver)
    )
    assert addresses == ["10.0.0.7"]
