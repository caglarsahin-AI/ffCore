"""Request and response bodies of the 05b API (published MCP servers).

These models are the source of `backend/openapi/05b.yaml`; 10c-3 (console) consumes that file.
Changes after merge are additive only.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field

from ffcore.api.schemas import Patch, Strict
from ffcore.api.tools_schemas import AuthBasic, AuthBearer, AuthHeader, AuthNone
from ffcore.models.mcp_servers import SERVER_KEY_REGEX

ServerKey = Annotated[
    str,
    Field(
        pattern=SERVER_KEY_REGEX,
        description="Server key, unique in the installation; the endpoint is /mcp/<key>/.",
    ),
]
UpstreamAuth = Annotated[
    AuthNone | AuthBearer | AuthHeader | AuthBasic,
    Field(
        discriminator="type",
        description="Identity sent to the upstream (forward_user is not offered: platform "
        "services are never an upstream); secret fields come back as ***.",
    ),
]
UpstreamUrl = Annotated[
    str,
    Field(
        min_length=1,
        max_length=2048,
        description="Scheme, host, port and path only (400 endpoint_url_not_allowed otherwise); a "
        "platform service is 422 upstream_url_refused; the egress policy applies (400 egress_*).",
    ),
]
SpecText = Annotated[
    str,
    Field(
        min_length=1,
        description="The OpenAPI 3 document, YAML or JSON (at most 1 000 000 characters).",
    ),
]
ToolName = Annotated[str, Field(pattern=r"^[A-Za-z0-9_.-]{1,64}$")]
Access = Literal["token", "internal"]
GuardrailMode = Literal["off", "monitor", "enforce"]


class McpServerCreate(Strict):
    key: ServerKey
    name: Annotated[str, Field(min_length=1, max_length=200)]
    source_kind: Literal["openapi", "remote_mcp"]
    spec: SpecText | None = Field(
        default=None, description="Required for openapi (422 spec_required); not for remote_mcp."
    )
    upstream_base_url: UpstreamUrl
    upstream_auth: UpstreamAuth
    access: Access = Field(
        default="internal",
        description="internal: only the platform runtime; token: API keys with tools_invoke too.",
    )
    guardrail_mode: GuardrailMode = Field(
        default="monitor",
        description="Makes the guardrail policy stricter, never looser: each rule runs in "
        "max(this mode, its own mode).",
    )
    guardrail_policy_key: Annotated[str, Field(min_length=1, max_length=64)] = "default"


class Alias(Strict):
    name: ToolName | None = None
    description: Annotated[str, Field(max_length=2000)] | None = None


class McpServerUpdate(Patch):
    name: Annotated[str, Field(min_length=1, max_length=200)] = Field(default=None)
    upstream_base_url: UpstreamUrl = Field(default=None)
    upstream_auth: UpstreamAuth = Field(default=None)
    access: Access = Field(default=None)
    guardrail_mode: GuardrailMode = Field(default=None)
    guardrail_policy_key: Annotated[str, Field(min_length=1, max_length=64)] = Field(default=None)
    status: Literal["draft", "active", "disabled"] = Field(default=None)
    exposed_operations: list[str] = Field(
        default=None, description="Operation names (not aliases) served at /mcp/<key>/."
    )
    aliases: dict[str, Alias] = Field(
        default=None,
        description="Per operation name: the tool name and description the model sees "
        "(null keeps the operation's own).",
    )


class SpecUpload(Strict):
    spec: SpecText


class OperationOut(Strict):
    name: str
    method: str | None
    path: str | None
    description: str | None
    input_schema: dict[str, Any]
    exposable: bool
    reason: str | None = Field(description="Why an operation cannot be published, as a code.")
    alias: str | None
    alias_description: str | None
    exposed: bool


class McpServerOut(Strict):
    id: UUID
    project_id: UUID
    key: str
    name: str
    source_kind: Literal["openapi", "remote_mcp"]
    endpoint_path: str
    upstream_base_url: str
    upstream_auth: dict[str, str]
    operations: list[OperationOut]
    exposed_operations: list[str]
    protocols: list[str]
    access: Access
    guardrail_mode: GuardrailMode
    guardrail_policy_key: str
    status: Literal["draft", "active", "disabled"]
    discovered_at: datetime | None
    last_error_code: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class McpServerList(Strict):
    data: list[McpServerOut]


class ConnectionTest(Strict):
    reachable: bool
    status_code: int | None = Field(description="The upstream's HTTP status (openapi).")
    error_code: str | None
    latency_ms: int
    tools: int | None = Field(description="Tools the remote MCP server lists (remote_mcp).")


class CallOut(Strict):
    operation: str
    status: Literal["ok", "error", "blocked", "denied"]
    error_code: str | None
    latency_ms: int
    ts: datetime
    run_id: UUID | None
    actor_type: str


class CallsSummary(Strict):
    window_hours: int
    requests: int
    errors: int = Field(description="Calls that did not end ok (error, blocked, denied).")
    blocked: int
    p50_ms: int | None
    p95_ms: int | None
    recent: list[CallOut] = Field(description="The last 50 calls, newest first.")
