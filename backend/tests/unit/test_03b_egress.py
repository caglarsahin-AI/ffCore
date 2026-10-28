import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import anyio
import httpcore2
import httpx2
import pytest

from ffcore.core import egress
from ffcore.core.egress import (
    EgressDenied,
    EgressRequestFailed,
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
        elif self.path == "/echo":
            self._reply(200, json.dumps({k.lower(): v for k, v in self.headers.items()}).encode())
        elif self.path == "/to-same":
            self._redirect("/echo")
        elif self.path == "/to-other-host":
            self._redirect(f"http://b.test:{port}/echo")
        elif self.path == "/to-other-port":
            self._redirect(f"http://a.test:{self.server.peer_port}/echo")
        elif self.path == "/set-cookie-other-port":
            self._redirect(
                f"http://a.example.com:{self.server.peer_port}/echo",
                cookie="session=dummy-not-secret-jar; Path=/",
            )
        elif self.path == "/set-cookie-other-host":
            self._redirect(
                f"http://b.example.com:{port}/echo",
                cookie="session=dummy-not-secret-jar; Domain=example.com; Path=/",
            )
        elif self.path == "/set-cookie-same-origin":
            self._redirect("/echo", cookie="session=dummy-not-secret-jar; Path=/")
        elif self.path == "/slow":
            time.sleep(2)
            self._reply(200, b"late")
        else:
            self._reply(404, b"no")

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        if self.path == "/post-to-other-host":
            self.send_response(303)
            self.send_header("Location", f"http://b.test:{self.server.server_address[1]}/echo")
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._reply(404, b"no")

    def _reply(self, status, body):
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, location, cookie=None):
        self.send_response(302)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture(scope="module")
def servers():
    first = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    second = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    first.peer_port = second.server_address[1]
    second.peer_port = first.server_address[1]
    for server in (first, second):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    yield first.server_address[1], second.server_address[1]
    for server in (first, second):
        server.shutdown()


@pytest.fixture(scope="module")
def server_port(servers):
    return servers[0]


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


# --- unresolvable host (10a-forms, K-10af-0003): a failed call, never an unhandled OSError ------

UNRESOLVABLE = "no-such-provider.invalid"  # RFC 6761: never resolves


def test_03b_2_unresolvable_host_is_request_failed(settings):
    client = _client(settings, egress.system_resolver, allowed_internal_hosts=[UNRESOLVABLE])
    with pytest.raises(EgressRequestFailed) as exc:
        anyio.run(_get, client, f"http://{UNRESOLVABLE}:11434/api/tags")
    assert exc.value.code == "egress_dns_failed"
    assert UNRESOLVABLE in str(exc.value)
    assert "/api/tags" not in str(exc.value)
    assert exc.value.__cause__ is None  # the system text is not carried along


def test_03b_2_resolver_os_error_is_request_failed(settings):
    async def failing(host, port):
        raise OSError("resolver exploded with system detail")

    client = _client(settings, failing, allowed_internal_hosts=["svc.internal"])
    with pytest.raises(EgressRequestFailed) as exc:
        anyio.run(_get, client, "http://svc.internal/ok")
    assert exc.value.code == "egress_dns_failed"
    assert "system detail" not in str(exc.value)


def test_03b_2_unresolvable_host_still_needs_the_policy(settings):
    # The policy check comes first and stays the same: a host that is not allowed is denied
    # before any name lookup.
    calls = []

    async def resolver(host, port):
        calls.append(host)
        raise OSError("not reached")

    _denied(settings, f"http://{UNRESOLVABLE}/x", "egress_not_allowlisted", resolver)
    assert calls == []


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


# --- review r1 MAJOR-1: callers cannot loosen the policy per request ---------------------------


