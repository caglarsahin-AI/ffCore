"""mcp-search (05a): the MCP server behind `search_documents(query, kb_key, top_k)` (C7).

Runs as its own compose service from the backend image: `python -m ffcore.services.
mcp_search_server`. It holds no signing key and no database access: it relays the caller's
`X-On-Behalf-Of` token unchanged to the backend's knowledge-base search (04a), whose ACL
applies to that user (C3, K-05a-0002 S3).

Every HTTP request is checked before MCP sees it:
- `Authorization: Bearer <SERVICE_TOKEN>` (only the backend calls this service),
- an `X-On-Behalf-Of` token whose `aud` lists this tool's key (a token cut for another tool
  is refused, 403 audience_mismatch) and that has not expired (401 token_expired).
These reads of the token are routing checks, not authentication: the signature is verified by
the backend, which this service calls with the same token.
"""

import hmac
import logging
import os
import time
import uuid
from typing import Annotated, Any

import jwt
import uvicorn
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from starlette.responses import JSONResponse

from ffcore.core.auth import OBO_HEADER, service_authorization
from ffcore.core.config import Settings, get_settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.core.logging import configure_logging

log = logging.getLogger("ffcore.mcp_search")

DEFAULT_TOOL_KEY = "mcp-search"
SEARCH_TIMEOUT = EgressTimeout(connect=5, read=30, total=60)
NO_HITS = "No passages found."


def _error(status: int, code: str, message: str) -> JSONResponse:
    error_type = "authentication_error" if status == 401 else "permission_error"
    return JSONResponse(
        {"error": {"type": error_type, "code": code, "message": message}}, status_code=status
    )


def token_claims(token: str) -> dict[str, Any]:
    """Claims read without the signature (routing only; the backend verifies)."""
    return jwt.decode(token, options={"verify_signature": False})


def _audiences(claims: dict[str, Any]) -> list[str]:
    aud = claims.get("aud")
    return [aud] if isinstance(aud, str) else list(aud or [])


class CallerCheck:
    """ASGI middleware: service bearer, on-behalf-of token for this tool, not expired."""

    def __init__(self, app: Any, settings: Settings, tool_key: str) -> None:
        self.app = app
        self.bearer = service_authorization(settings)["Authorization"]
        self.tool_key = tool_key

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/healthz":
            await JSONResponse({"status": "ok"})(scope, receive, send)
            return
        refusal = self._refusal({k.decode().lower(): v.decode() for k, v in scope["headers"]})
        if refusal is not None:
            await refusal(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _refusal(self, headers: dict[str, str]) -> JSONResponse | None:
        if not hmac.compare_digest(headers.get("authorization", ""), self.bearer):
            return _error(401, "unauthenticated", "Service credentials required.")
        token = headers.get(OBO_HEADER.lower())
        if not token:
            return _error(401, "unauthenticated", "On-behalf-of token required.")
        try:
            claims = token_claims(token)
        except jwt.PyJWTError:
            return _error(401, "invalid_token", "Token is invalid.")
        if self.tool_key not in _audiences(claims):
            return _error(403, "audience_mismatch", "Token audience mismatch.")
        exp = claims.get("exp")
        if not isinstance(exp, int) or time.time() >= exp:
            return _error(401, "token_expired", "Token has expired.")
        return None


async def _call_backend(
    settings: Settings, token: str, run_id: str | None, method, path, body=None
):
    headers = {**service_authorization(settings), OBO_HEADER: token}
    if run_id:
        headers["X-Run-Id"] = run_id
    url = f"{settings.internal_api_url.rstrip('/')}{path}"
    try:
        async with SafeOutboundClient(timeout=SEARCH_TIMEOUT, settings=settings) as client:
            response = await client.request(method, url, headers=headers, json=body)
    except EgressError:
        raise ToolError("backend_unreachable") from None
    if response.status_code == 200:
        return response.json()
    if response.status_code == 401:
        raise ToolError("token_rejected")
    if response.status_code == 403:
        raise ToolError("forbidden")
    if response.status_code == 404:
        raise ToolError("kb_not_found")
    raise ToolError(f"search_failed_{response.status_code}")


def _run_id(headers: dict[str, str]) -> str | None:
    value = headers.get("x-run-id")
    try:
        return str(uuid.UUID(value)) if value else None
    except ValueError:
        return None


def format_hits(hits: list[dict[str, Any]]) -> str:
    """Numbered passages with document name and page; the runtime cites them as sources."""
    if not hits:
        return NO_HITS
    parts = []
    for number, hit in enumerate(hits, start=1):
        page = f" (p. {hit['page']})" if hit.get("page") else ""
        parts.append(f"{number}. {hit['document_name']}{page}\n{hit['text']}")
    return "\n\n".join(parts)


def build_server(settings: Settings) -> MCPServer:
    server = MCPServer("mcp-search")

    @server.tool()
    async def search_documents(
        query: Annotated[str, Field(min_length=1, max_length=2000)],
        kb_key: Annotated[str, Field(min_length=1, max_length=64)],
        ctx: Context,
        top_k: Annotated[int, Field(ge=1, le=50)] = 5,
    ) -> str:
        """Search a knowledge base the caller can read. Returns numbered passages with the
        document name and page."""
        headers = {k.lower(): v for k, v in (ctx.headers or {}).items()}
        token = headers.get(OBO_HEADER.lower(), "")
        project_id = token_claims(token)["project_id"]
        run_id = _run_id(headers)
        base = f"/api/v1/projects/{project_id}/knowledge-bases"
        listing = await _call_backend(settings, token, run_id, "GET", base)
        kb_id = next((kb["id"] for kb in listing["data"] if kb["key"] == kb_key), None)
        if kb_id is None:
            raise ToolError("kb_not_found")
        found = await _call_backend(
            settings,
            token,
            run_id,
            "POST",
            f"{base}/{kb_id}/search",
            {"query": query, "top_k": top_k},
        )
        return format_hits(found["hits"])

    return server


def build_app(settings: Settings, *, tool_key: str, allowed_hosts: list[str]):
    security = TransportSecuritySettings(allowed_hosts=allowed_hosts, allowed_origins=[])
    inner = build_server(settings).streamable_http_app(transport_security=security)
    return CallerCheck(inner, settings, tool_key)


def main() -> None:
    settings = get_settings()
    configure_logging(settings)
    tool_key = os.environ.get("MCP_SEARCH_TOOL_KEY", DEFAULT_TOOL_KEY)
    hosts = os.environ.get("MCP_ALLOWED_HOSTS", "mcp-search:*").split(",")
    app = build_app(settings, tool_key=tool_key, allowed_hosts=[h.strip() for h in hosts])
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    main()
