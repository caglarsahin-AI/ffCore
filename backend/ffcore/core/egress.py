"""SafeOutboundClient: the only way FFCore calls an external HTTP endpoint (C5).

Webhooks, tool endpoints, MCP upstreams, channels and sources all go through it. Rules, in order:
only http/https; hosts in ALLOWED_INTERNAL_HOSTS (name or CIDR) are internal and may resolve to
private addresses; OFFLINE=true refuses every other host; otherwise the host must be in
EGRESS_ALLOWLIST (empty list: no external host). The address check runs at connect time, on the
address that is actually dialed, so a DNS answer cannot change between check and connect.
Redirects are followed here, one hop at a time, and every hop is checked again; a hop to another
origin (scheme, host, port) drops credential headers. Callers cannot change redirect handling,
transport, proxy, TLS verification or timeouts per request.
The client keeps no cookies: the only cookie sent is the caller's own Cookie header.
EGRESS_PROXY_URL set (FOLLOWUP-208, the egress profile): non-internal hosts go through the forward
proxy by name (CONNECT for https); the host rules above still run here, first, but the address
check moves to the proxy, which resolves and dials (deploy/egress/squid.conf `to_private`).
Internal hosts keep the direct pinned path; nothing falls back from one path to the other.
"""

import http.cookiejar
import ipaddress
import logging
import math
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import anyio
import httpcore2
import httpx2

from ffcore.core.config import Settings
from ffcore.core.errors import ApiError

Resolver = Callable[[str, int], Awaitable[list[str]]]
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

logger = logging.getLogger("ffcore.egress")

MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_DEFAULT_PORTS = {"http": 80, "https": 443}
# Dropped when a redirect leaves the origin; a host on the allowlist is not entitled to the
# first host's credentials.
_CREDENTIAL_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "x-api-key",
    "x-on-behalf-of",
}
_CREDENTIAL_SUFFIXES = ("-token", "-key", "-secret")


@dataclass(frozen=True)
class EgressTimeout:
    """Connect, read and whole-call limits in seconds; all mandatory, none may be None."""

    connect: float
    read: float
    total: float

    def __post_init__(self) -> None:
        for name in ("connect", "read", "total"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int | float):
                raise TypeError(f"egress timeout {name} must be a number of seconds")
            if not (value > 0 and math.isfinite(value)):
                raise ValueError(f"egress timeout {name} must be a positive finite number")
        if self.total < max(self.connect, self.read):
            raise ValueError("egress total timeout must be at least connect and read")


class EgressError(Exception):
    """Base class. Messages name only scheme and host: never path, query, headers or body."""

    def __init__(self, code: str, origin: str, detail: str) -> None:
        super().__init__(f"Outbound call to {origin} failed: {code} ({detail}).")
        self.code = code
        self.origin = origin


class EgressDenied(EgressError):
    pass


class EgressTimeoutError(EgressError):
    pass


class EgressRequestFailed(EgressError):
    pass


def _origin(url: httpx2.URL) -> str:
    port = f":{url.port}" if url.port else ""
    return f"{url.scheme}://{url.host}{port}"


def _origin_key(url: httpx2.URL) -> tuple[str, str, int | None]:
    port = url.port or _DEFAULT_PORTS.get(url.scheme)
    return url.scheme, (url.host or "").lower().rstrip("."), port


# The port the backend listens on in its container: loopback on it is the backend itself.
BACKEND_CONTAINER_PORT = 8000


def is_platform_target(url: str, settings: Settings) -> bool:
    """The backend itself (FOLLOWUP-159, -194): its INTERNAL_API_URL origin, the `backend`
    service name on any port, or loopback on the backend's container port. Never the target of
    a tool (05b), a provider URL (01) or a webhook (03c), whatever ALLOWED_INTERNAL_HOSTS says;
    the backend calls itself only by its own code (05b self endpoint, the /readyz probe).
    A URL that does not parse is not the platform; the caller's own URL check refuses it."""
    try:
        scheme, host, port = _origin_key(httpx2.URL(url))
    except httpx2.InvalidURL:
        return False
    if (scheme, host, port) == _origin_key(httpx2.URL(settings.internal_api_url)):
        return True
    if host == "backend":
        return True
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        loopback = False
    return loopback and port == BACKEND_CONTAINER_PORT


def refuse_platform_target(url: str | None, settings: Settings, what: str) -> None:
    """400 endpoint_is_platform when a URL being saved points at the backend (FOLLOWUP-194).
    The message names the field, never the URL (it may carry a credential)."""
    if url and is_platform_target(url, settings):
        raise ApiError(
            400,
            "invalid_request_error",
            "endpoint_is_platform",
            f"The {what} points at the FFCore backend itself; give the target service's address.",
        )


