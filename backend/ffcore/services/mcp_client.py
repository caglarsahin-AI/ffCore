"""MCP client (05a): tool discovery and calls over streamable HTTP, official SDK.

Rules:
- One session per call or discovery, every auth type. The SDK takes caller headers from the
  httpx2 client it is given, shared by the whole session; one shared session sent two users'
  calls with one identity (U5, B-05a-0002). forward_user signs a fresh token for every call
  (C3), aud = [<tool_key>, obo_audience] (K-05a-0002 S3).
- Every connection goes through the egress policy (core/egress.policy_http_client, C5).
- The endpoint URL is scheme, host, port and path only, and a custom auth header never names
  a transport header (KARARLAR "05a review r1 kararları" items 3-4): checked at registration
  (services/mcp_tools) and again here, before any connection.
- A result longer than TOOL_RESULT_MAX_CHARS is cut and ends in "[truncated: N/M chars]"
  (C13); the call log says truncated=true.
- One structured log line per call: tool, action, status, latency_ms, truncated. Arguments
  and results are not logged (06a writes them to run_events).
- Failures are ToolCallError with a closed code; upstream text is never carried.
"""

import base64
import logging
import re
import time
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

import anyio
import httpx2
import mcp_types as types
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

from ffcore.core.auth import OBO_HEADER, service_authorization, sign_on_behalf_of
from ffcore.core.config import Settings
from ffcore.core.egress import (  # noqa: F401 - is_platform_target: 05b callers use this name
    EgressError,
    EgressTimeout,
    is_platform_target,
    policy_http_client,
)

log = logging.getLogger("ffcore.tools")

FORWARD_USER_TTL_S = 60
RUN_ID_HEADER = "X-Run-Id"
CONNECT_TIMEOUT_S = 5
# RFC 7230 token characters.
_HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]{1,64}")
# Set by the transport, or by FFCore itself (identity); Proxy-* is refused as a prefix.
RESERVED_HEADERS = frozenset(
    {
        "host",
        "content-length",
        "connection",
        "transfer-encoding",
        "upgrade",
        "te",
        "trailer",
        "keep-alive",
        "authorization",
        OBO_HEADER.lower(),
        RUN_ID_HEADER.lower(),
    }
)


def header_name_refusal(name: str) -> str | None:
    """header_name_not_allowed for a name that is no RFC token or names a reserved header."""
    lowered = name.lower()
    if (
        not _HEADER_NAME.fullmatch(name)
        or lowered in RESERVED_HEADERS
        or lowered.startswith("proxy-")
    ):
        return "header_name_not_allowed"
    return None


# 05b: a published MCP server's own endpoint on this backend (self-consumption, S3).
SELF_PATH = re.compile(r"/mcp/[a-z][a-z0-9-]{1,63}/")


def _origin(url: httpx2.URL) -> tuple[str, str, int | None]:
    default = {"http": 80, "https": 443}.get(url.scheme)
    return url.scheme, (url.host or "").lower().rstrip("."), url.port or default


def is_self_endpoint(url: str, auth_type: str, settings: Settings) -> bool:
    """`<INTERNAL_API_URL>/mcp/<key>/` with forward_user: the only way a tool reaches the backend
    (a published server consumed by the runtime, 05b S3)."""
    target = httpx2.URL(url)
    return (
        auth_type == "forward_user"
        and _origin(target) == _origin(httpx2.URL(settings.internal_api_url))
        and SELF_PATH.fullmatch(target.raw_path.decode("ascii", "replace")) is not None
    )


def call_settings(target: "ToolTarget", settings: Settings) -> Settings:
    """Settings for one connection: the self endpoint's host becomes internal for that call only,
    so the backend never has to be in ALLOWED_INTERNAL_HOSTS (FOLLOWUP-159)."""
    if not is_self_endpoint(target.endpoint_url, target.auth_type, settings):
        return settings
    host = httpx2.URL(settings.internal_api_url).host
    return settings.model_copy(
        update={"allowed_internal_hosts": [*settings.allowed_internal_hosts, host]}
    )


