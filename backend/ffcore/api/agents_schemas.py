"""Request and response bodies of the 06a API (agents, versions, runs, run events).

Source of `backend/openapi/06a.yaml`; the console (10b-poc-2) generates its types from that file.
Changes after the draft are additive only.
"""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from ffcore.api.schemas import Patch, Strict
from ffcore.runtime.contracts import (
    AgentKind,
    AgentStatus,
    Channel,
    OutcomeLabel,
    RunEventType,
    RunStatus,
    TriggerType,
)
from ffcore.runtime.definition import KEY_PATTERN, AgentDefinition

AgentKey = Annotated[
    str, Field(pattern=KEY_PATTERN, description="Agent key, unique within the project (C1).")
]


class AgentCreate(Strict):
    """First step of the two-step creation: name, description and model. The first draft
    version gets a minimal definition; the rest is filled with PUT .../versions/{version}."""

    key: AgentKey
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    model: str = Field(description="Project model key, e.g. chat-default.")


class AgentUpdate(Patch):
    name: str = Field(default=None, min_length=1, max_length=200)
    description: str = Field(default=None, max_length=2000)


class AgentOut(BaseModel):
    id: UUID
    project_id: UUID
    key: AgentKey
    name: str
    description: str
    status: AgentStatus
    kind: AgentKind
    current_version_id: UUID | None = Field(description="The published version, if any.")
    latest_version: int = Field(description="Highest version number (draft or published).")
    created_at: datetime
    updated_at: datetime


class AgentList(BaseModel):
    items: list[AgentOut]


class VersionOut(BaseModel):
    id: UUID
    agent_id: UUID
    version: int
    definition: AgentDefinition
    created_by: str = Field(description="Actor id that created the version.")
    created_at: datetime
    published_at: datetime | None
    eval_run_id: UUID | None = Field(description="Exam run that gated publishing (09); null.")


class VersionList(BaseModel):
    items: list[VersionOut]


class VersionUpdate(Strict):
    definition: AgentDefinition


class VersionCreate(Strict):
    from_version: int | None = Field(
        default=None, ge=1, description="Copy this version; default: the latest."
    )


class PublishRequest(Strict):
    version: int = Field(ge=1)


class RollbackRequest(Strict):
    version: int = Field(ge=1, description="A version that was published before.")


class RunCreate(Strict):
    input: str = Field(min_length=1, max_length=20000)
    variables: dict[str, str] = Field(default_factory=dict)
    conversation_id: UUID | None = Field(
        default=None, description="Continue this conversation; omitted: a new one."
    )
    channel: Literal[Channel.chat, Channel.test] = Field(
        default=Channel.chat, description="`test` marks playground runs (console 'try' panel)."
    )
    version: int | None = Field(
        default=None,
        ge=1,
        description="Test a specific version (channel=test only); default: the published one.",
    )


class FeedbackRequest(Strict):
    """Expert review of a completed run (F9, K-06a-0005)."""

    vote: Literal["correct", "partial", "wrong"]
    note: str | None = Field(default=None, max_length=2000)


class FeedbackOut(BaseModel):
    run_id: UUID
    vote: Literal["correct", "partial", "wrong"]
    note: str | None
    by: str
    at: datetime
    score_sent: bool = Field(
        description="A Langfuse score was handed over (the run has a trace and tracing is on)."
    )


class RunOut(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    agent_version_id: UUID
    conversation_id: UUID | None
    user_id: UUID | None
    api_key_id: UUID | None = Field(description="Set by the facade (06b); null here.")
    channel: Channel
    trigger_type: TriggerType
    status: RunStatus
    input: str
    output: str | None
    partial: bool = Field(description="True when `output` is what was produced before a stop.")
    error_code: str | None
    reference_id: UUID | None = Field(description="Shown to the user on a guardrail block.")
    outcome_label: OutcomeLabel | None
    confidence: float | None
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float | None
    langfuse_trace_id: str | None
    model_ms: int | None
    tool_ms: int | None
    retrieval_ms: int | None
    unaccounted_ms: int | None
    slowest_step: str | None
    queue_wait_ms: int | None
    queued_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    feedback: dict[str, Any] | None = Field(
        default=None, description="Expert feedback on the answer (F9), if given."
    )


class RunList(BaseModel):
    items: list[RunOut]


class RunEventOut(BaseModel):
    seq: int
    ts: datetime
    type: RunEventType
    iteration: int | None = Field(description="Model turn this event belongs to (grouping).")
    payload: dict[str, Any]


class RunEventList(BaseModel):
    items: list[RunEventOut]


class ResumeRequest(Strict):
    """Exactly one of `decision` (a run in waiting_approval) or `answer` (waiting_user)."""

    decision: Literal["approved", "rejected"] | None = None
    comment: str | None = Field(default=None, max_length=2000)
    answer: str | None = Field(default=None, min_length=1, max_length=20000)


SSE_DESCRIPTION = (
    "Server-sent events. Event names (C9): token, tool_call, tool_result, approval_required, "
    "question, sources, progress, fallback, done, error; unknown names are to be ignored. "
    "Each event has an `id` (resume with Last-Event-ID). A comment line is sent every "
    "SSE_KEEPALIVE_S. The stream ends after done, error, approval_required or question."
)


# --- 06b: agent manifest (export / import) ---

MANIFEST_VERSION = 1


class ManifestAgent(Strict):
    key: str = Field(pattern=KEY_PATTERN, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    kind: Literal["native", "external"] = "native"


class Manifest(Strict):
    """An agent and one version's definition (C8), portable between installations. Secrets are
    never part of it (an external agent's endpoint credentials stay where they are)."""

    manifest_version: Literal[1] = MANIFEST_VERSION
    agent: ManifestAgent
    version: int | None = Field(default=None, description="The exported version; informative.")
    definition: dict[str, Any]


class ImportResult(BaseModel):
    dry_run: bool
    action: Literal["create", "new_version"]
    agent_key: str
    id: UUID | None = Field(default=None, description="The agent's id (none for a dry run).")
    version: int
    definition: AgentDefinition
