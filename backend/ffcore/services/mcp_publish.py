"""Published MCP servers (05b): `/mcp/{key}/`, the backend's second external surface (PLAN 5
R1.2, C14).

Every request, in this order, before the MCP SDK sees it:
1. `resolve_actor` (C2): an API key, a user an `impersonate` key acts for, or the runtime (the
   service account acting for a user through X-On-Behalf-Of). A console session or a bare service
   token is 401 mcp_credentials_required.
2. The server by key: unknown, deleted, not active, or in another project than the caller is one
   404 (KARARLAR "Proje dışı erişim 404").
3. Access: `token` admits keys with the `tools_invoke` scope (403 scope_missing) and the runtime;
   `internal` admits only the runtime (a key is 403 mcp_server_internal).
The SDK's Host header check is off (S4): there is no ambient credential (cookie) on this path,
every request carries a key or the service token, and the public Host behind a reverse proxy is
not known in advance. The order above is what protects the endpoint.

Each tools/call: request quota (S2: the request windows of the project's quotas, as the facade;
no token or USD counting, there is no model) -> guardrail `tool.pre` on the arguments -> the
upstream (OpenAPI over SafeOutboundClient to the registered origin only, redirects refused; or
the remote MCP server through the 05a client) -> truncation (C13) -> guardrail `tool.post` ->
answer. The server's guardrail_mode only tightens its policy (S1). Every call leaves one
mcp_server_calls row and one audit row (`mcp_server_call`), without arguments or results.
Failures reach the caller as an error result with a closed code; upstream text never does.
"""

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, replace

import httpx2
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import JSONResponse

from ffcore.core import db
from ffcore.core.audit import AuditEntry, request_context, write_event_detached
from ffcore.core.auth import Actor, resolve_actor
from ffcore.core.config import Settings, get_settings
from ffcore.core.egress import (
    EgressDenied,
    EgressError,
    EgressPolicy,
    EgressTimeout,
    SafeOutboundClient,
)
from ffcore.core.errors import ApiError, error_body
from ffcore.guardrails import engine
from ffcore.guardrails.engine import rule_mode
from ffcore.guardrails.recognizers.ner import local_ner
from ffcore.guardrails.schemas import ResolvedPolicy
from ffcore.guardrails.service import record_events, resolve_policy
from ffcore.models.mcp_servers import McpServer, McpServerCall
from ffcore.services import mcp_client, mcp_openapi
from ffcore.services.external_config import _reserved
from ffcore.services.quota import (
    REQUEST_WINDOWS,
    QuotaUnavailable,
    Subject,
    engine_for,
    load_rules,
    redis_client,
)

log = logging.getLogger("ffcore.mcp_publish")

MODE_RANK = {"off": 0, "monitor": 1, "enforce": 2}
CONNECT_TIMEOUT_S = 5
_KEY_PATH = re.compile(r"^/([a-z][a-z0-9-]{1,63})/?$")


# --- S1: the server's guardrail mode only tightens its policy ---


def _stricter(a: str, b: str) -> str:
    return a if MODE_RANK[a] >= MODE_RANK[b] else b


def effective_policy(policy: ResolvedPolicy, server_mode: str) -> ResolvedPolicy:
    """Each rule runs in max(server mode, its own mode); the policy mode likewise. `off` on the
    server adds nothing: the policy runs as it is (a server cannot loosen it)."""
    if server_mode not in MODE_RANK:
        raise ValueError(f"unknown guardrail mode {server_mode!r}")
    spec = policy.spec
    rules = []
    for rule in spec.rules:
        mode = _stricter(rule_mode(spec, rule), server_mode)
        rules.append(rule.model_copy(update={"mode": None if mode == "off" else mode}))
    tightened = spec.model_copy(update={"mode": _stricter(spec.mode, server_mode), "rules": rules})
    return replace(policy, spec=tightened)


# --- upstream URL (registration and every call) ---


def _refused(status: int, code: str, message: str) -> ApiError:
    error_type = "invalid_request_error"
    return ApiError(status, error_type, code, message)