def endpoint_refusal(url: str) -> str | None:
    """endpoint_url_not_allowed for a URL with user info, a query or a fragment: credentials
    belong in the encrypted auth fields, never in the stored and returned URL."""
    if "?" in url or "#" in url or "@" in urlsplit(url).netloc:
        return "endpoint_url_not_allowed"
    return None


class ToolCallError(Exception):
    """A call or discovery that did not produce a result. `code` is one of: egress_* (refused
    by the outbound policy), endpoint_url_not_allowed, header_name_not_allowed,
    tool_unreachable, tool_timeout, tool_auth_failed, tool_protocol_error, tool_http_<status>."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Caller:
    """Who the call is for; forward_user puts this identity into the token."""

    user_id: str
    project_id: str


@dataclass(frozen=True)
class ToolTarget:
    key: str
    endpoint_url: str
    auth_type: str
    # Decrypted auth fields (services/mcp_tools); never logged.
    auth: dict[str, str]


@dataclass(frozen=True)
class DiscoveredAction:
    name: str
    description: str | None
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class CallResult:
    text: str
    truncated: bool
    total_chars: int
    is_error: bool
    latency_ms: int


class Guard(Protocol):
    """tool.pre / tool.post call points (C4); enforcement arrives with 05b/06a."""

    async def pre(self, action: str, arguments: dict[str, Any]) -> dict[str, Any]: ...

    async def post(self, action: str, text: str) -> str: ...


def static_auth_headers(kind: str, auth: dict[str, str]) -> dict[str, str]:
    """The headers of a fixed identity (none, bearer, header, basic); 05b's upstream calls use
    the same rule."""
    if kind == "bearer":
        return {"Authorization": f"Bearer {auth['token']}"}
    if kind == "header":
        return {auth["name"]: auth["value"]}
    if kind == "basic":
        pair = f"{auth['username']}:{auth['password']}".encode()
        return {"Authorization": "Basic " + base64.b64encode(pair).decode("ascii")}
    return {}


def _headers(target: ToolTarget, settings: Settings, caller: Caller, run_id: str | None):
    auth, kind = target.auth, target.auth_type
    headers: dict[str, str] = static_auth_headers(kind, auth)
    if kind == "forward_user":
        headers.update(service_authorization(settings))
        headers[OBO_HEADER] = sign_on_behalf_of(
            user_id=caller.user_id,
            project_id=caller.project_id,
            audience=[target.key, settings.obo_audience],
            settings=settings,
            ttl_s=FORWARD_USER_TTL_S,
        )
    if run_id:
        headers[RUN_ID_HEADER] = run_id
    return headers


def _leaves(exc: BaseException) -> Iterable[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        for inner in exc.exceptions:
            yield from _leaves(inner)
    else:
        yield exc
        if exc.__cause__ is not None:
            yield from _leaves(exc.__cause__)


def _status_code(status: int) -> str:
    return "tool_auth_failed" if status in (401, 403) else f"tool_http_{status}"


def _code(exc: BaseException, statuses: list[int]) -> str:
    """Closed list; anything unknown is tool_protocol_error (never its text). The SDK turns an
    HTTP error answer into a generic MCPError without its status, so the status recorded on
    this call's own client decides first."""
    if statuses:
        return _status_code(statuses[-1])
    leaves = list(_leaves(exc))
    for leaf in leaves:
        if isinstance(leaf, EgressError):
            return leaf.code
    for leaf in leaves:
        if isinstance(leaf, httpx2.HTTPStatusError):
            return _status_code(leaf.response.status_code)
        if isinstance(leaf, httpx2.TimeoutException):
            return "tool_timeout"
        if isinstance(leaf, httpx2.TransportError | OSError):
            return "tool_unreachable"
    return "tool_protocol_error"