@pytest.mark.parametrize(
    "option",
    [
        {"follow_redirects": True},
        {"transport": object()},
        {"trust_env": True},
        {"proxy": "http://proxy.example:3128"},
        {"verify": False},
        {"mounts": {}},
        {"timeout": None},
        {"extensions": {"timeout": {}}},
    ],
)
def test_03b_2_policy_options_rejected(settings, option):
    client = _client(settings, _resolver({}), allowed_internal_hosts=["127.0.0.0/8"])

    async def call():
        async with client:
            return await client.request("GET", "http://127.0.0.1:1/ok", **option)

    with pytest.raises(TypeError):
        anyio.run(call)


def test_03b_2_redirect_chains_rechecked(settings, server_port):
    resolver = _resolver({"a.test": ["127.0.0.1"]})
    # Allowed internal start, redirect to a public host that is not allowlisted.
    _denied(
        settings,
        f"http://a.test:{server_port}/to-not-allowlisted",
        "egress_not_allowlisted",
        resolver,
        allowed_internal_hosts=["a.test"],
    )
    # OFFLINE: internal start, redirect to an external host.
    _denied(
        settings,
        f"http://a.test:{server_port}/to-not-allowlisted",
        "egress_offline",
        resolver,
        offline=True,
        allowed_internal_hosts=["a.test"],
        egress_allowlist=["evil.example"],
    )


def test_03b_2_connect_enforces_host_policy(settings):
    # Defence in depth: the connection layer refuses hosts the URL check would refuse.
    inner = _RecordingBackend()
    configured = settings.model_copy(update={"egress_allowlist": ["allowed.example"]})
    policy = egress.EgressPolicy(configured)
    backend = egress._PinnedBackend(policy, _resolver({"other.example": [PUBLIC_IP]}), inner)
    with pytest.raises(EgressDenied) as exc:
        anyio.run(backend.connect_tcp, "other.example", 443)
    assert exc.value.code == "egress_not_allowlisted"
    offline = egress.EgressPolicy(configured.model_copy(update={"offline": True}))
    backend = egress._PinnedBackend(offline, _resolver({"allowed.example": [PUBLIC_IP]}), inner)
    with pytest.raises(EgressDenied) as exc:
        anyio.run(backend.connect_tcp, "allowed.example", 443)
    assert exc.value.code == "egress_offline"
    assert inner.dialed == []


# --- review r1 MAJOR-2: credentials do not follow a redirect to another origin -----------------

CREDENTIALS = {
    "Authorization": "Bearer dummy-not-secret-bearer",
    "X-Api-Key": "dummy-not-secret-api-key",
    "Cookie": "session=dummy-not-secret-cookie",
    "Proxy-Authorization": "Basic dummy-not-secret-proxy",
    "X-On-Behalf-Of": "dummy-not-secret-obo",
    "X-Upstream-Token": "dummy-not-secret-upstream",
    "X-Tenant-Secret": "dummy-not-secret-tenant",
}


def _credential_client(settings):
    return _client(
        settings,
        _resolver({"a.test": ["127.0.0.1"], "b.test": ["127.0.0.1"]}),
        allowed_internal_hosts=["a.test", "b.test"],
    )


def _echo(response):
    assert response.status_code == 200, response.status_code
    return json.loads(response.text)


def test_03b_2_redirect_other_host_drops_credentials(settings, server_port, caplog):
    headers = {**CREDENTIALS, "X-Request-ID": "req-1"}
    client = _credential_client(settings)
    with caplog.at_level(logging.INFO, logger="ffcore.egress"):
        response = anyio.run(
            lambda: _get(client, f"http://a.test:{server_port}/to-other-host", headers=headers)
        )
    seen = _echo(response)
    for name in CREDENTIALS:
        assert name.lower() not in seen
    assert seen["x-request-id"] == "req-1"
    events = [r for r in caplog.records if getattr(r, "event", None) == "redirect_cross_origin"]
    assert len(events) == 1
    assert events[0].target_origin == f"http://b.test:{server_port}"
    assert sorted(events[0].dropped_headers) == sorted(n.lower() for n in CREDENTIALS)
    assert "dummy-not-secret" not in caplog.text


