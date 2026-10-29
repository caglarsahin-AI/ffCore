"""Request and response bodies of the 05a API (tool registry, actions, discovery, invoke).

These models are the source of `backend/openapi/05a.yaml`; 06a (runtime) and 10b-poc-2
(console) consume that file. Changes after merge are additive only.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import Field

from ffcore.api.schemas import Patch, Strict
from ffcore.models.tools import TOOL_KEY_REGEX

ToolKey = Annotated[
    str, Field(pattern=TOOL_KEY_REGEX, description="Tool key, unique within the project.")
]
SecretText = Annotated[str, Field(min_length=1, max_length=4096)]


class AuthNone(Strict):
    type: Literal["none"]


class AuthBearer(Strict):
    type: Literal["bearer"]
    token: SecretText


class AuthHeader(Strict):
    type: Literal["header"]
    name: Annotated[
        str,
        Field(
            min_length=1,
            max_length=64,
            description="Header name: an RFC 7230 token, not a transport or identity header "
            "(Host, Content-Length, Connection, Transfer-Encoding, Upgrade, TE, Trailer, "
            "Keep-Alive, Proxy-*, Authorization, X-On-Behalf-Of, X-Run-Id); otherwise 400 "
            "header_name_not_allowed.",
        ),
    ]
    value: SecretText


class AuthBasic(Strict):
    type: Literal["basic"]
    username: SecretText
    password: SecretText


class AuthForwardUser(Strict):
    """The caller's identity as an `X-On-Behalf-Of` JWT, signed for every call; internal FFCore
    services only (ALLOWED_INTERNAL_HOSTS, C3)."""

    type: Literal["forward_user"]


ToolAuth = Annotated[
    AuthNone | AuthBearer | AuthHeader | AuthBasic | AuthForwardUser,
    Field(discriminator="type", description="Upstream identity; secret fields come back as ***."),
]


class ToolCreate(Strict):
    key: ToolKey
    name: Annotated[str, Field(min_length=1, max_length=200)]
    kind: Literal["mcp", "openapi"] = "mcp"
    endpoint_url: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2048,
            description="Scheme, host, port and path only; user info, a query or a fragment is "
            "400 endpoint_url_not_allowed (credentials go into auth).",
        ),
    ]
    auth: ToolAuth


class ToolUpdate(Patch):
    name: Annotated[str, Field(min_length=1, max_length=200)] = Field(default=None)
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2048)] = Field(default=None)
    auth: ToolAuth = Field(default=None)


class ToolActionOut(Strict):
    id: UUID
    name: str
    description: str | None
    input_schema: dict[str, Any]
    needs_approval: bool
    enabled: bool
    max_calls_per_run: int | None
    timeout_s: int | None
    status: Literal["available", "missing"]
    updated_at: datetime


class ToolOut(Strict):
    id: UUID
    project_id: UUID
    key: str
    name: str
    kind: Literal["mcp", "openapi"]
    endpoint_url: str
    auth: dict[str, str]
    status: Literal["registered", "discovered", "error"]
    discovered_at: datetime | None
    last_error_code: str | None
    actions: list[ToolActionOut]
    created_by: str
    created_at: datetime
    updated_at: datetime


class ToolList(Strict):
    data: list[ToolOut]


class ToolActionUpdate(Patch):
    enabled: bool = Field(default=None)
    needs_approval: bool = Field(default=None)
    max_calls_per_run: Annotated[int, Field(gt=0, le=1000)] | None = Field(default=None)
    timeout_s: Annotated[int, Field(ge=1, le=600)] | None = Field(default=None)


class InvokeRequest(Strict):
    arguments: dict[str, Any] = Field(default_factory=dict)


class InvokeResult(Strict):
    """A direct test call. `text` is what a model would get: cut results end in
    "[truncated: N/M chars]" (C13); `is_error` is the tool's own error flag."""

    text: str
    truncated: bool
    total_chars: int
    is_error: bool
    latency_ms: int


class SqlContextRequest(Strict):
    tool_key: Annotated[
        ToolKey,
        Field(description="Key of the registered mcp-sql tool whose examples are wanted."),
    ]
    question: Annotated[str, Field(max_length=2000)] | None = None


class SqlColumn(Strict):
    name: str
    description: str
    sample_values: list[Any]
    is_metric: bool
    formula: str | None


class SqlTable(Strict):
    name: str
    description: str
    columns: list[SqlColumn]


class SqlExample(Strict):
    question: str
    sql: str


class SqlContext(Strict):
    """What mcp-sql's get_schema shows the model: tables narrowed to the question (`matched`
    false: none matched, all listed) and the nearest approved question-SQL examples."""

    tables: list[SqlTable]
    matched: bool
    examples: list[SqlExample]
