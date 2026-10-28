"""08: pii_policies, guardrail_policies (project-owned root tables, C3) and guardrail_events
(append-only event table, C3 exception)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.guardrails.categories import (
    ACTIONS,
    EVENT_SOURCES,
    EVENT_STATUSES,
    MODES,
    ON_ERROR,
    SEVERITIES,
    STAGES,
)
from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

POLICY_KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class PiiPolicy(Timestamps, Base):
    __tablename__ = "pii_policies"
    __table_args__ = (
        CheckConstraint(f"key ~ '{POLICY_KEY_REGEX}'", name="key_format"),
        CheckConstraint("engine IN ('regex', 'ner')", name="engine"),
        CheckConstraint(_in("default_action", ACTIONS), name="default_action"),
        CheckConstraint("min_confidence >= 0 AND min_confidence <= 1", name="min_confidence"),
        Index(
            "uq_pii_policies_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_pii_policies_project_default_live",
            "project_id",
            unique=True,
            postgresql_where=text("is_default AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    engine: Mapped[str] = mapped_column(Text)
    default_action: Mapped[str] = mapped_column(Text)
    languages: Mapped[list[str]] = mapped_column(ARRAY(Text))
    min_confidence: Mapped[float] = mapped_column(Float)
    context_boost: Mapped[bool] = mapped_column(Boolean)
    categories: Mapped[dict] = mapped_column(JSONB)
    custom_patterns: Mapped[list] = mapped_column(JSONB)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GuardrailPolicy(Timestamps, Base):
    __tablename__ = "guardrail_policies"
    __table_args__ = (
        CheckConstraint(f"key ~ '{POLICY_KEY_REGEX}'", name="key_format"),
        CheckConstraint(_in("mode", MODES), name="mode"),
        CheckConstraint(_in("on_error", ON_ERROR), name="on_error"),
        Index(
            "uq_guardrail_policies_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_guardrail_policies_project_default_live",
            "project_id",
            unique=True,
            postgresql_where=text("is_default AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    rules: Mapped[list] = mapped_column(JSONB)
    mode: Mapped[str] = mapped_column(Text)
    short_circuit: Mapped[bool] = mapped_column(Boolean)
    on_error: Mapped[str] = mapped_column(Text)
    # {"en": ..., "tr": ...}; the error body text in the caller's locale, English fallback.
    block_message: Mapped[dict] = mapped_column(JSONB)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GuardrailEventRow(Base):
    """One row per rule evaluated at a stage. Values are masked; the raw text is never stored."""

    __tablename__ = "guardrail_events"
    __table_args__ = (
        CheckConstraint(_in("stage", STAGES), name="stage"),
        CheckConstraint(_in("action_taken", ACTIONS), name="action_taken"),
        CheckConstraint(_in("status", EVENT_STATUSES), name="status"),
        CheckConstraint(_in("mode", MODES), name="mode"),
        CheckConstraint(_in("source", EVENT_SOURCES), name="source"),
        CheckConstraint(f"severity IS NULL OR {_in('severity', SEVERITIES)}", name="severity"),
        Index("ix_guardrail_events_project_ts", "project_id", "ts"),
        Index("ix_guardrail_events_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    # runs belong to 06a; no foreign key until that table exists.
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reference_id: Mapped[str | None] = mapped_column(Text)
    policy_key: Mapped[str] = mapped_column(Text)
    stage: Mapped[str] = mapped_column(Text)
    rule: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(Text)
    input_preview: Mapped[str] = mapped_column(Text)
    findings: Mapped[list] = mapped_column(JSONB)
    matches: Mapped[list] = mapped_column(JSONB)
    severity: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[float] = mapped_column(Float)
    error: Mapped[str | None] = mapped_column(Text)