def check_upstream_url(url: str, settings: Settings) -> None:
    """Scheme, host, port and path only; never a platform service (RESERVED_HOSTS, the backend
    itself, 06b-2 rule); the egress policy (allowlist, OFFLINE, internal hosts)."""
    if mcp_client.endpoint_refusal(url) is not None:
        raise _refused(
            400,
            "endpoint_url_not_allowed",
            "The upstream URL takes scheme, host, port and path only; put credentials in auth.",
        )
    try:
        target = httpx2.URL(url)
    except httpx2.InvalidURL:
        raise _refused(400, "egress_invalid_url", "The upstream URL does not parse.") from None
    host = (target.host or "").lower().rstrip(".")
    port = target.port or {"http": 80, "https": 443}.get(target.scheme, 0)
    if host and (mcp_client.is_platform_target(url, settings) or _reserved(host, port, settings)):
        raise _refused(
            422, "upstream_url_refused", "A platform service cannot be a published upstream."
        )
    try:
        EgressPolicy(settings).check_url(target)
    except EgressDenied as exc:
        raise _refused(400, exc.code, f"Refused by the outbound policy ({exc.code}).") from None


# --- the published catalog ---


def published(operations: list[dict], exposed: list[str]) -> dict[str, dict]:
    """Exposed name (alias or operation name) -> operation, for exposable selected operations."""
    chosen = set(exposed)
    return {
        (op.get("alias") or op["name"]): op
        for op in operations
        if op["name"] in chosen and op.get("exposable")
    }


@dataclass(frozen=True)
class Snapshot:
    """What one request needs of the server row (read once, detached from the session)."""

    id: str
    project_id: str
    key: str
    source_kind: str
    upstream_base_url: str
    upstream_auth_type: str
    upstream_auth: dict[str, str]
    operations: list[dict]
    exposed: list[str]
    guardrail_mode: str
    guardrail_policy_key: str


@dataclass(frozen=True)
class Caller:
    actor_type: str
    actor_id: str
    project_id: str
    user_id: str | None
    key_id: str | None  # the API key (also when it acts for a user)
    via_key_id: str | None
    run_id: str | None
    request_id: str
    ip: str | None


@dataclass
class Outcome:
    text: str
    is_error: bool
    status: str = "ok"
    code: str | None = None
    guardrail_action: str | None = None


def _error(exc: ApiError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        error_body(exc.error_type, exc.code, exc.message), exc.status_code, headers=headers
    )


def _not_found() -> ApiError:
    return ApiError(404, "not_found_error", "mcp_server_not_found", "MCP server not found.")


def _credentials_required() -> ApiError:
    return ApiError(
        401,
        "authentication_error",
        "mcp_credentials_required",
        "A published MCP server takes an API key (tools_invoke) or the platform runtime.",
    )


async def _key_scopes(key_id: str) -> frozenset[str]:
    from ffcore.services.facade_identity import _key_scopes as scopes

    return await scopes(key_id)


