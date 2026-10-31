"""06a: when a run's checkpoint was deleted, and when a source of a live run was deleted

Revision ID: 06a_0002
Revises: 06a_0001
Create Date: 2026-10-31

FOLLOWUP-116 (K-116-0002): a finished run's LangGraph thread is deleted (the chunk text it
carries must not outlive the run). `checkpoint_deleted_at` says it was done, so the sweep tries
again where it is NULL; `source_deleted_at` is set by the document delete on runs that are
still live and showed that document as a source, so they end `source_deleted` instead of going
on with deleted text. Both are nullable additions; runs that ended before this revision have a
NULL `checkpoint_deleted_at` and their threads are deleted by the first sweeps.
"""

import sqlalchemy as sa
from alembic import op

revision = "06a_0002"
down_revision = "06a_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("checkpoint_deleted_at", sa.DateTime(timezone=True)))
    op.add_column("runs", sa.Column("source_deleted_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_runs_checkpoint_pending",
        "runs",
        ["ended_at"],
        postgresql_where=sa.text("checkpoint_deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_runs_checkpoint_pending", table_name="runs")
    op.drop_column("runs", "source_deleted_at")
    op.drop_column("runs", "checkpoint_deleted_at")