def test_03b_2_redirect_other_port_drops_credentials(settings, servers):
    first, _ = servers
    client = _credential_client(settings)
    response = anyio.run(
        lambda: _get(client, f"http://a.test:{first}/to-other-port", headers=CREDENTIALS)
    )
    seen = _echo(response)
    assert "authorization" not in seen and "x-api-key" not in seen


def test_03b_2_redirect_post_303_drops_credentials(settings, server_port):
    client = _credential_client(settings)

    async def call():
        async with client:
            return await client.request(
                "POST",
                f"http://a.test:{server_port}/post-to-other-host",
                headers=CREDENTIALS,
                json={"x": 1},
            )

    seen = _echo(anyio.run(call))
    assert "authorization" not in seen and "x-api-key" not in seen


def test_03b_2_redirect_same_origin_keeps_credentials(settings, server_port):
    client = _credential_client(settings)
    response = anyio.run(
        lambda: _get(client, f"http://a.test:{server_port}/to-same", headers=CREDENTIALS)
    )
    seen = _echo(response)
    assert seen["authorization"] == CREDENTIALS["Authorization"]
    assert seen["x-api-key"] == CREDENTIALS["X-Api-Key"]


@pytest.mark.parametrize(
    ("current", "target", "dropped"),
    [
        ("https://a.example/", "http://a.example/x", True),  # TLS downgrade
        ("https://a.example/", "https://a.example:8443/x", True),
        ("https://a.example/", "https://b.example/x", True),
        ("https://a.example/", "https://a.example:443/x", False),
        ("http://a.example/", "http://A.EXAMPLE:80/x", False),
    ],
)
def test_03b_2_cross_origin_rule(current, target, dropped):
    kept, removed = egress.headers_for_redirect(
        httpx2.URL(current), httpx2.URL(target), {"Authorization": "x", "Accept": "a"}
    )
    assert ("Authorization" not in kept) is dropped
    assert removed == (["authorization"] if dropped else [])
    assert kept["Accept"] == "a"


# --- review r2 MAJOR-2: the client keeps no cookies --------------------------------------------


def _cookie_client(settings):
    return _client(
        settings,
        _resolver({"a.example.com": ["127.0.0.1"], "b.example.com": ["127.0.0.1"]}),
        allowed_internal_hosts=["a.example.com", "b.example.com"],
    )


@pytest.mark.parametrize("path", ["/set-cookie-other-port", "/set-cookie-other-host"])
def test_03b_2_set_cookie_not_carried_cross_origin(settings, server_port, path):
    client = _cookie_client(settings)
    response = anyio.run(lambda: _get(client, f"http://a.example.com:{server_port}{path}"))
    assert "cookie" not in _echo(response)


def test_03b_2_set_cookie_ignored_same_origin(settings, server_port):
    # Stateless: even on the same origin a response cookie is not stored and replayed.
    client = _cookie_client(settings)
    url = f"http://a.example.com:{server_port}/set-cookie-same-origin"
    response = anyio.run(lambda: _get(client, url))
    assert "cookie" not in _echo(response)


def test_03b_2_caller_cookie_same_origin_kept(settings, server_port):
    client = _cookie_client(settings)
    url = f"http://a.example.com:{server_port}/to-same"
    response = anyio.run(lambda: _get(client, url, headers={"Cookie": "caller=1"}))
    assert _echo(response)["cookie"] == "caller=1"


def test_03b_2_no_cookies_between_calls(settings, server_port):
    client = _cookie_client(settings)

    async def two_calls():
        async with client:
            await client.request(
                "GET", f"http://a.example.com:{server_port}/set-cookie-same-origin"
            )
            return await client.request("GET", f"http://a.example.com:{server_port}/echo")

    assert "cookie" not in _echo(anyio.run(two_calls))


def test_03b_2_client_cookie_jar_stores_nothing(settings):
    # Guard on httpx2 internals (pinned 2.16.0), together with the pool guard above.
    client = _client(settings, _resolver({}))
    jar = client._client.cookies.jar
    assert isinstance(jar, egress._NoCookieJar)
