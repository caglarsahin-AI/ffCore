"""16 tables (migration 16_0001): data sources feeding a knowledge base from a live system.

`data_sources`: one configured source (network folder, Confluence, Jira, SharePoint) bound to one
knowledge base. `config` holds only what the screen shows (URL, filters, schedule choices);
credentials are Fernet-encrypted in `secret_encrypted` and never leave the API unmasked.
`source_items`: one row per item the source listed (a file, a page, an issue); `document_id` is
the knowledge-base document the item became (04, C6). `source_attachments`: the Kapı 0 ledger,
written before anything is downloaded (PayCore D1); an attachment that was downloaded becomes a
04 `attachments` row when its document is converted. `sync_runs`: one row per layer run, with
the counts and the prune decision (D3, D4). `source_sync_state`: each layer's own cursor (N48:
not PayCore's `sync_state`). `acl_mappings`: a source group to a role or a user (C15).
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
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

KINDS = ("fs", "confluence", "jira", "sharepoint")
DEPLOYMENTS = ("server", "cloud")
SOURCE_STATUSES = ("active", "paused")
ITEM_STATES = ("active", "deleted")
GATE_STATUSES = ("ok", "flagged", "skipped")
LAYERS = ("raw", "silver", "gold")
MODES = ("full", "delta")
RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
TRIGGERS = ("manual", "schedule", "cli")
PRUNE_DECISIONS = (
    "none",
    "done",
    "forced",
    "count_mismatch",
    "prune_refused",
    "listing_failed",
    "prune_failed",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN {values}" if len(values) > 1 else f"{column} = '{values[0]}'"


class DataSource(Timestamps, Base):
    __tablename__ = "data_sources"
    __table_args__ = (
        CheckConstraint(_in("kind", KINDS), name="kind"),
        CheckConstraint(
            f"deployment IS NULL OR {_in('deployment', DEPLOYMENTS)}", name="deployment"
        ),
        CheckConstraint(_in("status", SOURCE_STATUSES), name="status"),
        CheckConstraint(
            "prune_max_ratio IS NULL OR (prune_max_ratio > 0 AND prune_max_ratio <= 1)",
            name="prune_max_ratio",
        ),
        Index(
            "uq_data_sources_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=sql_text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    deployment: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    schedule: Mapped[dict] = mapped_column(
        JSONB, server_default=sql_text("""'{"kind": "manual"}'::jsonb""")
    )
    sync_mode: Mapped[str] = mapped_column(Text, server_default=sql_text("'delta'"))
    prune_max_ratio: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'active'"))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceItem(Timestamps, Base):
    __tablename__ = "source_items"
    __table_args__ = (
        CheckConstraint(_in("state", ITEM_STATES), name="state"),
        CheckConstraint(
            f"gate0_status IS NULL OR {_in('gate0_status', GATE_STATUSES)}", name="gate0"
        ),
        UniqueConstraint("data_source_id", "external_id", name="uq_source_items_external"),
        Index("ix_source_items_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    external_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    external_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(Text)
    # The content hash silver last ingested: an item whose hash differs waits for silver.
    silver_hash: Mapped[str | None] = mapped_column(Text)
    raw_path: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")
    )
    acl_source: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    state: Mapped[str] = mapped_column(Text, server_default=sql_text("'active'"))
    gate0_status: Mapped[str | None] = mapped_column(Text)
    gate0_reason: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class SourceAttachment(Timestamps, Base):
    __tablename__ = "source_attachments"
    __table_args__ = (
        CheckConstraint(
            f"gate0_status IS NULL OR {_in('gate0_status', GATE_STATUSES)}", name="gate0"
        ),
        UniqueConstraint("source_item_id", "name", name="uq_source_attachments_item_name"),
        Index("ix_source_attachments_name_size", "name", "size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_items.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int | None] = mapped_column(BigInteger)
    mime: Mapped[str | None] = mapped_column(Text)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gate0_status: Mapped[str | None] = mapped_column(Text)
    gate0_reason: Mapped[str | None] = mapped_column(Text)
    raw_path: Mapped[str | None] = mapped_column(Text)
    shared_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_attachments.id", ondelete="SET NULL")
    )


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        CheckConstraint(_in("layer", LAYERS), name="layer"),
        CheckConstraint(_in("mode", MODES), name="mode"),
        CheckConstraint(_in("status", RUN_STATUSES), name="status"),
        CheckConstraint(_in("trigger", TRIGGERS), name="trigger"),
        CheckConstraint(
            f"prune_decision IS NULL OR {_in('prune_decision', PRUNE_DECISIONS)}",
            name="prune_decision",
        ),
        Index("ix_sync_runs_source_started", "data_source_id", "started_at"),
        # One active run per source (raw, silver or gold): the next waits for the last (D3).
        Index(
            "uq_sync_runs_one_active",
            "data_source_id",
            unique=True,
            postgresql_where=sql_text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    layer: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    requested_by: Mapped[str] = mapped_column(Text, nullable=False)
    force_prune: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'queued'"))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    listed: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    added: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    updated: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    deleted: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    skipped: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    reused: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    unchanged: Mapped[int] = mapped_column(Integer, server_default=sql_text("0"))
    errors: Mapped[list] = mapped_column(JSONB, server_default=sql_text("'[]'::jsonb"))
    count_before: Mapped[int | None] = mapped_column(Integer)
    count_after: Mapped[int | None] = mapped_column(Integer)
    prune_decision: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)


class SourceSyncState(Base):
    __tablename__ = "source_sync_state"
    __table_args__ = (CheckConstraint(_in("layer", LAYERS), name="layer"),)

    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True
    )
    layer: Mapped[str] = mapped_column(Text, primary_key=True)
    cursor: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AclMapping(Base):
    __tablename__ = "acl_mappings"
    __table_args__ = (
        CheckConstraint("(role IS NULL) <> (user_id IS NULL)", name="one_target"),
        CheckConstraint(
            "role IS NULL OR role IN ('user', 'analyst', 'developer', 'admin')", name="role"
        ),
        UniqueConstraint(
            "data_source_id", "external_group", "role", "user_id", name="uq_acl_mappings_target"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    data_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False
    )
    external_group: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
