"""03c: API keys, quotas and daily usage

Revision ID: 03c_0001
Revises: 0001
Depends on: 03a_0001 (projects)
Create Date: 2026-10-31
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, UUID

revision = "03c_0001"
down_revision = "0001"
branch_labels = ("03c",)
depends_on = ("03a_0001",)

# Frozen copies of the value lists at this revision.
API_KEY_SCOPES = ("chat_direct", "agents", "impersonate", "kb_search", "tools_invoke")
API_KEY_ACL_ROLES = ("analyst", "developer", "admin")


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


def downgrade() -> None:
    op.drop_table("api_keys")
