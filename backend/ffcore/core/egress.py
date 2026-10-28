"""SafeOutboundClient: the only way FFCore calls an external HTTP endpoint (C5).

Webhooks, tool endpoints, MCP upstreams, channels and sources all go through it. Rules, in order:
only http/https; hosts in ALLOWED_INTERNAL_HOSTS (name or CIDR) are internal and may resolve to
private addresses; OFFLINE=true refuses every other host; otherwise the host must be in
EGRESS_ALLOWLIST (empty list: no external host). The address check runs at connect time, on the
address that is actually dialed, so a DNS answer cannot change between check and connect.
Redirects are followed here, one hop at a time, and every hop is checked again.
"""

import ipaddress
import math
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urljoin

import anyio
import httpcore2
import httpx2

from ffcore.core.config import Settings

Resolver = Callable[[str, int], Awaitable[list[str]]]
IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

MAX_REDIRECTS = 5
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}


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
        host = url.host.lower().rstrip(".")
        origin = _origin(url)
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
        literal = _parse_ip(host)
        addresses = [str(literal)] if literal is not None else await self._resolver(host, port)
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


class _PinnedTransport(httpx2.AsyncHTTPTransport):
    def __init__(self, backend: _PinnedBackend) -> None:
        # trust_env=False: an environment proxy would dial the proxy, not the checked address.
        super().__init__(trust_env=False)
        ssl_context = self._pool._ssl_context
        self._pool = httpcore2.AsyncConnectionPool(ssl_context=ssl_context, network_backend=backend)


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
        backend = _PinnedBackend(
            self._policy, resolver or system_resolver, inner_backend or httpcore2.AnyIOBackend()
        )
        self._transport = _PinnedTransport(backend)
        self._client = httpx2.AsyncClient(
            transport=self._transport,
            timeout=httpx2.Timeout(
                connect=timeout.connect, read=timeout.read, write=timeout.read, pool=timeout.connect
            ),
            follow_redirects=False,
            trust_env=False,
        )

    async def __aenter__(self) -> "SafeOutboundClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(self, method: str, url: str, **kwargs) -> httpx2.Response:
        target = httpx2.URL(url)
        try:
            with anyio.fail_after(self._timeout.total):
                return await self._follow(method, target, kwargs)
        except TimeoutError:
            raise EgressTimeoutError(
                "egress_timeout", _origin(target), f"exceeded {self._timeout.total} s"
            ) from None

    async def _follow(self, method: str, url: httpx2.URL, kwargs: dict) -> httpx2.Response:
        for _ in range(self._max_redirects + 1):
            self._policy.check_url(url)
            try:
                response = await self._client.request(method, url, **kwargs)
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
            url = httpx2.URL(urljoin(str(url), location))
            if response.status_code == 303 or (
                response.status_code in (301, 302) and method.upper() == "POST"
            ):
                method, kwargs = "GET", {k: v for k, v in kwargs.items() if k == "headers"}
        raise EgressDenied(
            "egress_too_many_redirects", _origin(url), f"more than {self._max_redirects}"
        )
