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
    name: Annotated[str, Field(pattern=r"^[A-Za-z0-9-]{1,64}$", description="Header name.")]
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
    endpoint_url: Annotated[str, Field(min_length=1, max_length=2048)]
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
