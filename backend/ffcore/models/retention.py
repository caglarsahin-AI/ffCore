"""retention_policies and retention_runs (03c, R2.2): one class list for every package.

`retention_policies`: one global row per data class (seeded by migration 03c_0002) and optional
per-project overrides (`project_id` set). C3 exception: rows are edited, never soft-deleted.
`retention_runs`: one row per class and execution (dry run, schedule, manual, document delete);
append-only (trigger + REVOKE, like audit_events). C3 exception.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base

# Brief 03 R2.2, the single list: class -> (keep_days, min_days, max_days, expiry_behavior).
RETENTION_CLASSES = {
    "content": (30, 1, 90, "clear_content"),
    "telemetry": (90, 30, 400, "delete"),
    "traces": (30, 7, 180, "delete"),
    "jobs": (90, 30, 365, "delete"),
    "metrics": (45, 7, 180, "delete"),
    "alerts": (180, 90, 730, "delete"),
    "audit": (365, 365, 3650, "delete"),
    "usage": (760, 400, 1095, "delete"),
    "results": (365, 90, 3650, "delete"),
    "memory": (365, 30, 1095, "delete"),
}
EXPIRY_BEHAVIORS = ("delete", "clear_content")
RUN_TRIGGERS = ("dry_run", "schedule", "manual", "document_delete")
# partial: a batch failed and the class stopped there (the other classes went on).
RUN_STATUSES = ("ok", "partial", "failed")


class RetentionPolicy(Base):
    __tablename__ = "retention_policies"
    __table_args__ = (
        CheckConstraint(f"data_class IN {tuple(RETENTION_CLASSES)}", name="data_class"),
        CheckConstraint(f"expiry_behavior IN {EXPIRY_BEHAVIORS}", name="expiry_behavior"),
        CheckConstraint("keep_days BETWEEN min_days AND max_days", name="keep_in_range"),
        Index(
            "uq_retention_policies_class_project",
            "data_class",
            text("coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_class: Mapped[str] = mapped_column(Text)
    # NULL: the installation default; set: this project's override.
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    keep_days: Mapped[int] = mapped_column(Integer)
    min_days: Mapped[int] = mapped_column(Integer)
    max_days: Mapped[int] = mapped_column(Integer)
    expiry_behavior: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
    updated_by: Mapped[str] = mapped_column(Text, server_default=text("'migration'"))


class RetentionRun(Base):
    """What one execution did per class: counts only, never the removed content."""

    __tablename__ = "retention_runs"
    __table_args__ = (
        CheckConstraint(f"trigger IN {RUN_TRIGGERS}", name="trigger"),
        CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        Index("ix_retention_runs_ts", "ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    data_class: Mapped[str] = mapped_column(Text)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    trigger: Mapped[str] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(Boolean)
    cutoff: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # {"run_events.llm_call": 3, ...} or {"target": "none"} / {"target": "external:langfuse"}.
    counts: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'ok'"))
    error_code: Mapped[str | None] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
