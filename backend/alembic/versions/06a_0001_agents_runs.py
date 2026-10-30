"""06a: agents, agent_versions, conversations, runs, messages, run_events; checkpoints schema

Revision ID: 06a_0001
Revises: 0001
Depends on: 03a_0001 (foreign keys to projects)
Create Date: 2026-10-29

The LangGraph checkpointer's tables live in the `checkpoints` schema. This revision creates and
drops the schema; the tables inside are created by `python -m ffcore.cli setup-checkpointer`
(the saver's own idempotent setup, run by the `migrate` service after `alembic upgrade`,
K-06a-0002 S12). Downgrading drops the schema with every checkpoint in it: waiting runs cannot
resume afterwards, so `runs abandon-pending` runs first (RELEASE_AND_ROLLBACK).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "06a_0001"
down_revision = "0001"
branch_labels = ("06a",)
depends_on = "03a_0001"

# Frozen copies of the value lists at this revision (C9); later revisions change them explicitly.
AGENT_KEY_REGEX = "^[a-z][a-z0-9_-]{0,63}$"
AGENT_STATUSES = ("draft", "published", "inactive")
AGENT_KINDS = ("native", "external")
RUN_STATUSES = (
    "queued",
    "running",
    "waiting_approval",
    "waiting_user",
    "completed",
    "failed",
    "cancelled",
    "abandoned",
)
RUN_CHANNELS = ("chat", "api", "test", "slack", "teams", "mattermost", "widget")
TRIGGER_TYPES = ("chat", "api", "schedule", "webhook")
OUTCOME_LABELS = ("answered", "declined", "below_threshold")
RUN_EVENT_TYPES = (
    "queued",
    "llm_call",
    "tool_call",
    "tool_result",
    "approval_requested",
    "approval_resolved",
    "question",
    "user_answer",
    "guardrail_hook",
    "budget",
    "progress",
    "memory_used",
    "sources",
    "answer",
    "fallback",
    "error",
    # 07 writes these (K-06a-0016): approval reused within its TTL, approval expired unanswered.
    "approval_reused",
    "approval_expired",
)
MESSAGE_ROLES = ("user", "assistant")
CHECKPOINT_SCHEMA = "checkpoints"


def _uuid_pk():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _now(name: str):
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _root_tail():
    return [
        _now("created_at"),
        _now("updated_at"),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def _project_fk():
    return sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "agents",
        _uuid_pk(),
        _project_fk(),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'draft'"), nullable=False),
        sa.Column("kind", sa.Text, server_default=sa.text("'native'"), nullable=False),
        sa.Column("current_version_id", UUID(as_uuid=True)),
        *_root_tail(),
        sa.CheckConstraint(f"key ~ '{AGENT_KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint(f"status IN {AGENT_STATUSES}", name="status"),
        sa.CheckConstraint(f"kind IN {AGENT_KINDS}", name="kind"),
        sa.CheckConstraint(
            "status <> 'published' OR current_version_id IS NOT NULL", name="published_has_version"
        ),
    )
    op.create_index(
        "uq_agents_project_key_live",
        "agents",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "agent_versions",
        _uuid_pk(),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("definition", JSONB, nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        _now("created_at"),
        _now("updated_at"),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("eval_run_id", UUID(as_uuid=True)),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
    )
    op.create_foreign_key(
        "fk_agents_current_version", "agents", "agent_versions", ["current_version_id"], ["id"]
    )

    op.create_table(
        "conversations",
        _uuid_pk(),
        _project_fk(),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("title", sa.Text, server_default=sa.text("''"), nullable=False),
        *_root_tail(),
    )

    op.create_table(
        "runs",
        _uuid_pk(),
        _project_fk(),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id"), nullable=False),
        sa.Column(
            "agent_version_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_versions.id"),
            nullable=False,
        ),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("user_id", UUID(as_uuid=True)),
        sa.Column("api_key_id", UUID(as_uuid=True)),
        sa.Column("channel", sa.Text, nullable=False),
        sa.Column("trigger_type", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'queued'"), nullable=False),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("variables", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("output", sa.Text),
        sa.Column("partial", sa.Boolean, server_default=sa.text("false"), nullable=False),
        sa.Column("error_code", sa.Text),
        sa.Column("reference_id", UUID(as_uuid=True)),
        sa.Column("confidence", sa.Float),
        sa.Column("confidence_formulas", JSONB),
        sa.Column("outcome_label", sa.Text),
        sa.Column("tokens_in", sa.Integer),
        sa.Column("tokens_out", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(14, 6)),
        sa.Column("langfuse_trace_id", sa.Text),
        sa.Column("model_ms", sa.Integer),
        sa.Column("tool_ms", sa.Integer),
        sa.Column("retrieval_ms", sa.Integer),
        sa.Column("unaccounted_ms", sa.Integer),
        sa.Column("slowest_step", sa.Text),
        sa.Column("queue_wait_ms", sa.Integer),
        _now("queued_at"),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        *_root_tail(),
        sa.CheckConstraint(f"status IN {RUN_STATUSES}", name="status"),
        sa.CheckConstraint(f"channel IN {RUN_CHANNELS}", name="channel"),
        sa.CheckConstraint(f"trigger_type IN {TRIGGER_TYPES}", name="trigger_type"),
        sa.CheckConstraint(
            f"outcome_label IS NULL OR outcome_label IN {OUTCOME_LABELS}", name="outcome_label"
        ),
    )
    op.create_index("ix_runs_project_queued", "runs", ["project_id", "queued_at"])
    op.create_index("ix_runs_agent", "runs", ["agent_id"])

    op.create_table(
        "messages",
        _uuid_pk(),
        sa.Column(
            "conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False
        ),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id")),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", JSONB),
        sa.Column("feedback", JSONB),
        _now("created_at"),
        sa.CheckConstraint(f"role IN {MESSAGE_ROLES}", name="role"),
    )
    op.create_index("ix_messages_conversation", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "run_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False),
        sa.Column("seq", sa.Integer, nullable=False),
        _now("ts"),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("iteration", sa.Integer),
        sa.Column("payload", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),
        sa.CheckConstraint(f"type IN {RUN_EVENT_TYPES}", name="type"),
    )

    op.execute(f"CREATE SCHEMA IF NOT EXISTS {CHECKPOINT_SCHEMA}")


def downgrade() -> None:
    op.execute(f"DROP SCHEMA IF EXISTS {CHECKPOINT_SCHEMA} CASCADE")
    op.drop_table("run_events")
    op.drop_table("messages")
    op.drop_table("runs")
    op.drop_table("conversations")
    op.drop_constraint("fk_agents_current_version", "agents", type_="foreignkey")
    op.drop_table("agent_versions")
    op.drop_table("agents")
