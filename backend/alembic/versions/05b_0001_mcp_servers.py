"""05b: published MCP servers (mcp_servers) and their calls (mcp_server_calls)

Revision ID: 05b_0001
Revises: 09_0001
Create Date: 2026-11-17

K-05B-0002: an OpenAPI document or a remote MCP server published under `/mcp/{key}/`. The key is
unique across the installation (live rows). The document and the upstream identity are Fernet
tokens. mcp_server_calls is a C3 child table of mcp_servers (one row per tools/call; no
arguments or results). Additive only: no existing table changes.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "05b_0001"
down_revision = "09_0001"
branch_labels = ("05b",)
depends_on = None

# Frozen copies of the value lists at this revision; later revisions change them explicitly.
SOURCE_KINDS = ("openapi", "remote_mcp")
UPSTREAM_AUTH_TYPES = ("none", "bearer", "header", "basic")
SERVER_ACCESS = ("token", "internal")
GUARDRAIL_MODES = ("off", "monitor", "enforce")
SERVER_STATUSES = ("draft", "active", "disabled")
CALL_STATUSES = ("ok", "error", "blocked", "denied")
KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def upgrade() -> None:
    op.create_table(
        "mcp_servers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("source_kind", sa.Text, nullable=False),
        sa.Column("spec_encrypted", sa.LargeBinary),
        sa.Column("upstream_base_url", sa.Text, nullable=False),
        sa.Column("upstream_auth_type", sa.Text, nullable=False),
        sa.Column("upstream_auth_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("operations", JSONB, server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "exposed_operations",
            ARRAY(sa.Text),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "protocols",
            ARRAY(sa.Text),
            server_default=sa.text("'{streamable_http}'::text[]"),
            nullable=False,
        ),
        sa.Column("access", sa.Text, server_default="internal", nullable=False),
        sa.Column("guardrail_mode", sa.Text, server_default="monitor", nullable=False),
        sa.Column("guardrail_policy_key", sa.Text, server_default="default", nullable=False),
        sa.Column("status", sa.Text, server_default="draft", nullable=False),
        sa.Column("discovered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.Text),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(_in("source_kind", SOURCE_KINDS), name="source_kind"),
        sa.CheckConstraint(
            _in("upstream_auth_type", UPSTREAM_AUTH_TYPES), name="upstream_auth_type"
        ),
        sa.CheckConstraint(_in("access", SERVER_ACCESS), name="access"),
        sa.CheckConstraint(_in("guardrail_mode", GUARDRAIL_MODES), name="guardrail_mode"),
        sa.CheckConstraint(_in("status", SERVER_STATUSES), name="status"),
        sa.CheckConstraint(f"key ~ '{KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint(
            "(source_kind = 'openapi' AND spec_encrypted IS NOT NULL)"
            " OR (source_kind <> 'openapi' AND spec_encrypted IS NULL)",
            name="spec_for_openapi",
        ),
    )
    op.create_index(
        "uq_mcp_servers_key_live",
        "mcp_servers",
        ["key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "mcp_server_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "server_id",
            UUID(as_uuid=True),
            sa.ForeignKey("mcp_servers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operation", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("error_code", sa.Text),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True)),
        sa.Column("actor_type", sa.Text, nullable=False),
        sa.Column("actor_id", sa.Text, nullable=False),
        sa.Column("guardrail_action", sa.Text),
        sa.CheckConstraint(_in("status", CALL_STATUSES), name="status"),
    )
    op.create_index(
        "ix_mcp_server_calls_server_ts", "mcp_server_calls", ["server_id", sa.text("ts DESC")]
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_server_calls_server_ts", table_name="mcp_server_calls")
    op.drop_table("mcp_server_calls")
    op.drop_index("uq_mcp_servers_key_live", table_name="mcp_servers")
    op.drop_table("mcp_servers")