async def admit(request: Request, actor: Actor, key: str) -> tuple[Snapshot, Caller]:
    """Who may call which server (module docstring 1-3)."""
    from ffcore.services.mcp_tools import decrypt_auth

    if actor.actor_type == "api_key":
        key_id, user_id, scopes = actor.actor_id, None, actor.scopes
    elif actor.actor_type == "user" and actor.via_key_id is not None:
        key_id, user_id = actor.via_key_id, actor.actor_id
        scopes = await _key_scopes(actor.via_key_id)
    elif actor.actor_type == "user" and actor.via_service:
        key_id, user_id, scopes = None, actor.actor_id, frozenset()
    else:
        raise _credentials_required()
    async with db.session_scope() as session:
        row = await session.scalar(
            select(McpServer).where(McpServer.key == key, McpServer.deleted_at.is_(None))
        )
        if row is None or row.status != "active" or str(row.project_id) != actor.project_id:
            raise _not_found()
        settings = request.state.ffcore_settings
        snapshot = Snapshot(
            id=str(row.id),
            project_id=str(row.project_id),
            key=row.key,
            source_kind=row.source_kind,
            upstream_base_url=row.upstream_base_url,
            upstream_auth_type=row.upstream_auth_type,
            upstream_auth=decrypt_auth(row.upstream_auth_encrypted, settings),
            operations=list(row.operations or []),
            exposed=list(row.exposed_operations or []),
            guardrail_mode=row.guardrail_mode,
            guardrail_policy_key=row.guardrail_policy_key,
        )
        access = row.access
    if key_id is not None:
        if access == "internal":
            raise ApiError(
                403,
                "permission_error",
                "mcp_server_internal",
                "This MCP server is for the platform runtime only.",
            )
        if "tools_invoke" not in scopes:
            raise ApiError(
                403,
                "permission_error",
                "scope_missing",
                "The API key lacks the 'tools_invoke' scope.",
            )
    request_id, ip = request_context(request)
    run_id = request.headers.get(mcp_client.RUN_ID_HEADER)
    try:
        run_id = str(uuid.UUID(run_id)) if run_id and key_id is None else None
    except ValueError:
        run_id = None
    caller = Caller(
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        project_id=actor.project_id or "",
        user_id=user_id,
        key_id=key_id,
        via_key_id=actor.via_key_id,
        run_id=run_id,
        request_id=request_id,
        ip=ip,
    )
    return snapshot, caller


# --- one call ---


async def _quota(settings: Settings, session, caller: Caller) -> tuple[str, str] | None:
    """(status, code) when the request windows refuse the call; None lets it go on (S2)."""
    rules = [
        replace(rule, tokens={}, budget={})
        for rule in await load_rules(session, caller.project_id)
        if any(rule.windows.get(w) is not None for w in REQUEST_WINDOWS)
    ]
    if not rules:
        return None
    try:
        redis = redis_client(settings)
    except QuotaUnavailable:
        return "denied", "quota_unavailable"
    try:
        subject = Subject(caller.project_id, user_id=caller.user_id, api_key_id=caller.key_id)
        decision = await engine_for(settings, redis).check(rules, subject)
    except QuotaUnavailable:
        return "denied", "quota_unavailable"
    finally:
        await redis.aclose()
    return ("denied", decision.code or "quota_exceeded") if decision.blocked else None


# The strongest guardrail action of a call, kept on its mcp_server_calls row.
_ACTION_RANK = {"allow": 0, "warn": 1, "mask": 2, "block": 3}


class _Guard:
    def __init__(self, session, policy: ResolvedPolicy, snapshot: Snapshot, caller: Caller):
        self.session, self.policy, self.snapshot, self.caller = session, policy, snapshot, caller
        self.strongest: str | None = None

    async def check(self, stage: str, text: str, operation: str) -> engine.Decision:
        ctx = engine.EvalContext(
            run_id=self.caller.run_id,
            project_id=self.snapshot.project_id,
            source="api",
            tool=f"{self.snapshot.key}.{operation}",
            ner=local_ner(),
        )
        decision = await engine.evaluate(text, stage, self.policy, ctx=ctx)
        if decision.events:
            events = [replace(e, run_id=self.caller.run_id) for e in decision.events]
            record_events(self.session, self.snapshot.project_id, events, decision.reference_id)
            await self.session.commit()
            for event in decision.events:
                rank = _ACTION_RANK.get(event.action_taken, 0)
                if self.strongest is None or rank > _ACTION_RANK.get(self.strongest, 0):
                    self.strongest = event.action_taken
        return decision


