"""14: user memory (`memories`, `memory_settings`, `memory_opt_outs`)

Revision ID: 14_0001
Revises: 11_0001
Create Date: 2026-11-22

- `memories`: one learned item per row (brief 14 "Veri modeli"); `embedding vector(EMBED_DIM)`
  with EMBED_DIM read at migration time (04a pattern, P5: one embedding model per
  installation). No `scope` column (N26). A user's delete removes the row (K-14-0003 S6).
- `memory_settings`: one row per project (`agent_id IS NULL`) and at most one per agent (two
  partial unique indexes; NULLS NOT DISTINCT is not needed).
- `memory_opt_outs`: the members who turned memory off (S5).

Additive: three new tables, no change to an existing one.
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "14_0001"
down_revision = "11_0001"
branch_labels = ("14",)
depends_on = None

KINDS = ("profile", "preference", "fact", "decision")
STATUSES = ("active", "archived", "deleted_by_user")


def _embed_dim() -> int:
    raw = os.environ.get("EMBED_DIM")
    if not raw or not raw.isdigit() or int(raw) <= 0:
        raise RuntimeError(
            "EMBED_DIM must be set to a positive integer to create memories.embedding"
        )
    return int(raw)


def upgrade() -> None:
    dim = _embed_dim()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "source_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column(
            "supersedes_id",
            UUID(as_uuid=True),
            sa.ForeignKey("memories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer, server_default=sa.text("0"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text, server_default=sa.text("'active'"), nullable=False),
        sa.CheckConstraint(f"kind IN {KINDS}", name="kind"),
        sa.CheckConstraint(f"status IN {STATUSES}", name="status"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
        sa.CheckConstraint("use_count >= 0", name="use_count"),
    )
    # Raw DDL: the vector dimension is not a portable column type (04a).
    op.execute(f"ALTER TABLE memories ADD COLUMN embedding vector({dim}) NOT NULL")
    op.create_index("ix_memories_owner", "memories", ["project_id", "user_id", "status"])

    op.create_table(
        "memory_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("allowed_kinds", ARRAY(sa.Text), nullable=False),
        sa.Column("max_items_per_user", sa.Integer, nullable=False),
        sa.Column("recall_top_k", sa.Integer, nullable=False),
        sa.Column("ttl_days", sa.Integer, nullable=True),
        sa.Column("extraction_model", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.Text, nullable=False),
        sa.CheckConstraint("max_items_per_user > 0", name="max_items"),
        sa.CheckConstraint("recall_top_k >= 0 AND recall_top_k <= 50", name="recall_top_k"),
        sa.CheckConstraint("ttl_days IS NULL OR ttl_days > 0", name="ttl_days"),
    )
    op.create_index(
        "uq_memory_settings_project",
        "memory_settings",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("agent_id IS NULL"),
    )
    op.create_index(
        "uq_memory_settings_agent",
        "memory_settings",
        ["project_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("agent_id IS NOT NULL"),
    )

    op.create_table(
        "memory_opt_outs",
        sa.Column(
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("memory_opt_outs")
    op.drop_index("uq_memory_settings_agent", table_name="memory_settings")
    op.drop_index("uq_memory_settings_project", table_name="memory_settings")
    op.drop_table("memory_settings")
    op.drop_index("ix_memories_owner", table_name="memories")
    op.drop_table("memories")
    # The vector extension stays (04a owns it).
