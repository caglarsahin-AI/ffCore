"""conversations, messages, runs, run_events (06a).

`conversations` and `runs` are project-owned root tables (C3 common columns; `runs.created_by`
is who started the run, `user_id` the user it ran for, the same unless a service acts on behalf
of a user). `messages` is a child of `conversations`; `run_events` is append-only.

Facade fields (`api_key_id`, channel values api/slack/teams/mattermost/widget, trigger types)
are here from the start so 06b, 11 and 15 add no migration (brief 06 R5.1, N8). `api_key_id`
has no foreign key until 03c creates `api_keys`.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps
from ffcore.runtime.contracts import Channel, OutcomeLabel, RunEventType, RunStatus, TriggerType


def _values(enum) -> tuple[str, ...]:
    return tuple(member.value for member in enum)


RUN_STATUSES = _values(RunStatus)
RUN_CHANNELS = _values(Channel)
TRIGGER_TYPES = _values(TriggerType)
OUTCOME_LABELS = _values(OutcomeLabel)
RUN_EVENT_TYPES = _values(RunEventType)
MESSAGE_ROLES = ("user", "assistant")


class Conversation(Timestamps, Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(Text, server_default=sql_text("''"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Run(Timestamps, Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        CheckConstraint(f"channel IN {RUN_CHANNELS}", name="channel"),
        CheckConstraint(f"trigger_type IN {TRIGGER_TYPES}", name="trigger_type"),
        CheckConstraint(
            f"outcome_label IS NULL OR outcome_label IN {OUTCOME_LABELS}", name="outcome_label"
        ),
        Index("ix_runs_project_queued", "project_id", "queued_at"),
        Index("ix_runs_agent", "agent_id"),
        Index(
            "ix_runs_checkpoint_pending",
            "ended_at",
            postgresql_where=sql_text("checkpoint_deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    channel: Mapped[str] = mapped_column(Text)
    trigger_type: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'queued'"))
    input: Mapped[str] = mapped_column(Text)
    variables: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    output: Mapped[str | None] = mapped_column(Text)
    partial: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    error_code: Mapped[str | None] = mapped_column(Text)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_formulas: Mapped[dict | None] = mapped_column(JSONB)
    outcome_label: Mapped[str | None] = mapped_column(Text)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6))
    langfuse_trace_id: Mapped[str | None] = mapped_column(Text)
    model_ms: Mapped[int | None] = mapped_column(Integer)
    tool_ms: Mapped[int | None] = mapped_column(Integer)
    retrieval_ms: Mapped[int | None] = mapped_column(Integer)
    unaccounted_ms: Mapped[int | None] = mapped_column(Integer)
    slowest_step: Mapped[str | None] = mapped_column(Text)
    queue_wait_ms: Mapped[int | None] = mapped_column(Integer)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # POST .../cancel sets it; the worker stops at the next step boundary (K-06a-0002 S8).
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # FOLLOWUP-116: the run's LangGraph thread was deleted (NULL on a finished run: the sweep
    # tries again); a source document of the still-live run was deleted (it ends source_deleted).
    checkpoint_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 03c (FOLLOWUP-119): the run's prompt and answer text was cleared (retention `content`).
    content_cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(f"role IN {MESSAGE_ROLES}", name="role"),
        Index("ix_messages_conversation", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id")
    )
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"))
    role: Mapped[str] = mapped_column(Text)
    # The raw user message lives only here and is under the `content` retention class (02, 08).
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list | None] = mapped_column(JSONB)
    feedback: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )


class RunEvent(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
        CheckConstraint(f"type IN {RUN_EVENT_TYPES}", name="type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("runs.id"))
    seq: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sql_text("now()"))
    type: Mapped[str] = mapped_column(Text)
    iteration: Mapped[int | None] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