def _is_credential_header(name: str) -> bool:
    lowered = name.lower()
    return lowered in _CREDENTIAL_HEADERS or lowered.endswith(_CREDENTIAL_SUFFIXES)


def headers_for_redirect(
    current: httpx2.URL, target: httpx2.URL, headers: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Headers for the next hop. Same origin (scheme, host, port): unchanged. Another origin,
    including an https to http downgrade: credential headers are dropped. Returns the kept
    headers and the dropped header names (never values)."""
    if _origin_key(current) == _origin_key(target):
        return dict(headers), []
    kept = {name: value for name, value in headers.items() if not _is_credential_header(name)}
    dropped = sorted(name.lower() for name in headers if _is_credential_header(name))
    return kept, dropped


def _parse_ip(host: str) -> IPAddress | None:
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


class EgressPolicy:
    def __init__(self, settings: Settings) -> None:
        self.offline = settings.offline
        self.allowlist = [entry.rstrip(".") for entry in settings.egress_allowlist]
        self.internal_names: set[str] = set()
        self.internal_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for entry in settings.allowed_internal_hosts:
            try:
                self.internal_networks.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                self.internal_names.add(entry.rstrip("."))

    def _in_internal_network(self, ip: IPAddress) -> bool:
        return any(ip in network for network in self.internal_networks)

    def is_internal(self, host: str) -> bool:
        host = host.lower().rstrip(".")
        ip = _parse_ip(host)
        if ip is not None:
            return self._in_internal_network(ip)
        return host in self.internal_names

    def _allowlisted(self, host: str) -> bool:
        for entry in self.allowlist:
            if entry.startswith("*."):
                if host.endswith(entry[1:]) and len(host) > len(entry) - 1:
                    return True
            elif host == entry:
                return True
        return False

    def check_url(self, url: httpx2.URL) -> None:
        if url.scheme not in ("http", "https") or not url.host:
            raise EgressDenied("egress_invalid_url", f"{url.scheme}://", "only http and https")
        self.check_host(url.host, _origin(url))

    def check_host(self, host: str, origin: str) -> None:
        """OFFLINE and allowlist rules for a host name; runs per URL and again per connection."""
        host = host.lower().rstrip(".")
        if self.is_internal(host):
            return
        if self.offline:
            raise EgressDenied("egress_offline", origin, "OFFLINE=true refuses external hosts")
        if not self._allowlisted(host):
            raise EgressDenied("egress_not_allowlisted", origin, "host is not in EGRESS_ALLOWLIST")

    def check_address(self, host: str, address: str, port: int) -> None:
        ip = _parse_ip(address)
        origin = f"{host}:{port}"
        if ip is None:
            raise EgressDenied("egress_private_address", origin, "unparseable address")
        if self.is_internal(host):
            return
        if not ip.is_global:
            raise EgressDenied("egress_private_address", origin, "resolves to a non-public address")


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(str(info[4][0]) for info in infos))


async def _checked_addresses(
    policy: EgressPolicy, host: str, port: int, origin: str, resolver: Resolver
) -> list[str]:
    """Every address `host` resolves to, each one through the policy (DNS rebinding: not only
    the first). A name that does not resolve is a failed request, without the system text."""
    literal = _parse_ip(host)
    try:
        addresses = [str(literal)] if literal is not None else await resolver(host, port)
    except OSError:
        raise EgressRequestFailed("egress_dns_failed", origin, "name does not resolve") from None
    if not addresses:
        raise EgressDenied("egress_private_address", origin, "no address")
    for address in addresses:
        policy.check_address(host, address, port)
    return addresses


async def check_http_destination(
    settings: Settings, url: str, *, resolver: Resolver = system_resolver
) -> list[str]:
    """(08-tam-1a, FOLLOWUP-147) The rules SafeOutboundClient applies when it dials, checked
    before any connection, for callers that must refuse a destination up front (an external
    agent's base URL, a webhook): http/https only, a valid port, host name (OFFLINE, allowlist
    or internal), then every resolved address. Returns the checked addresses ([] for an external
    host when EGRESS_PROXY_URL is set: the proxy checks the addresses it dials). The connection
    itself still goes through SafeOutboundClient, which checks again at dial time."""
    try:
        target = httpx2.URL(url)
    except httpx2.InvalidURL:
        raise EgressDenied("egress_invalid_url", "", "the URL does not parse") from None
    policy = EgressPolicy(settings)
    policy.check_url(target)
    if target.port is not None and not 0 < target.port < 65536:
        # httpx2 parses any number as a port; the dial would fail later and less clearly.
        raise EgressDenied("egress_invalid_port", _origin(target), "port out of range")
    port = target.port or (443 if target.scheme == "https" else 80)
    if settings.egress_proxy_url and not policy.is_internal(target.host):
        # FOLLOWUP-208: through the proxy the backend does not resolve external names (the
        # egress network has no outside DNS); the proxy resolves and refuses private addresses.
        return []
    return await _checked_addresses(policy, target.host, port, _origin(target), resolver)


SMTP_PORTS = (25, 465, 587)


async def check_destination(
    settings: Settings, host: str, port: int, *, resolver: Resolver = system_resolver
) -> str:
    """(03c, additive) The same rules for a non-HTTP destination (SMTP): host name (OFFLINE,
    allowlist), then every resolved address (no private address unless internal). Returns the
    checked address to dial, so the connection never resolves the name a second time (DNS
    rebinding); TLS keeps `host` as server_hostname. Only the SMTP ports are accepted."""
    origin = f"{host}:{port}"
    if port not in SMTP_PORTS:
        raise EgressDenied("egress_port_not_allowed", origin, "only SMTP ports 25, 465, 587")
    policy = EgressPolicy(settings)
    policy.check_host(host, origin)
    addresses = await _checked_addresses(policy, host, port, origin, resolver)
    return addresses[0]


class _PinnedBackend(httpcore2.AsyncNetworkBackend):
    """Resolves once per connection, checks every answer, dials the checked address."""

    def __init__(
        self, policy: EgressPolicy, resolver: Resolver, inner: httpcore2.AsyncNetworkBackend
    ) -> None:
        self._policy = policy
        self._resolver = resolver
        self._inner = inner

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ) -> httpcore2.AsyncNetworkStream:
        # Defence in depth: the same host rules as the URL check, at the layer that dials.
        self._policy.check_host(host, f"{host}:{port}")
        literal = _parse_ip(host)
        try:
            addresses = [str(literal)] if literal is not None else await self._resolver(host, port)
        except OSError:
            # Name lookup failed (socket.gaierror and friends): a failed call like any other
            # connection failure, not an unhandled error. The system text is not carried along.
            raise EgressRequestFailed(
                "egress_dns_failed", f"{host}:{port}", "name does not resolve"
            ) from None
        if not addresses:
            raise EgressDenied("egress_private_address", f"{host}:{port}", "no address")
        for address in addresses:
            self._policy.check_address(host, address, port)
        # TLS still uses the host name for SNI and certificate checks (httpcore start_tls).
        return await self._inner.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise EgressDenied("egress_invalid_url", "unix://", "unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _NoCookieJar(http.cookiejar.CookieJar):
    """Stores nothing: the client is stateless. A response's Set-Cookie is ignored, so the only
    cookie ever sent is the caller's own Cookie header, which follows the origin rule."""

    def set_cookie(self, cookie) -> None:
        return None

    def extract_cookies(self, response, request) -> None:
        return None

    def set_cookie_if_ok(self, cookie, request) -> None:
        return None


class _PinnedTransport(httpx2.AsyncHTTPTransport):
    def __init__(self, backend: _PinnedBackend) -> None:
        # trust_env=False: an environment proxy would dial the proxy, not the checked address.
        super().__init__(trust_env=False)
        ssl_context = self._pool._ssl_context
        self._pool = httpcore2.AsyncConnectionPool(ssl_context=ssl_context, network_backend=backend)


class _ProxyOnlyBackend(httpcore2.AsyncNetworkBackend):
    """(FOLLOWUP-208) The network layer under the proxy transport: it dials the configured
    proxy origin and nothing else, whatever the connection pool asks for."""

    def __init__(
        self, host: str, port: int, resolver: Resolver, inner: httpcore2.AsyncNetworkBackend
    ) -> None:
        self._host = host.lower().strip("[]")
        self._port = port
        self._resolver = resolver
        self._inner = inner

    async def connect_tcp(
        self, host, port, timeout=None, local_address=None, socket_options=None
    ) -> httpcore2.AsyncNetworkStream:
        name = host.decode() if isinstance(host, bytes) else str(host)
        if (name.lower().strip("[]"), port) != (self._host, self._port):
            raise EgressDenied(
                "egress_proxy_only",
                f"{name}:{port}",
                "the proxy transport dials EGRESS_PROXY_URL only",
            )
        literal = _parse_ip(self._host)
        try:
            addresses = [str(literal)] if literal is not None else await self._resolver(name, port)
        except OSError:
            raise EgressRequestFailed(
                "egress_proxy_unreachable", f"{name}:{port}", "proxy name does not resolve"
            ) from None
        if not addresses:
            raise EgressRequestFailed("egress_proxy_unreachable", f"{name}:{port}", "no address")
        return await self._inner.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise EgressDenied("egress_invalid_url", "unix://", "unix sockets are not allowed")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


class _ProxyTransport(httpx2.AsyncHTTPTransport):
    """https targets: a CONNECT tunnel by host name (TLS, SNI and the certificate check stay
    here, end to end); http targets: an absolute-form request. The proxy resolves the name and
    applies the address rules (deploy/egress/squid.conf `to_private`)."""

    def __init__(self, proxy_url: str, backend: _ProxyOnlyBackend) -> None:
        super().__init__(trust_env=False)
        ssl_context = self._pool._ssl_context
        self._pool = httpcore2.AsyncHTTPProxy(
            proxy_url=proxy_url, ssl_context=ssl_context, network_backend=backend
        )


class _EgressTransport(httpx2.AsyncBaseTransport):
    """Chooses the path per request: internal hosts (ALLOWED_INTERNAL_HOSTS) and every host when
    EGRESS_PROXY_URL is empty take the pinned direct path; other hosts take the proxy. There is
    no fallback from one path to the other. A refusal by the proxy is an EgressDenied, not a
    response the caller could mistake for the target's own 403."""

    def __init__(
        self,
        policy: EgressPolicy,
        settings: Settings,
        resolver: Resolver,
        inner: httpcore2.AsyncNetworkBackend,
    ) -> None:
        self._policy = policy
        self._direct = _PinnedTransport(_PinnedBackend(policy, resolver, inner))
        self._proxy: _ProxyTransport | None = None
        if settings.egress_proxy_url:
            proxy = httpx2.URL(settings.egress_proxy_url)
            self._proxy = _ProxyTransport(
                settings.egress_proxy_url,
                _ProxyOnlyBackend(proxy.host, proxy.port or 80, resolver, inner),
            )

    def _via_proxy(self, host: str) -> bool:
        return self._proxy is not None and not self._policy.is_internal(host)

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        if not self._via_proxy(request.url.host):
            return await self._direct.handle_async_request(request)
        proxy = self._proxy
        if proxy is None:  # _via_proxy said so; kept explicit for the type checker
            raise EgressDenied("egress_proxy_only", _origin(request.url), "no proxy configured")
        origin = _origin(request.url)
        # Defence in depth: the host rules again, at the layer that picks the proxy.
        self._policy.check_host(request.url.host, origin)
        try:
            response = await proxy.handle_async_request(request)
        except httpx2.ProxyError as exc:
            # CONNECT refused by the proxy (httpcore raises with the proxy's status line).
            raise EgressDenied("egress_proxy_denied", origin, str(exc) or "proxy refused") from None
        squid_error = response.headers.get("x-squid-error")
        if squid_error is not None:
            await response.aclose()
            raise EgressDenied("egress_proxy_denied", origin, squid_error)
        return response

    async def aclose(self) -> None:
        await self._direct.aclose()
        if self._proxy is not None:
            await self._proxy.aclose()


def policy_http_client(
    *,
    timeout: EgressTimeout,
    settings: Settings,
    headers: Mapping[str, str] | None = None,
    resolver: Resolver | None = None,
    inner_backend: httpcore2.AsyncNetworkBackend | None = None,
) -> httpx2.AsyncClient:
    """An httpx2.AsyncClient for a library that sends its own requests (the MCP SDK, 05a,
    K-05a-0002 S2), on the same pinned transport as SafeOutboundClient: the host rules and the
    address check run at connect time for every connection the library opens. Redirects are not
    followed by the client, no cookies are kept, no environment proxy is used. The client has
    connect and read limits only; the caller bounds the whole call (anyio.fail_after)."""
    if not isinstance(timeout, EgressTimeout):
        raise TypeError("policy_http_client needs an EgressTimeout; calls without one are refused")
    transport = _EgressTransport(
        EgressPolicy(settings),
        settings,
        resolver or system_resolver,
        inner_backend or httpcore2.AnyIOBackend(),
    )
    return httpx2.AsyncClient(
        transport=transport,
        headers=dict(headers or {}),
        timeout=httpx2.Timeout(
            connect=timeout.connect, read=timeout.read, write=timeout.read, pool=timeout.connect
        ),
        follow_redirects=False,
        trust_env=False,
        cookies=_NoCookieJar(),
    )


class SafeOutboundClient:
    """Async HTTP client with a mandatory timeout and the egress policy above."""

    def __init__(
        self,
        *,
        timeout: EgressTimeout,
        settings: Settings,
        resolver: Resolver | None = None,
        inner_backend: httpcore2.AsyncNetworkBackend | None = None,
        max_redirects: int = MAX_REDIRECTS,
    ) -> None:
        if not isinstance(timeout, EgressTimeout):
            raise TypeError(
                "SafeOutboundClient needs an EgressTimeout; calls without one are refused"
            )
        self._timeout = timeout
        self._policy = EgressPolicy(settings)
        self._max_redirects = max_redirects
        self._transport = _EgressTransport(
            self._policy,
            settings,
            resolver or system_resolver,
            inner_backend or httpcore2.AnyIOBackend(),
        )
        self._client = httpx2.AsyncClient(
            transport=self._transport,
            timeout=httpx2.Timeout(
                connect=timeout.connect, read=timeout.read, write=timeout.read, pool=timeout.connect
            ),
            follow_redirects=False,
            trust_env=False,
            # A raw CookieJar is used as is; httpx2.Cookies(...) would copy it into a normal jar.
            cookies=_NoCookieJar(),
        )

    async def __aenter__(self) -> "SafeOutboundClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | str | None = None,
        json: Any = None,
    ) -> httpx2.Response:
        """Send one request. Deliberately no **kwargs: redirect handling, transport, proxy, TLS
        verification and timeouts are fixed by the client and cannot be changed per call."""
        target = httpx2.URL(url)
        body = {"content": content, "json": json}
        try:
            with anyio.fail_after(self._timeout.total):
                return await self._follow(method, target, dict(headers or {}), params, body)
        except TimeoutError:
            raise EgressTimeoutError(
                "egress_timeout", _origin(target), f"exceeded {self._timeout.total} s"
            ) from None

    @asynccontextmanager
    async def stream(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, str] | None = None,
        content: bytes | str | None = None,
        json: Any = None,
    ) -> AsyncIterator[httpx2.Response]:
        """Like request(), but the caller reads the body as it arrives (SSE). Same policy, same
        redirect rules (one code path). The total timeout covers reaching the final response;
        afterwards the read timeout applies to each chunk, and reading raises httpx2 errors
        (TimeoutException, HTTPError) that the caller maps. The response is closed on exit."""
        target = httpx2.URL(url)
        body = {"content": content, "json": json}
        try:
            with anyio.fail_after(self._timeout.total):
                response = await self._follow(
                    method, target, dict(headers or {}), params, body, stream=True
                )
        except TimeoutError:
            raise EgressTimeoutError(
                "egress_timeout", _origin(target), f"exceeded {self._timeout.total} s"
            ) from None
        try:
            yield response
        finally:
            await response.aclose()

    async def _follow(
        self,
        method: str,
        url: httpx2.URL,
        headers: dict[str, str],
        params: Mapping[str, str] | None,
        body: dict,
        stream: bool = False,
    ) -> httpx2.Response:
        for _ in range(self._max_redirects + 1):
            self._policy.check_url(url)
            try:
                request = self._client.build_request(
                    method, url, headers=headers, params=params, **body
                )
                response = await self._client.send(request, stream=stream)
            except httpx2.TimeoutException:
                raise EgressTimeoutError(
                    "egress_timeout", _origin(url), "connect or read"
                ) from None
            except httpx2.HTTPError as exc:
                raise EgressRequestFailed(
                    "egress_request_failed", _origin(url), type(exc).__name__
                ) from None
            location = response.headers.get("location")
            if response.status_code not in _REDIRECT_STATUSES or not location:
                return response
            if stream:
                await response.aclose()
            target = httpx2.URL(urljoin(str(url), location))
            headers, dropped = headers_for_redirect(url, target, headers)
            if _origin_key(target) != _origin_key(url):
                logger.info(
                    "redirect_cross_origin",
                    extra={
                        "event": "redirect_cross_origin",
                        "target_origin": _origin(target),
                        "dropped_headers": dropped,
                    },
                )
            url, params = target, None
            if response.status_code == 303 or (
                response.status_code in (301, 302) and method.upper() == "POST"
            ):
                method, body = "GET", {"content": None, "json": None}
        raise EgressDenied(
            "egress_too_many_redirects", _origin(url), f"more than {self._max_redirects}"
        )
