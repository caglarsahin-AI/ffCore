"""05a: tools, tool_actions, schema_descriptions, few_shots

Revision ID: 05a_0001
Revises: 0001
Depends on: 03a_0001 (projects)
Create Date: 2026-10-29

`few_shots.embedding` is vector(EMBED_DIM) with EMBED_DIM read at migration time, as
`chunks.embedding` (04a): one embedding model per installation.
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "05a_0001"
down_revision = "0001"
branch_labels = ("05a",)
# The foreign keys need projects; without this the 05a branch could run before 03a.
depends_on = ("03a_0001",)

# Frozen copies of the value lists at this revision; later revisions change them explicitly.
TOOL_KINDS = ("mcp", "openapi")
AUTH_TYPES = ("none", "bearer", "header", "basic", "forward_user")
TOOL_STATUSES = ("registered", "discovered", "error")
ACTION_STATUSES = ("available", "missing")
KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def _embed_dim() -> int:
    raw = os.environ.get("EMBED_DIM")
    if not raw or not raw.isdigit() or int(raw) <= 0:
        raise RuntimeError("EMBED_DIM must be set to a positive integer to create few_shots")
    return int(raw)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _timestamps() -> list:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    dim = _embed_dim()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("endpoint_url", sa.Text, nullable=False),
        sa.Column("auth_type", sa.Text, nullable=False),
        sa.Column("auth_config_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("status", sa.Text, server_default="registered", nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.Text),
        sa.Column("created_by", sa.Text, nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(_in("kind", TOOL_KINDS), name="kind"),
        sa.CheckConstraint(_in("auth_type", AUTH_TYPES), name="auth_type"),
        sa.CheckConstraint(_in("status", TOOL_STATUSES), name="status"),
        sa.CheckConstraint(f"key ~ '{KEY_REGEX}'", name="key_format"),
    )
    op.create_index(
        "uq_tools_project_key_live",
        "tools",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "tool_actions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tool_id", UUID(as_uuid=True), sa.ForeignKey("tools.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("input_schema", JSONB, nullable=False),
        sa.Column("needs_approval", sa.Boolean, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("max_calls_per_run", sa.Integer),
        sa.Column("timeout_s", sa.Integer),
        sa.Column("status", sa.Text, server_default="available", nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("tool_id", "name", name="uq_tool_actions_tool_name"),
        sa.CheckConstraint(_in("status", ACTION_STATUSES), name="status"),
        sa.CheckConstraint("max_calls_per_run IS NULL OR max_calls_per_run > 0", name="max_calls"),
        sa.CheckConstraint("timeout_s IS NULL OR timeout_s BETWEEN 1 AND 600", name="timeout"),
    )

    op.create_table(
        "schema_descriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("table_name", sa.Text, nullable=False),
        sa.Column("column_name", sa.Text),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("sample_values", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("is_metric", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("formula", sa.Text),
        sa.Column("created_by", sa.Text, nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_schema_descriptions_live ON schema_descriptions"
        " (project_id, table_name, coalesce(column_name, '')) WHERE deleted_at IS NULL"
    )

    op.create_table(
        "few_shots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("sql", sa.Text, nullable=False),
        sa.Column("approved_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # Raw DDL: the vector dimension is not a portable column type.
    op.execute(f"ALTER TABLE few_shots ADD COLUMN embedding vector({dim}) NOT NULL")
    op.create_index("ix_few_shots_project", "few_shots", ["project_id"])


def downgrade() -> None:
    for table in ("few_shots", "schema_descriptions", "tool_actions", "tools"):
        op.drop_table(table)
