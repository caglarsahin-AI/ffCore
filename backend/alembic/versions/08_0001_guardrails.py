"""08: pii_policies, guardrail_policies, guardrail_events

Revision ID: 08_0001
Revises: 0001
Depends on: 03a_0001 (projects)
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "08_0001"
down_revision = "0001"
branch_labels = ("08",)
# The foreign keys need projects; without this the 08 branch could run before 03a.
depends_on = ("03a_0001",)

# Frozen copies of the value lists at this revision (C4); later revisions change them explicitly.
STAGES = (
    "prompt.pre",
    "input.pre",
    "output.pre",
    "output.stream.delta",
    "tool.pre",
    "tool.post",
    "egress",
)
ACTIONS = ("block", "redact", "mask", "tokenize", "warn", "log")
STATUSES = ("passed", "redacted", "failed")
MODES = ("off", "monitor", "enforce")
SOURCES = ("agent-playground", "chat", "api", "channel")
SEVERITIES = ("low", "medium", "high")
KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _common() -> list:
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
    ]


def _tail() -> list:
    return [
        sa.Column("is_default", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def _live_indexes(table: str) -> None:
    op.create_index(
        f"uq_{table}_project_key_live",
        table,
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        f"uq_{table}_project_default_live",
        table,
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )


def upgrade() -> None:
    op.create_table(
        "pii_policies",
        *_common(),
        sa.Column("engine", sa.Text, nullable=False),
        sa.Column("default_action", sa.Text, nullable=False),
        sa.Column("languages", ARRAY(sa.Text), nullable=False),
        sa.Column("min_confidence", sa.Float, nullable=False),
        sa.Column("context_boost", sa.Boolean, nullable=False),
        sa.Column("categories", JSONB, nullable=False),
        sa.Column("custom_patterns", JSONB, nullable=False),
        *_tail(),
        sa.CheckConstraint(f"key ~ '{KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint("engine IN ('regex', 'ner')", name="engine"),
        sa.CheckConstraint(_in("default_action", ACTIONS), name="default_action"),
        sa.CheckConstraint("min_confidence >= 0 AND min_confidence <= 1", name="min_confidence"),
    )
    _live_indexes("pii_policies")

    op.create_table(
        "guardrail_policies",
        *_common(),
        sa.Column("rules", JSONB, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("short_circuit", sa.Boolean, nullable=False),
        sa.Column("on_error", sa.Text, nullable=False),
        sa.Column("block_message", JSONB, nullable=False),
        *_tail(),
        sa.CheckConstraint(f"key ~ '{KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint(_in("mode", MODES), name="mode"),
        sa.CheckConstraint("on_error IN ('block', 'allow')", name="on_error"),
    )
    _live_indexes("guardrail_policies")

    op.create_table(
        "guardrail_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True)),
        sa.Column("reference_id", sa.Text),
        sa.Column("policy_key", sa.Text, nullable=False),
        sa.Column("stage", sa.Text, nullable=False),
        sa.Column("rule", sa.Text, nullable=False),
        sa.Column("action_taken", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("mode", sa.Text, nullable=False),
        sa.Column("input_preview", sa.Text, nullable=False),
        sa.Column("findings", JSONB, nullable=False),
        sa.Column("matches", JSONB, nullable=False),
        sa.Column("severity", sa.Text),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Float, nullable=False),
        sa.Column("error", sa.Text),
        sa.CheckConstraint(_in("stage", STAGES), name="stage"),
        sa.CheckConstraint(_in("action_taken", ACTIONS), name="action_taken"),
        sa.CheckConstraint(_in("status", STATUSES), name="status"),
        sa.CheckConstraint(_in("mode", MODES), name="mode"),
        sa.CheckConstraint(_in("source", SOURCES), name="source"),
        sa.CheckConstraint(f"severity IS NULL OR {_in('severity', SEVERITIES)}", name="severity"),
    )
    op.create_index("ix_guardrail_events_project_ts", "guardrail_events", ["project_id", "ts"])
    op.create_index("ix_guardrail_events_run", "guardrail_events", ["run_id"])


def downgrade() -> None:
    for table in ("guardrail_events", "guardrail_policies", "pii_policies"):
        op.drop_table(table)
