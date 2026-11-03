"""08-tam-1a, FOLLOWUP-147: `core/egress.check_http_destination(settings, url)`, the egress rules
for an HTTP destination checked before any connection (name, every resolved address, scheme and
port), the same rules SafeOutboundClient applies when it dials. 06b-2's `check_base_url` uses it;
its own tests (test_06b2_external) stay as they are."""

import socket

import anyio
import pytest

from ffcore.core.egress import EgressDenied, EgressRequestFailed, check_http_destination

PUBLIC_IP = "93.184.216.34"


def _resolver(table):
    calls = []

    async def resolve(host, port):
        calls.append((host, port))
        return list(table[host])

    resolve.calls = calls
    return resolve


def _check(settings, url, resolver=None, **overrides):
    configured = settings.model_copy(update=overrides)
    return anyio.run(
        lambda: check_http_destination(configured, url, resolver=resolver or _resolver({}))
    )


def _denied(settings, url, code, resolver=None, **overrides):
    with pytest.raises(EgressDenied) as exc:
        _check(settings, url, resolver, **overrides)
    assert exc.value.code == code
    return exc.value


def test_08t_14_public_allowlisted_host_returns_checked_addresses(settings):
    resolver = _resolver({"api.example.com": [PUBLIC_IP, "93.184.216.35"]})
    addresses = _check(
        settings, "https://api.example.com/v1", resolver, egress_allowlist=["api.example.com"]
    )
    assert addresses == [PUBLIC_IP, "93.184.216.35"]
    assert resolver.calls == [("api.example.com", 443)]


def test_08t_14_default_ports_by_scheme(settings):
    resolver = _resolver({"a.example.com": [PUBLIC_IP]})
    _check(settings, "http://a.example.com/x", resolver, egress_allowlist=["a.example.com"])
    _check(settings, "https://a.example.com:8443/x", resolver, egress_allowlist=["a.example.com"])
    assert resolver.calls == [("a.example.com", 80), ("a.example.com", 8443)]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://a.example.com/", "ftp://a/x"])
def test_08t_14_scheme_refused(settings, url):
    _denied(settings, url, "egress_invalid_url", egress_allowlist=["a.example.com", "a"])


@pytest.mark.parametrize("url", ["http://", "not a url", "http://[::1"])
def test_08t_14_invalid_url_refused(settings, url):
    _denied(settings, url, "egress_invalid_url")


def test_08t_14_invalid_port_refused(settings):
    _denied(
        settings,
        "http://a.example.com:99999/x",
        "egress_invalid_port",
        egress_allowlist=["a.example.com"],
    )


def test_08t_14_not_allowlisted_before_lookup(settings):
    resolver = _resolver({})
    _denied(settings, "https://evil.example/x", "egress_not_allowlisted", resolver)
    assert resolver.calls == []


def test_08t_14_offline_refuses_external(settings):
    _denied(
        settings,
        "https://api.example.com/x",
        "egress_offline",
        offline=True,
        egress_allowlist=["api.example.com"],
    )


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "::1"]
)
def test_08t_14_private_address_refused(settings, address):
    resolver = _resolver({"api.example.com": [address]})
    _denied(
        settings,
        "https://api.example.com/x",
        "egress_private_address",
        resolver,
        egress_allowlist=["api.example.com"],
    )


def test_08t_14_one_private_address_among_public_refused(settings):
    # DNS rebinding: every resolved address is checked, not only the first.
    resolver = _resolver({"api.example.com": [PUBLIC_IP, "10.0.0.5"]})
    _denied(
        settings,
        "https://api.example.com/x",
        "egress_private_address",
        resolver,
        egress_allowlist=["api.example.com"],
    )


@pytest.mark.parametrize("url", ["http://127.0.0.1/x", "http://[::1]:8080/x"])
def test_08t_14_private_literal_refused(settings, url):
    _denied(settings, url, "egress_private_address", egress_allowlist=["127.0.0.1", "::1"])


def test_08t_14_internal_host_allowed(settings):
    resolver = _resolver({"svc.internal": ["10.0.0.5"]})
    assert _check(
        settings, "http://svc.internal:8000/x", resolver, allowed_internal_hosts=["svc.internal"]
    ) == ["10.0.0.5"]


def test_08t_14_unresolvable_is_request_failed(settings):
    async def nxdomain(host, port):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    with pytest.raises(EgressRequestFailed) as exc:
        _check(settings, "http://svc.internal/x", nxdomain, allowed_internal_hosts=["svc.internal"])
    assert exc.value.code == "egress_dns_failed"
    assert exc.value.__cause__ is None


def test_08t_14_no_address_refused(settings):
    resolver = _resolver({"api.example.com": []})
    _denied(
        settings,
        "https://api.example.com/x",
        "egress_private_address",
        resolver,
        egress_allowlist=["api.example.com"],
    )