async def _openapi_call(snapshot: Snapshot, op: dict, arguments: dict, settings: Settings) -> str:
    """The upstream answer as text; any failure is mcp_client.ToolCallError with a code."""
    try:
        request = mcp_openapi.build_request(op, arguments)
    except mcp_openapi.ArgumentsError as exc:
        raise mcp_client.ToolCallError(exc.code) from None
    url = snapshot.upstream_base_url.rstrip("/") + request.path
    check_upstream_url(url, settings)  # the base URL passed at registration; checked again
    limit = settings.mcp_call_timeout_s
    timeout = EgressTimeout(connect=min(CONNECT_TIMEOUT_S, limit), read=limit, total=limit)
    headers = mcp_client.static_auth_headers(snapshot.upstream_auth_type, snapshot.upstream_auth)
    cap = settings.mcp_upstream_max_bytes
    try:
        async with SafeOutboundClient(timeout=timeout, settings=settings, max_redirects=0) as http:
            async with http.stream(
                request.method,
                url,
                headers=headers,
                params=request.params or None,
                json=request.json,
            ) as response:
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > cap:
                        raise mcp_client.ToolCallError("upstream_response_too_large")
                status = response.status_code
    except EgressError as exc:
        raise mcp_client.ToolCallError(exc.code) from None
    except httpx2.TimeoutException:
        raise mcp_client.ToolCallError("upstream_timeout") from None
    except httpx2.HTTPError:
        raise mcp_client.ToolCallError("upstream_unreachable") from None
    if status >= 400:
        raise mcp_client.ToolCallError(f"upstream_http_{status}")
    return bytes(body).decode("utf-8", errors="replace")


async def _remote_call(
    snapshot: Snapshot, op: dict, arguments: dict, settings: Settings, caller: Caller
) -> tuple[str, bool]:
    target = mcp_client.ToolTarget(
        key=snapshot.key,
        endpoint_url=snapshot.upstream_base_url,
        auth_type=snapshot.upstream_auth_type,
        auth=snapshot.upstream_auth,
    )
    who = mcp_client.Caller(user_id=caller.user_id or caller.actor_id, project_id=caller.project_id)
    result = await mcp_client.call(target, op["name"], arguments, settings, caller=who)
    return result.text, result.is_error


async def invoke(
    snapshot: Snapshot, caller: Caller, name: str, arguments: dict, settings: Settings
) -> Outcome:
    started = time.monotonic()
    ops = published(snapshot.operations, snapshot.exposed)
    op = ops.get(name)
    operation = op["name"] if op is not None else name
    outcome = Outcome("", True, "error", "unknown_tool" if op is None else "internal_error")
    try:
        if op is not None:
            outcome = await _guarded(snapshot, caller, op, arguments, settings)
    finally:
        await _record(
            snapshot, caller, operation, outcome, int((time.monotonic() - started) * 1000)
        )
    if outcome.is_error and not outcome.text:
        outcome.text = f"error: {outcome.code}"
    return outcome


async def _guarded(
    snapshot: Snapshot, caller: Caller, op: dict, arguments: dict, settings: Settings
) -> Outcome:
    async with db.session_scope() as session:
        refused = await _quota(settings, session, caller)
        if refused is not None:
            return Outcome("", True, refused[0], refused[1])
        policy = effective_policy(
            await resolve_policy(session, snapshot.project_id, snapshot.guardrail_policy_key),
            snapshot.guardrail_mode,
        )
        guard = _Guard(session, policy, snapshot, caller)
        pre = await guard.check("tool.pre", json.dumps(arguments, ensure_ascii=False), op["name"])
        if pre.action == "block":
            return _blocked(pre)
        arguments = json.loads(pre.text_out)
        try:
            if snapshot.source_kind == "openapi":
                text, upstream_error = await _openapi_call(snapshot, op, arguments, settings), False
            else:
                text, upstream_error = await _remote_call(snapshot, op, arguments, settings, caller)
        except mcp_client.ToolCallError as exc:
            return Outcome("", True, "error", exc.code, guard.strongest)
        text, _ = mcp_client._truncate(text, settings.tool_result_max_chars)
        post = await guard.check("tool.post", text, op["name"])
        if post.action == "block":
            return _blocked(post)
        if upstream_error:
            return Outcome(post.text_out, True, "error", "tool_error", guard.strongest)
        return Outcome(post.text_out, False, "ok", None, guard.strongest)


