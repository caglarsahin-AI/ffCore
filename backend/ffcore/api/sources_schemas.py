"""Request and response bodies of the data source API (16)."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ffcore.sources.schedule import Schedule

KEY_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}$"


class SourceKind(StrEnum):
    fs = "fs"
    confluence = "confluence"
    jira = "jira"
    sharepoint = "sharepoint"


class Deployment(StrEnum):
    server = "server"
    cloud = "cloud"


class SyncMode(StrEnum):
    full = "full"
    delta = "delta"


class SyncLayer(StrEnum):
    raw = "raw"
    silver = "silver"
    gold = "gold"


class SourceStatus(StrEnum):
    active = "active"
    paused = "paused"


class DataSourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN, description="Unique in the project; used in names.")
    name: str = Field(min_length=1, max_length=200)
    kb_id: UUID
    kind: SourceKind
    deployment: Deployment | None = Field(
        default=None, description="Atlassian sources: server (Server/Data Center) or cloud."
    )
    config: dict[str, Any] = Field(
        default_factory=dict, description="Kind specific, no credentials (fs: root, globs)."
    )
    secret: dict[str, Any] | None = Field(
        default=None, description="Credentials; stored encrypted and returned as ***."
    )
    # K-16-0003 (user): a connected source syncs regularly; default daily, out of office
    # hours (UTC). The first run is still started by a person (schedule.due).
    schedule: Schedule = Field(default_factory=lambda: Schedule(kind="daily", at="02:00"))
    sync_mode: SyncMode = SyncMode.delta
    prune_max_ratio: float | None = Field(default=None, gt=0, le=1)


class DataSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    secret: dict[str, Any] | None = Field(
        default=None, description="A field sent back as *** keeps its stored value."
    )
    schedule: Schedule | None = None
    sync_mode: SyncMode | None = None
    prune_max_ratio: float | None = Field(default=None, gt=0, le=1)
    clear_prune_max_ratio: bool = False
    status: SourceStatus | None = None


class ActiveRun(BaseModel):
    id: UUID
    layer: SyncLayer
    mode: SyncMode
    status: str


class DataSourceOut(BaseModel):
    id: UUID
    project_id: UUID
    kb_id: UUID
    key: str
    name: str
    kind: SourceKind
    deployment: Deployment | None
    config: dict[str, Any]
    secret: dict[str, str] | None = Field(description="Credential field names, values ***.")
    schedule: Schedule
    sync_mode: SyncMode
    prune_max_ratio: float | None
    effective_prune_max_ratio: float
    status: SourceStatus
    last_sync_at: datetime | None
    last_error: str | None
    active_run: ActiveRun | None
    items: int
    created_by: str
    created_at: datetime
    updated_at: datetime


class DataSourceList(BaseModel):
    data: list[DataSourceOut]


class SourceConnectionTest(BaseModel):
    reachable: bool
    count: int | None = None
    error_code: str | None = None
    detail: str | None = None


class SyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: SyncLayer = Field(
        default=SyncLayer.raw,
        description="raw asks the source (then silver for what changed); silver reconverts "
        "from raw; gold rechunks and re-embeds from silver. Neither silver nor gold asks the "
        "source.",
    )
    mode: SyncMode | None = Field(default=None, description="Default: the source's sync_mode.")
    force_prune: bool = Field(
        default=False,
        description="Full raw run only, admin only: delete even when the share is over the "
        "ratio limit (prune_refused). A count mismatch is never forced.",
    )


class SyncError(BaseModel):
    code: str
    external_id: str | None = None
    detail: str | None = None


class SyncRunOut(BaseModel):
    id: UUID
    data_source_id: UUID
    layer: SyncLayer
    mode: SyncMode
    trigger: str
    requested_by: str
    force_prune: bool
    status: str
    cancel_requested: bool
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    listed: int
    added: int
    updated: int
    deleted: int
    skipped: int
    reused: int
    unchanged: int
    errors: list[SyncError]
    count_before: int | None
    count_after: int | None
    prune_decision: str | None
    error: str | None


class SyncRunList(BaseModel):
    data: list[SyncRunOut]


class SourceAttachmentOut(BaseModel):
    name: str
    size: int | None
    gate0_status: str | None
    gate0_reason: str | None
    shared: bool


class SourceItemOut(BaseModel):
    id: UUID
    external_id: str
    external_url: str | None
    title: str | None
    external_updated_at: datetime | None
    state: str
    gate0_status: str | None
    gate0_reason: str | None
    last_error: str | None
    document_id: UUID | None
    document_status: str | None
    default_admin: bool
    updated_at: datetime
    attachments: list[SourceAttachmentOut]


class SourceItemList(BaseModel):
    data: list[SourceItemOut]
    total: int


class AclMappingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_group: str = Field(
        min_length=1,
        max_length=500,
        description="A source group (fs: folder:/path; '*' maps every item).",
    )
    role: str | None = Field(default=None, pattern=r"^(user|analyst|developer|admin)$")
    user_id: UUID | None = None


class AclMappingsPut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mappings: list[AclMappingIn] = Field(max_length=1000)


class AclMappingOut(BaseModel):
    id: UUID
    external_group: str
    role: str | None
    user_id: UUID | None
    created_by: str
    created_at: datetime


class AclMappingList(BaseModel):
    data: list[AclMappingOut]
