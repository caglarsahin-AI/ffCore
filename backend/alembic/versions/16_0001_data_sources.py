"""16: data sources (`data_sources`, `source_items`, `source_attachments`, `sync_runs`,
`source_sync_state`, `acl_mappings`)

Revision ID: 16_0001
Revises: 14_0001
Create Date: 2026-11-22

- `data_sources`: one source bound to one knowledge base; credentials only in
  `secret_encrypted` (Fernet, 03a pattern); `config` holds what the screen shows.
- `source_items`: one row per listed item, unique per (source, external id); `document_id` is
  the 04 document it became (C6).
- `source_attachments`: the Kapı 0 ledger written before a download (PayCore D1); `shared_from`
  points at the attachment whose file this one borrows (same name and size).
- `sync_runs`: per layer run counts, errors and the prune decision (D3, D4).
- `source_sync_state`: each layer's cursor (N48: not PayCore's `sync_state`).
- `acl_mappings`: a source group to exactly one role or user (C15).

Additive: six new tables, no change to an existing one.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "16_0001"
down_revision = "14_0001"
branch_labels = ("16",)
depends_on = None

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


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _fk(name: str, target: str, ondelete: str | None = "CASCADE", nullable=False) -> sa.Column:
    return sa.Column(
        name, UUID(as_uuid=True), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable
    )


def upgrade() -> None:
    op.create_table(
        "data_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _fk("project_id", "projects.id"),
        _fk("kb_id", "knowledge_bases.id", ondelete=None),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("deployment", sa.Text, nullable=True),
        sa.Column("config", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("secret_encrypted", sa.LargeBinary, nullable=True),
        sa.Column(
            "schedule",
            JSONB,
            server_default=sa.text("""'{"kind": "manual"}'::jsonb"""),
            nullable=False,
        ),
        sa.Column("sync_mode", sa.Text, server_default=sa.text("'delta'"), nullable=False),
        sa.Column("prune_max_ratio", sa.Float, nullable=True),
        sa.Column("status", sa.Text, server_default=sa.text("'active'"), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_by", sa.Text, nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"kind IN {KINDS}", name="kind"),
        sa.CheckConstraint(f"deployment IS NULL OR deployment IN {DEPLOYMENTS}", name="deployment"),
        sa.CheckConstraint(f"status IN {SOURCE_STATUSES}", name="status"),
        sa.CheckConstraint(
            "prune_max_ratio IS NULL OR (prune_max_ratio > 0 AND prune_max_ratio <= 1)",
            name="prune_max_ratio",
        ),
    )
    op.create_index(
        "uq_data_sources_project_key_live",
        "data_sources",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "source_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _fk("data_source_id", "data_sources.id"),
        sa.Column("external_id", sa.Text, nullable=False),
        sa.Column("external_url", sa.Text, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("external_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.Text, nullable=True),
        sa.Column("silver_hash", sa.Text, nullable=True),
        sa.Column("raw_path", sa.Text, nullable=True),
        _fk("document_id", "documents.id", ondelete="SET NULL", nullable=True),
        sa.Column("acl_source", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("state", sa.Text, server_default=sa.text("'active'"), nullable=False),
        sa.Column("gate0_status", sa.Text, nullable=True),
        sa.Column("gate0_reason", sa.Text, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("last_run_id", UUID(as_uuid=True), nullable=True),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(f"state IN {ITEM_STATES}", name="state"),
        sa.CheckConstraint(
            f"gate0_status IS NULL OR gate0_status IN {GATE_STATUSES}", name="gate0"
        ),
        sa.UniqueConstraint("data_source_id", "external_id", name="uq_source_items_external"),
    )
    op.create_index("ix_source_items_document", "source_items", ["document_id"])

    op.create_table(
        "source_attachments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _fk("source_item_id", "source_items.id"),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("size", sa.BigInteger, nullable=True),
        sa.Column("mime", sa.Text, nullable=True),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("gate0_status", sa.Text, nullable=True),
        sa.Column("gate0_reason", sa.Text, nullable=True),
        sa.Column("raw_path", sa.Text, nullable=True),
        _fk("shared_from", "source_attachments.id", ondelete="SET NULL", nullable=True),
        _now("created_at"),
        _now("updated_at"),
        sa.CheckConstraint(
            f"gate0_status IS NULL OR gate0_status IN {GATE_STATUSES}", name="gate0"
        ),
        sa.UniqueConstraint("source_item_id", "name", name="uq_source_attachments_item_name"),
    )
    op.create_index("ix_source_attachments_name_size", "source_attachments", ["name", "size"])

    op.create_table(
        "sync_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _fk("data_source_id", "data_sources.id"),
        sa.Column("layer", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("requested_by", sa.Text, nullable=False),
        sa.Column("force_prune", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'queued'"), nullable=False),
        sa.Column("cancel_requested", sa.Boolean, server_default=sa.text("false"), nullable=False),
        _now("created_at"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        *(
            sa.Column(name, sa.Integer, server_default=sa.text("0"), nullable=False)
            for name in ("listed", "added", "updated", "deleted", "skipped", "reused", "unchanged")
        ),
        sa.Column("errors", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("count_before", sa.Integer, nullable=True),
        sa.Column("count_after", sa.Integer, nullable=True),
        sa.Column("prune_decision", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.CheckConstraint(f"layer IN {LAYERS}", name="layer"),
        sa.CheckConstraint(f"mode IN {MODES}", name="mode"),
        sa.CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        sa.CheckConstraint(f"trigger IN {TRIGGERS}", name="trigger"),
        sa.CheckConstraint(
            f"prune_decision IS NULL OR prune_decision IN {PRUNE_DECISIONS}",
            name="prune_decision",
        ),
    )
    op.create_index("ix_sync_runs_source_started", "sync_runs", ["data_source_id", "started_at"])
    # One active run per source (raw, silver or gold): a second trigger is 409 sync_running.
    op.create_index(
        "uq_sync_runs_one_active",
        "sync_runs",
        ["data_source_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )

    op.create_table(
        "source_sync_state",
        _fk("data_source_id", "data_sources.id"),
        sa.Column("layer", sa.Text, nullable=False),
        sa.Column("cursor", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("data_source_id", "layer", name="pk_source_sync_state"),
        sa.CheckConstraint(f"layer IN {LAYERS}", name="layer"),
    )

    op.create_table(
        "acl_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        _fk("data_source_id", "data_sources.id"),
        sa.Column("external_group", sa.Text, nullable=False),
        sa.Column("role", sa.Text, nullable=True),
        _fk("user_id", "users.id", nullable=True),
        sa.Column("created_by", sa.Text, nullable=False),
        _now("created_at"),
        sa.CheckConstraint("(role IS NULL) <> (user_id IS NULL)", name="one_target"),
        sa.CheckConstraint(
            "role IS NULL OR role IN ('user', 'analyst', 'developer', 'admin')", name="role"
        ),
        sa.UniqueConstraint(
            "data_source_id", "external_group", "role", "user_id", name="uq_acl_mappings_target"
        ),
    )


def downgrade() -> None:
    for table in (
        "acl_mappings",
        "source_sync_state",
        "sync_runs",
        "source_attachments",
        "source_items",
        "data_sources",
    ):
        op.drop_table(table)
