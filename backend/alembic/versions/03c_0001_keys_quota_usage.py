"""03c: API keys, quotas and daily usage

Revision ID: 03c_0001
Revises: 0001
Depends on: 03a_0001 (projects), 03b_0001 (audit_events)
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, JSONB, UUID

revision = "03c_0001"
down_revision = "0001"
branch_labels = ("03c",)
depends_on = ("03a_0001", "03b_0001")

# Frozen copies of the value lists at this revision.
API_KEY_SCOPES = ("chat_direct", "agents", "impersonate", "kb_search", "tools_invoke")
API_KEY_ACL_ROLES = ("analyst", "developer", "admin")
QUOTA_SCOPES = ("project", "api_key", "user")
QUOTA_ACTIONS = ("block", "warn")


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
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("key_prefix", sa.Text, nullable=False),
        sa.Column("key_hash", sa.Text, nullable=False),
        sa.Column("scopes", ARRAY(sa.Text), nullable=False),
        sa.Column("acl_role", sa.Text, server_default="analyst", nullable=False),
        sa.Column(
            "allowed_cidrs", ARRAY(CIDR), server_default=sa.text("'{}'::cidr[]"), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        *_common(),
        sa.CheckConstraint(
            "scopes <@ ARRAY[" + ", ".join(repr(s) for s in API_KEY_SCOPES) + "]::text[]",
            name="scopes",
        ),
        sa.CheckConstraint("cardinality(scopes) > 0", name="scopes_not_empty"),
        sa.CheckConstraint(_in("acl_role", API_KEY_ACL_ROLES), name="acl_role"),
        sa.CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name="key_hash_format"),
    )
    op.create_index("uq_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=True)
    op.create_index("ix_api_keys_project_created_by", "api_keys", ["project_id", "created_by"])
    # K-03c-0006: the key that impersonated the acting user; nullable, no FK (append-only table,
    # partitioned; a key row may be soft-deleted while its audit trail stays).
    op.add_column("audit_events", sa.Column("via_key_id", UUID(as_uuid=True)))

    op.create_table(
        "quotas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scope_type", sa.Text, nullable=False),
        sa.Column("scope_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, server_default="0", nullable=False),
        sa.Column("windows", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("tokens", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("budget", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("action", sa.Text, server_default="block", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("activate_at", sa.DateTime(timezone=True)),
        *_common(),
        sa.CheckConstraint(_in("scope_type", QUOTA_SCOPES), name="scope_type"),
        sa.CheckConstraint(_in("action", QUOTA_ACTIONS), name="action"),
    )
    op.create_index("ix_quotas_project_scope", "quotas", ["project_id", "scope_type", "scope_id"])

    # Reporting only (C20); one row per project, day, model, key and user, upserted per call.
    op.create_table(
        "usage_daily",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("model", sa.Text, nullable=False),
        sa.Column("api_key_id", UUID(as_uuid=True)),
        sa.Column("user_id", sa.Text),
        sa.Column("input_tokens", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("output_tokens", sa.BigInteger, server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(18, 8), server_default="0", nullable=False),
        sa.Column("requests", sa.BigInteger, server_default="0", nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_usage_daily_row ON usage_daily (project_id, date, model,"
        " coalesce(api_key_id, '00000000-0000-0000-0000-000000000000'::uuid),"
        " coalesce(user_id, ''))"
    )


def downgrade() -> None:
    op.drop_table("usage_daily")
    op.drop_table("quotas")
    op.drop_column("audit_events", "via_key_id")
    op.drop_table("api_keys")
