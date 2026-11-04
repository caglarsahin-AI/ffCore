"""09: eval_suites, eval_runs (local rows over Langfuse datasets and dataset runs)

Revision ID: 09_0001
Revises: 06b_0001
Create Date: 2026-11-04

Datasets and items are not stored here (A5, ARCH-09). Downgrade drops both tables; the
Langfuse datasets, dataset runs and scores stay where they are.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "09_0001"
down_revision = "06b_0001"
branch_labels = ("09",)
depends_on = None

# Frozen copies of the value lists at this revision.
EVAL_RUN_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
SUITE_KEY_REGEX = "^[a-z0-9][a-z0-9-]{0,62}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _common() -> list[sa.Column]:
    return [
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    op.create_table(
        "eval_suites",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id")),
        sa.Column("langfuse_dataset_name", sa.Text, nullable=False),
        sa.Column("scorers", JSONB, nullable=False),
        sa.Column("pass_threshold", sa.Float, nullable=False),
        sa.Column("repeat", sa.Integer, server_default="1", nullable=False),
        sa.Column("approve_tools", sa.Boolean, server_default=sa.false(), nullable=False),
        *_common(),
        sa.CheckConstraint(f"key ~ '{SUITE_KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint("pass_threshold > 0 AND pass_threshold <= 1", name="pass_threshold"),
        sa.CheckConstraint("repeat >= 1 AND repeat <= 10", name="repeat"),
    )
    op.create_index(
        "uq_eval_suites_project_key_live",
        "eval_suites",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_eval_suites_agent", "eval_suites", ["agent_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("suite_id", UUID(as_uuid=True), sa.ForeignKey("eval_suites.id"), nullable=False),
        sa.Column(
            "agent_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id"),
            nullable=False,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("langfuse_run_name", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default="queued", nullable=False),
        sa.Column("error_code", sa.Text),
        sa.Column("item_runs", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        # The suite as the exam started (scorers, threshold, repeat, approve_tools, dataset,
        # starter): the advancer and the summary read only this (09-1 r1 MAJOR-4).
        sa.Column("config", JSONB, nullable=False),
        sa.Column("summary", JSONB),
        sa.Column("cost_usd", sa.Numeric(14, 6)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        *_common(),
        sa.CheckConstraint(_in("status", EVAL_RUN_STATUSES), name="status"),
    )
    op.create_index("ix_eval_runs_suite", "eval_runs", ["suite_id", "created_at"])
    op.create_index(
        "ix_eval_runs_active",
        "eval_runs",
        ["status"],
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("eval_runs")
    op.drop_table("eval_suites")