@asynccontextmanager
async def _session(
    target: ToolTarget,
    settings: Settings,
    caller: Caller,
    run_id: str | None,
    timeout_s: float,
    statuses: list[int],
) -> AsyncIterator[ClientSession]:
    refusal = endpoint_refusal(target.endpoint_url)
    if refusal is None and target.auth_type == "header":
        refusal = header_name_refusal(target.auth["name"])
    if refusal is not None:
        raise ToolCallError(refusal)
    timeout = EgressTimeout(
        connect=min(CONNECT_TIMEOUT_S, timeout_s), read=timeout_s, total=timeout_s
    )
    headers = _headers(target, settings, caller, run_id)

    async def note(response: httpx2.Response) -> None:
        if response.status_code >= 400:
            statuses.append(response.status_code)

    policy_settings = call_settings(target, settings)
    async with policy_http_client(
        timeout=timeout, settings=policy_settings, headers=headers
    ) as http:
        http.event_hooks["response"] = [note]
        async with streamable_http_client(target.endpoint_url, http_client=http) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session


async def discover(
    target: ToolTarget, settings: Settings, *, caller: Caller, timeout_s: float | None = None
) -> list[DiscoveredAction]:
    """MCP tools/list, every page."""
    limit = timeout_s or settings.mcp_call_timeout_s
    actions: list[DiscoveredAction] = []
    statuses: list[int] = []
    try:
        with anyio.fail_after(limit):
            async with _session(target, settings, caller, None, limit, statuses) as session:
                cursor = None
                while True:
                    params = types.PaginatedRequestParams(cursor=cursor) if cursor else None
                    page = await session.list_tools(params=params)
                    actions += [
                        DiscoveredAction(t.name, t.description, dict(t.input_schema))
                        for t in page.tools
                    ]
                    cursor = page.next_cursor
                    if not cursor:
                        break
    except TimeoutError:
        raise ToolCallError("tool_timeout") from None
    except ToolCallError:
        raise
    except Exception as exc:  # noqa: BLE001 - mapped to a closed code
        raise ToolCallError(_code(exc, statuses)) from None
    return actions


def _text(result: types.CallToolResult) -> str:
    parts = []
    for block in result.content:
        if isinstance(block, types.TextContent):
            parts.append(block.text)
        else:
            # Said, not dropped: the model learns a non-text block was there.
            parts.append(f"[non-text content: {getattr(block, 'type', 'unknown')}]")
    return "\n".join(parts)


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return f"{text[:limit]}\n[truncated: {limit}/{len(text)} chars]", True


async def call(
    target: ToolTarget,
    action: str,
    arguments: dict[str, Any],
    settings: Settings,
    *,
    caller: Caller,
    timeout_s: float | None = None,
    run_id: str | None = None,
    guard: Guard | None = None,
) -> CallResult:
    limit = timeout_s or settings.mcp_call_timeout_s
    started = time.monotonic()
    status, truncated = "ok", False
    statuses: list[int] = []
    try:
        if guard is not None:
            arguments = await guard.pre(action, arguments)
        try:
            with anyio.fail_after(limit):
                async with _session(target, settings, caller, run_id, limit, statuses) as session:
                    result = await session.call_tool(action, arguments)
        except TimeoutError:
            raise ToolCallError("tool_timeout") from None
        except ToolCallError:
            raise
        except Exception as exc:  # noqa: BLE001 - mapped to a closed code (MCPError too)
            raise ToolCallError(_code(exc, statuses)) from None
        text = _text(result)
        if guard is not None:
            text = await guard.post(action, text)
        total = len(text)
        text, truncated = _truncate(text, settings.tool_result_max_chars)
        if result.is_error:
            status = "tool_error"
        latency = int((time.monotonic() - started) * 1000)
        return CallResult(text, truncated, total, bool(result.is_error), latency)
    except ToolCallError as exc:
        status = exc.code
        raise
    finally:
        latency = int((time.monotonic() - started) * 1000)
        log.info(
            "tool_call tool=%s action=%s status=%s latency_ms=%d truncated=%s",
            target.key,
            action,
            status,
            latency,
            truncated,
            extra={
                "tool": target.key,
                "action": action,
                "status": status,
                "latency_ms": latency,
                "truncated": truncated,
            },
        )
