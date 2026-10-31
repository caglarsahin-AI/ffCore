"""Request and response bodies of the 03c API keys; part of `backend/openapi/03c.yaml`."""

from datetime import datetime
from enum import StrEnum
from ipaddress import IPv4Network, IPv6Network
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import Patch, Strict


class ApiKeyScope(StrEnum):
    """C2. `impersonate`: the key may send X-On-Behalf-Of (a user's signed token); only a project
    admin grants it."""

    chat_direct = "chat_direct"
    agents = "agents"
    impersonate = "impersonate"
    kb_search = "kb_search"
    tools_invoke = "tools_invoke"


class ApiKeyAclRole(StrEnum):
    """The role the key's own knowledge searches run under; at most the creator's role."""

    analyst = "analyst"
    developer = "developer"
    admin = "admin"


Scopes = list[ApiKeyScope]
Cidrs = list[IPv4Network | IPv6Network]


class ApiKeyCreate(Strict):
    name: str = Field(min_length=1, max_length=120)
    scopes: Scopes = Field(min_length=1)
    acl_role: ApiKeyAclRole = ApiKeyAclRole.analyst
    allowed_cidrs: Cidrs = Field(
        default_factory=list, description="Client networks allowed to use the key; empty: any."
    )
    expires_at: datetime | None = None


class ApiKeyUpdate(Patch):
    name: str = Field(default=None, min_length=1, max_length=120)
    scopes: Scopes = Field(default=None, min_length=1)
    acl_role: ApiKeyAclRole = Field(default=None)
    allowed_cidrs: Cidrs = Field(default=None)
    expires_at: datetime | None = Field(default=None)


class ApiKeyOut(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    key_prefix: str = Field(description="Public part of the key, shown in lists and audit.")
    scopes: Scopes
    acl_role: ApiKeyAclRole
    allowed_cidrs: list[str]
    expires_at: datetime | None
    last_used_at: datetime | None = Field(description="Updated at most once a minute.")
    revoked_at: datetime | None
    created_by: str
    created_at: datetime


class ApiKeyCreated(ApiKeyOut):
    key: str = Field(description="The raw key. Returned only here, once; it is never stored.")


class ApiKeyList(BaseModel):
    data: list[ApiKeyOut]
