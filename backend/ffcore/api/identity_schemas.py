"""Schemas of the 17 identity routes (directory sign-in, group mappings, CSV import)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import AccessMode, Role, Strict

Provider = Literal["ldap", "oidc"]


class SignInProviders(BaseModel):
    """What the login screen offers. Flags only: no address, no setting value."""

    local: bool = Field(description="Local email/password form is offered (LOCAL_LOGIN != off).")
    ldap: bool = Field(description="Directory accounts sign in on the same form.")
    oidc: bool = Field(description="'Sign in with your organisation account' button.")


# --- group mappings ---


class MappingCreate(Strict):
    provider: Provider
    external_group: str = Field(
        min_length=1,
        max_length=1024,
        description="LDAP group DN (compared case-insensitively) or OIDC group claim value.",
    )
    role: Role
    access: AccessMode = AccessMode.read


class MappingOut(BaseModel):
    id: UUID
    project_id: UUID
    project_key: str
    provider: Provider
    external_group: str
    role: Role
    access: AccessMode
    created_by: str
    created_at: datetime


class MappingList(BaseModel):
    data: list[MappingOut]
    # Directory-sourced members of the project(s) listed: a number, never names.
    affected_members: int


# --- identity providers (status) ---


class ProviderStatus(BaseModel):
    provider: Provider
    enabled: bool
    # ldaps or ldap (plaintext allowed for a test directory); null when off.
    transport: Literal["ldaps", "ldap"] | None = None
    accounts: int = Field(description="Platform accounts of this source.")


class LastSync(BaseModel):
    at: datetime
    outcome: str
    checked: int | None = None
    deactivated: int | None = None
    error: str | None = None


class IdentityProvidersOut(BaseModel):
    local_login: Literal["all", "superadmin_only", "off"]
    providers: list[ProviderStatus]
    last_sync: LastSync | None


class ProviderTestOut(BaseModel):
    provider: Provider
    ok: bool
    elapsed_ms: int
    code: str | None = Field(
        default=None, description="Why the test failed (e.g. service_bind_failed); no secret."
    )


# --- CSV import ---


class ImportRow(BaseModel):
    line: int = Field(description="Line number in the file (the header is line 1).")
    email: str | None
    action: Literal["create", "update", "error"]
    code: str | None = Field(default=None, description="Why the row is refused.")
    temporary_password: str | None = Field(
        default=None,
        description="New local accounts only, in the applied answer only, shown once; never "
        "stored in clear or audited.",
    )


class ImportSummary(BaseModel):
    create: int
    update: int
    error: int


class ImportReport(BaseModel):
    dry_run: bool
    summary: ImportSummary
    rows: list[ImportRow]
