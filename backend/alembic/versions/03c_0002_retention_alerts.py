"""03c: retention policies and runs, alerts, notification settings

Revision ID: 03c_0002
Revises: 03c_0001
Depends on: 06a_0002 (runs), 07_0001 (approvals: cleared by retention)
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "03c_0002"
down_revision = "03c_0001"
branch_labels = None
depends_on = ("06a_0002", "07_0001")

# Frozen copy of the brief's single class list (R2.2) at this revision.
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
RUN_TRIGGERS = ("dry_run", "schedule", "manual", "document_delete")
RUN_STATUSES = ("ok", "partial", "failed")


def _in(column: str, values) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "retention_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("data_class", sa.Text, nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id")),
        sa.Column("keep_days", sa.Integer, nullable=False),
        sa.Column("min_days", sa.Integer, nullable=False),
        sa.Column("max_days", sa.Integer, nullable=False),
        sa.Column("expiry_behavior", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.Text, server_default="migration", nullable=False),
        sa.CheckConstraint(_in("data_class", RETENTION_CLASSES), name="data_class"),
        sa.CheckConstraint(
            _in("expiry_behavior", ("delete", "clear_content")), name="expiry_behavior"
        ),
        sa.CheckConstraint("keep_days BETWEEN min_days AND max_days", name="keep_in_range"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_retention_policies_class_project ON retention_policies"
        " (data_class, coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid))"
    )
    for name, (keep, low, high, behavior) in RETENTION_CLASSES.items():
        op.execute(
            sa.text(
                "INSERT INTO retention_policies (id, data_class, keep_days, min_days, max_days,"
                " expiry_behavior) VALUES (gen_random_uuid(), :n, :k, :lo, :hi, :b)"
            ).bindparams(n=name, k=keep, lo=low, hi=high, b=behavior)
        )

    op.create_table(
        "retention_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("data_class", sa.Text, nullable=False),
        sa.Column("project_id", UUID(as_uuid=True)),
        sa.Column("trigger", sa.Text, nullable=False),
        sa.Column("dry_run", sa.Boolean, nullable=False),
        sa.Column("cutoff", sa.DateTime(timezone=True)),
        sa.Column("counts", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.Text, server_default="ok", nullable=False),
        sa.Column("error_code", sa.Text),
        sa.Column("actor_id", sa.Text, nullable=False),
        sa.CheckConstraint(_in("trigger", RUN_TRIGGERS), name="trigger"),
        sa.CheckConstraint(_in("status", RUN_STATUSES), name="status"),
    )
    op.create_index("ix_retention_runs_ts", "retention_runs", ["ts"])
    # Append-only like audit_events (K-03c-0004 condition 7): the record of what was removed
    # cannot itself be removed or rewritten.
    op.execute(
        """
        CREATE FUNCTION ffcore_retention_runs_append_only() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'retention_runs is append-only';
        END $$;
        CREATE TRIGGER retention_runs_no_update_delete
            BEFORE UPDATE OR DELETE ON retention_runs
            FOR EACH ROW EXECUTE FUNCTION ffcore_retention_runs_append_only();
        CREATE TRIGGER retention_runs_no_truncate
            BEFORE TRUNCATE ON retention_runs
            FOR EACH STATEMENT EXECUTE FUNCTION ffcore_retention_runs_append_only();
        REVOKE UPDATE, DELETE, TRUNCATE ON retention_runs FROM PUBLIC;
        """
    )

    # FOLLOWUP-119: the run's text was cleared (a second pass is a no-op).
    op.add_column("runs", sa.Column("content_cleared_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("runs", "content_cleared_at")
    op.execute("DROP TABLE retention_runs")
    op.execute("DROP FUNCTION ffcore_retention_runs_append_only()")
    op.drop_table("retention_policies")