def _blocked(decision: engine.Decision) -> Outcome:
    message = decision.message or "Blocked by a guardrail policy."
    text = f"error: guardrail_blocked ({message})"
    return Outcome(text, True, "blocked", "guardrail_blocked", "block")


_AUDIT_OUTCOME = {"ok": "success", "error": "error", "blocked": "denied", "denied": "denied"}


async def _record(
    snapshot: Snapshot, caller: Caller, operation: str, outcome: Outcome, latency_ms: int
) -> None:
    async with db.session_scope() as session:
        session.add(
            McpServerCall(
                server_id=uuid.UUID(snapshot.id),
                operation=operation,
                status=outcome.status,
                error_code=outcome.code,
                latency_ms=latency_ms,
                run_id=uuid.UUID(caller.run_id) if caller.run_id else None,
                actor_type=caller.actor_type,
                actor_id=caller.actor_id,
                guardrail_action=outcome.guardrail_action,
            )
        )
        await session.commit()
    await write_event_detached(
        AuditEntry(
            action="mcp_server_call",
            resource_type="mcp_server",
            outcome=_AUDIT_OUTCOME[outcome.status],
            actor_type=caller.actor_type,
            actor_id=caller.actor_id,
            project_id=snapshot.project_id,
            resource_id=snapshot.id,
            after={
                "operation": operation,
                "status": outcome.status,
                "error_code": outcome.code,
                "latency_ms": latency_ms,
                "run_id": caller.run_id,
            },
            request_id=caller.request_id,
            ip=caller.ip,
            via_key_id=caller.via_key_id,
        )
    )
    log.info(
        "mcp_server_call server=%s operation=%s status=%s code=%s latency_ms=%d",
        snapshot.key,
        operation,
        outcome.status,
        outcome.code,
        latency_ms,
    )


# --- the MCP server and the ASGI endpoint ---


def _server(snapshot: Snapshot, caller: Caller, settings: Settings) -> Server:
    async def list_tools(ctx, params) -> types.ListToolsResult:
        tools = [
            types.Tool(
                name=name,
                description=op.get("alias_description") or op.get("description"),
                input_schema=op["input_schema"],
            )
            for name, op in sorted(published(snapshot.operations, snapshot.exposed).items())
        ]
        return types.ListToolsResult(tools=tools)

    async def call_tool(ctx, params) -> types.CallToolResult:
        outcome = await invoke(snapshot, caller, params.name, params.arguments or {}, settings)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=outcome.text)], is_error=outcome.is_error
        )

    return Server(f"ffcore-{snapshot.key}", on_list_tools=list_tools, on_call_tool=call_tool)


def _settings_of(scope) -> Settings:
    app = scope.get("app")
    overrides = getattr(app, "dependency_overrides", {}) if app is not None else {}
    return overrides.get(get_settings, get_settings)()


def _key_of(scope) -> str | None:
    path, root = scope.get("path", ""), scope.get("root_path", "")
    if root and path.startswith(root):
        path = path[len(root) :]
    found = _KEY_PATH.match(path)
    return found.group(1) if found else None


class PublishedMcpApp:
    """Mounted at /mcp: one stateless MCP server per request, after the checks above."""

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return
        key = _key_of(scope)
        if key is None:
            await _error(_not_found())(scope, receive, send)
            return
        settings = _settings_of(scope)
        request = Request(scope, receive)
        request.state.ffcore_settings = settings
        try:
            actor = await resolve_actor(request, settings)
            snapshot, caller = await admit(request, actor, key)
        except ApiError as exc:
            await _error(exc)(scope, receive, send)
            return
        manager = StreamableHTTPSessionManager(
            app=_server(snapshot, caller, settings),
            json_response=True,
            stateless=True,
            security_settings=TransportSecuritySettings(enable_dns_rebinding_protection=False),
        )
        async with manager.run():
            await manager.handle_request(scope, receive, send)


app = PublishedMcpApp()
