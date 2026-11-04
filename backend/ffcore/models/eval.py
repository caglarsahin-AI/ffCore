"""eval_suites, eval_runs (09): thin local rows over Langfuse datasets and dataset runs.

Datasets, items, per-item scores and dataset runs live in Langfuse (A5, DECISION-4, ARCH-09);
there is no local `datasets` / `dataset_items` table. A suite maps a project's exam to one
Langfuse dataset (`<project_key>.<suite_key>`, K-09-0007 S6) and, optionally, to one agent
whose publish it gates (S2). An eval run keeps the summary and which 06a run answered which
item (`item_runs`), so the advancer (S4) can score finished runs and the summary stays local.
Both are project-owned root tables (C3 common columns).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

EVAL_RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
SUITE_KEY_REGEX = "^[a-z0-9][a-z0-9-]{0,62}$"


class EvalSuite(Timestamps, Base):
    __tablename__ = "eval_suites"
    __table_args__ = (
        CheckConstraint(f"key ~ '{SUITE_KEY_REGEX}'", name="key_format"),
        CheckConstraint("pass_threshold > 0 AND pass_threshold <= 1", name="pass_threshold"),
        CheckConstraint("repeat >= 1 AND repeat <= 10", name="repeat"),
        Index(
            "uq_eval_suites_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=sql_text("deleted_at IS NULL"),
        ),
        Index("ix_eval_suites_agent", "agent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    # The agent whose publish this suite gates (S2); NULL: a suite without a gate.
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    langfuse_dataset_name: Mapped[str] = mapped_column(Text)
    # [{"name": "contains"}, {"name": "llm_judge", "pass_min": 4}, ...]; validated by the API.
    scorers: Mapped[list] = mapped_column(JSONB)
    pass_threshold: Mapped[float] = mapped_column(Float)
    repeat: Mapped[int] = mapped_column(Integer, server_default=sql_text("1"))
    # S3: items whose run waits for an approval are approved by the exam's starter only when
    # this is true (audited as eval_auto_approve); false: such items are not_run.
    approve_tools: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvalRun(Timestamps, Base):
    __tablename__ = "eval_runs"
    __table_args__ = (
        CheckConstraint(f"status IN {EVAL_RUN_STATUSES}", name="status"),
        Index("ix_eval_runs_suite", "suite_id", "created_at"),
        Index(
            "ix_eval_runs_active",
            "status",
            postgresql_where=sql_text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    suite_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("eval_suites.id"))
    agent_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_versions.id")
    )
    # The user the item runs act for (runs need a user, 06a); the exam's starter.
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    langfuse_run_name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'queued'"))
    error_code: Mapped[str | None] = mapped_column(Text)
    # {item_id: {"runs": [run_id, ...], "scored": bool, "outcome": ..., "scores": {...}}}
    item_runs: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
