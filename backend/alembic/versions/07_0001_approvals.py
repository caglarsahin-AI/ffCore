"""07: approvals

Revision ID: 07_0001
Revises: 0001
Depends on: 03a_0001 (projects), 06a_0001 (runs)
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "07_0001"
down_revision = "0001"
branch_labels = ("07",)
depends_on = ("03a_0001", "06a_0001")

# Frozen copies of the value lists at this revision.
APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired")
APPROVER_ROLES = ("analyst", "developer", "admin")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("tool_call_id", sa.Text, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("arguments", JSONB, nullable=False),
        sa.Column("args_hash", sa.Text, nullable=False),
        sa.Column("reason_from_model", sa.Text),
        sa.Column("status", sa.Text, server_default="pending", nullable=False),
        sa.Column("assigned_role", sa.Text, nullable=False),
        sa.Column(
            "requested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_by", sa.Text),
        sa.Column("resolution_note", sa.Text),
        sa.Column("age_reported_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(_in("status", APPROVAL_STATUSES), name="status"),
        sa.CheckConstraint(_in("assigned_role", APPROVER_ROLES), name="assigned_role"),
        sa.CheckConstraint(
            "(status = 'pending') = (resolved_at IS NULL)", name="resolved_at_matches_status"
        ),
        sa.CheckConstraint("args_hash ~ '^[0-9a-f]{64}$'", name="args_hash_format"),
    )
    op.create_index(
        "uq_approvals_run_tool_call", "approvals", ["run_id", "tool_call_id"], unique=True
    )
    op.create_index(
        "ix_approvals_pending_expires_at",
        "approvals",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index("ix_approvals_project_status", "approvals", ["project_id", "status"])


def downgrade() -> None:
    op.drop_table("approvals")
