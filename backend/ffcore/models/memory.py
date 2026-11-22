"""14 tables (migration 14_0001).

`memories` holds one item per learned fact about a member. `agent_id` NULL: valid in every agent
of the project (profile, preference); set: only in that agent (decision, fact). There is no
`scope` column (N26, ARCH-07): team and organisation memory are out of scope and come additive.
A user's delete removes the row at once (K-14-0003 S6); `archived` keeps a superseded or
over-limit item visible to its owner. The embedding is the installation's model (P5): when the
model changes the vectors are made again from the stored text.

`memory_settings`: one row per project (agent_id NULL) and optionally one per agent; the run uses
the agent's row, else the project's, else memory is off (S2). `memory_opt_outs`: a member who
turned memory off; while the row exists nothing is written or recalled for them (S5).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy import text as sql_text  # `text` is also a column name of memories
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base

KINDS = ("profile", "preference", "fact", "decision")
STATUSES = ("active", "archived")

DEFAULT_MAX_ITEMS = 200
DEFAULT_TOP_K = 5
DEFAULT_EXTRACTION_MODEL = "memory-extract"


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        CheckConstraint(f"kind IN {KINDS}", name="kind"),
        CheckConstraint(f"status IN {STATUSES}", name="status"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
        CheckConstraint("use_count >= 0", name="use_count"),
        Index("ix_memories_owner", "project_id", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Dimension from EMBED_DIM at migration time (04a pattern); the ORM type is dimensionless.
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    source_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=sql_text("0"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'active'"))


class MemorySetting(Base):
    __tablename__ = "memory_settings"
    __table_args__ = (
        CheckConstraint("max_items_per_user > 0", name="max_items"),
        CheckConstraint("recall_top_k >= 0 AND recall_top_k <= 50", name="recall_top_k"),
        CheckConstraint("ttl_days IS NULL OR ttl_days > 0", name="ttl_days"),
        Index(
            "uq_memory_settings_project",
            "project_id",
            unique=True,
            postgresql_where=sql_text("agent_id IS NULL"),
        ),
        Index(
            "uq_memory_settings_agent",
            "project_id",
            "agent_id",
            unique=True,
            postgresql_where=sql_text("agent_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agents.id", ondelete="CASCADE"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))
    allowed_kinds: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    max_items_per_user: Mapped[int] = mapped_column(Integer, nullable=False)
    recall_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    ttl_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_model: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    updated_by: Mapped[str] = mapped_column(Text, nullable=False)


class MemoryOptOut(Base):
    __tablename__ = "memory_opt_outs"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
