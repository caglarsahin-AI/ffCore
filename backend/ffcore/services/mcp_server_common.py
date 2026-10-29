"""What FFCore's own MCP servers (mcp-search, mcp-sql; 05a) share.

Both run from the backend image as their own compose services, hold no signing key and relay
the caller's `X-On-Behalf-Of` token unchanged to the backend (C3, K-05a-0002 S3).

Every HTTP request is checked before MCP sees it (CallerCheck):
- `Authorization: Bearer <SERVICE_TOKEN>` (only the backend calls these services),
- an `X-On-Behalf-Of` token whose `aud` lists this tool's key (a token cut for another tool
  is refused, 403 audience_mismatch) and that has not expired (401 token_expired).
These reads of the token are routing checks, not authentication: the signature is verified by
the backend, which the service calls with the same token.
"""

import hmac
import os
import time
import uuid
from typing import Annotated, Any, Literal

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from starlette.responses import JSONResponse

from ffcore.core.auth import (
    OBO_HEADER,
    OnBehalfOfError,
    service_authorization,
    unverified_on_behalf_of_claims,
)
from ffcore.core.config import Settings
from ffcore.core.egress import EgressError, EgressTimeout, SafeOutboundClient
from ffcore.core.logging import configure_logging

BACKEND_TIMEOUT = EgressTimeout(connect=5, read=30, total=60)


class McpServiceSettings(BaseSettings):
    """What mcp-search and mcp-sql read from their environment, and nothing more: no signing
    key, no backend database, no encryption key (K-05a-0002 S3). The backend's Settings would
    require all of them. Same names and meanings as core/config.Settings; the helpers that take
    a Settings (egress, service_authorization, configure_logging) read only these fields."""

    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    service_token: SecretStr = Field(min_length=32)
    offline: bool
    egress_allowlist: Annotated[list[str], NoDecode] = []
    allowed_internal_hosts: Annotated[list[str], NoDecode] = []
    internal_api_url: str = "http://backend:8000"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # mcp-sql only.
    sql_demo_database_url: SecretStr | None = None
    sql_max_rows: int = Field(default=500, gt=0)
    sql_timeout_s: int = Field(default=20, gt=0)

    @field_validator("egress_allowlist", "allowed_internal_hosts", mode="before")
    @classmethod
    def _split_commas(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().lower() for item in value.split(",") if item.strip()]
        return value


def _error(status: int, code: str, message: str) -> JSONResponse:
    error_type = "authentication_error" if status == 401 else "permission_error"
    return JSONResponse(
        {"error": {"type": error_type, "code": code, "message": message}}, status_code=status
    )


def token_claims(token: str) -> dict[str, Any]:
    """Claims read without the signature (routing only; the backend verifies)."""
    return unverified_on_behalf_of_claims(token)


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
        except OnBehalfOfError:
            return _error(401, "invalid_token", "Token is invalid.")
        if self.tool_key not in _audiences(claims):
            return _error(403, "audience_mismatch", "Token audience mismatch.")
        exp = claims.get("exp")
        if not isinstance(exp, int) or time.time() >= exp:
            return _error(401, "token_expired", "Token has expired.")
        return None


class Relay:
    """The caller's identity, taken from the MCP request headers, for backend calls."""

    def __init__(self, headers: dict[str, str] | None) -> None:
        lowered = {k.lower(): v for k, v in (headers or {}).items()}
        self.token = lowered.get(OBO_HEADER.lower(), "")
        self.project_id = token_claims(self.token)["project_id"]
        value = lowered.get("x-run-id")
        try:
            self.run_id = str(uuid.UUID(value)) if value else None
        except ValueError:
            self.run_id = None

    async def call(
        self, settings: Settings, method: str, path: str, body: Any = None, not_found: str = ""
    ) -> Any:
        """Backend call on behalf of the caller; a failure is a ToolError with a code only."""
        headers = {**service_authorization(settings), OBO_HEADER: self.token}
        if self.run_id:
            headers["X-Run-Id"] = self.run_id
        url = f"{settings.internal_api_url.rstrip('/')}{path}"
        try:
            async with SafeOutboundClient(timeout=BACKEND_TIMEOUT, settings=settings) as client:
                response = await client.request(method, url, headers=headers, json=body)
        except EgressError:
            raise ToolError("backend_unreachable") from None
        if response.status_code == 200:
            return response.json()
        if response.status_code == 401:
            raise ToolError("token_rejected")
        if response.status_code == 403:
            raise ToolError("forbidden")
        if response.status_code == 404 and not_found:
            raise ToolError(not_found)
        raise ToolError(f"backend_http_{response.status_code}")


def build_app(server: MCPServer, settings: Settings, *, tool_key: str, allowed_hosts: list[str]):
    security = TransportSecuritySettings(allowed_hosts=allowed_hosts, allowed_origins=[])
    return CallerCheck(server.streamable_http_app(transport_security=security), settings, tool_key)


def serve(build: Any, *, default_key: str, key_env: str) -> None:
    """Process entry: central logging (02), tool key and allowed Host values from the env."""
    settings = McpServiceSettings()
    configure_logging(settings)
    tool_key = os.environ.get(key_env, default_key)
    hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", f"{default_key}:*").split(",")]
    app = build(settings, tool_key=tool_key, allowed_hosts=hosts)
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
