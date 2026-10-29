"""What FFCore's own MCP servers (mcp-search, mcp-sql; 05a) share.

Both run from the backend image as their own compose services, hold no signing key and relay
the caller's `X-On-Behalf-Of` token unchanged to the backend (C3, K-05a-0002 S3).

Every HTTP request is checked before MCP sees it (CallerCheck):
- `Authorization: Bearer <SERVICE_TOKEN>` (only the backend calls these services),
- an `X-On-Behalf-Of` token whose `aud` lists this tool's key (a token cut for another tool
  is refused, 403 audience_mismatch) and that has not expired (401 token_expired).
These reads of the token are routing checks that can only refuse, never authentication
(KARARLAR "05a review r1 kararları" item 2). The signature is verified by the backend:
- mcp-search relays the token to the backend, which verifies it before searching;
- mcp-sql acts on the caller's identity itself (it runs queries), so every request also goes
  through OboVerifier: the backend's POST /api/v1/internal/obo/verify, one answer per token
  kept for the token's lifetime. Its tools take the project from the verified claims.
"""

import hashlib
import hmac
import os
import time
import uuid
from collections.abc import Callable
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
    error_type = {401: "authentication_error", 403: "permission_error"}.get(status, "api_error")
    return JSONResponse(
        {"error": {"type": error_type, "code": code, "message": message}}, status_code=status
    )


def token_claims(token: str) -> dict[str, Any]:
    """Claims read without the signature (routing only; the backend verifies)."""
    return unverified_on_behalf_of_claims(token)


def _audiences(claims: dict[str, Any]) -> list[str]:
    aud = claims.get("aud")
    return [aud] if isinstance(aud, str) else list(aud or [])


class VerifyRefused(Exception):
    """The backend refused the token (401/403 with its code) or could not be asked (503
    verifier_unavailable)."""

    def __init__(self, status: int, code: str) -> None:
        super().__init__(code)
        self.status = status
        self.code = code


VERIFY_PATH = "/api/v1/internal/obo/verify"


class OboVerifier:
    """Verified claims of a caller's token, from the backend (the only holder of the key).

    One cache entry per token, keyed by a hash of the whole token and kept until the token's
    `exp`: a token is cut per call, so the MCP requests of one call ask once. Keying by `jti`
    alone would let a forged token that copies a verified token's jti reuse its answer.
    Refusals are not kept."""

    def __init__(
        self, settings: Settings, tool_key: str, *, clock: Callable[[], float] = time.time
    ) -> None:
        self.settings = settings
        self.tool_key = tool_key
        self.clock = clock
        self.cache: dict[str, dict[str, Any]] = {}

    async def claims(self, token: str) -> dict[str, Any]:
        now = self.clock()
        key = hashlib.sha256(token.encode()).hexdigest()
        kept = self.cache.get(key)
        if kept is not None and now < kept["exp"]:
            return kept
        claims = await self._ask(token)
        self.cache = {k: v for k, v in self.cache.items() if now < v["exp"]}
        self.cache[key] = claims
        return claims

    async def _ask(self, token: str) -> dict[str, Any]:
        url = f"{self.settings.internal_api_url.rstrip('/')}{VERIFY_PATH}"
        body = {"token": token, "audience": self.tool_key}
        try:
            async with SafeOutboundClient(
                timeout=BACKEND_TIMEOUT, settings=self.settings
            ) as client:
                response = await client.request(
                    "POST", url, headers=service_authorization(self.settings), json=body
                )
        except EgressError:
            raise VerifyRefused(503, "verifier_unavailable") from None
        if response.status_code == 200:
            return response.json()
        if response.status_code in (401, 403):
            try:
                code = response.json()["error"]["code"]
            except (ValueError, KeyError, TypeError):
                code = "invalid_token"
            raise VerifyRefused(response.status_code, str(code))
        raise VerifyRefused(503, "verifier_unavailable")


class CallerCheck:
    """ASGI middleware: service bearer, on-behalf-of token for this tool, not expired, and
    (with a verifier) the backend's verification of the token."""

    def __init__(
        self,
        app: Any,
        settings: Settings,
        tool_key: str,
        *,
        verifier: OboVerifier | None = None,
    ) -> None:
        self.app = app
        self.bearer = service_authorization(settings)["Authorization"]
        self.tool_key = tool_key
        self.verifier = verifier

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if scope["path"] == "/healthz":
            await JSONResponse({"status": "ok"})(scope, receive, send)
            return
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        refusal = self._refusal(headers)
        if refusal is None and self.verifier is not None:
            try:
                await self.verifier.claims(headers[OBO_HEADER.lower()])
            except VerifyRefused as exc:
                refusal = _error(exc.status, exc.code, "Token was not accepted.")
        if refusal is not None:
            await refusal(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _refusal(self, headers: dict[str, str]) -> JSONResponse | None:
        """A refusal, or None; None never admits a request by itself (routing read)."""
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


def obo_token(headers: dict[str, str] | None) -> str:
    lowered = {k.lower(): v for k, v in (headers or {}).items()}
    return lowered.get(OBO_HEADER.lower(), "")


class Relay:
    """The caller's identity, taken from the MCP request headers, for backend calls.

    `project_id` from verified claims (mcp-sql); without it the project is the routing read
    (mcp-search), and the backend verifies the same token before answering."""

    def __init__(self, headers: dict[str, str] | None, project_id: str | None = None) -> None:
        lowered = {k.lower(): v for k, v in (headers or {}).items()}
        self.token = obo_token(headers)
        self.project_id = project_id or token_claims(self.token)["project_id"]
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


def build_app(
    server: MCPServer,
    settings: Settings,
    *,
    tool_key: str,
    allowed_hosts: list[str],
    verifier: OboVerifier | None = None,
):
    security = TransportSecuritySettings(allowed_hosts=allowed_hosts, allowed_origins=[])
    app = server.streamable_http_app(transport_security=security)
    return CallerCheck(app, settings, tool_key, verifier=verifier)


def serve(build: Any, *, default_key: str, key_env: str) -> None:
    """Process entry: central logging (02), tool key and allowed Host values from the env."""
    settings = McpServiceSettings()
    configure_logging(settings)
    tool_key = os.environ.get(key_env, default_key)
    hosts = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", f"{default_key}:*").split(",")]
    app = build(settings, tool_key=tool_key, allowed_hosts=hosts)
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
