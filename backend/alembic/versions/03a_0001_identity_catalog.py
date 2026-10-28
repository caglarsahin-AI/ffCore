"""03a: users, projects, project_members, providers, provider_projects, model_catalog, models

Revision ID: 03a_0001
Revises: 0001
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "03a_0001"
down_revision = "0001"
branch_labels = ("03a",)
depends_on = None

# Frozen copies of the value lists at this revision; later revisions change them explicitly.
ROLES = ("user", "analyst", "developer", "admin")
ACCESS_MODES = ("edit", "read")
DRIVERS = (
    "ollama",
    "vllm",
    "anthropic",
    "openai",
    "azure_openai",
    "bedrock",
    "openai_compatible",
    "local_flagembedding",
    "pgvector",
    "qdrant",
    "local_fs",
)
DOMAINS = ("model", "embedding", "vector", "file")
CATEGORIES = ("llm", "embedding", "stt", "tts", "ocr", "moderation")
PROJECT_KEY_REGEX = "^[a-z][a-z0-9-]{1,31}$"
MODEL_KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def _uuid_pk():
    return sa.Column("id", UUID(as_uuid=True), primary_key=True)


def _timestamps():
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        _uuid_pk(),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("is_superadmin", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("superadmin_access", sa.Text),
        sa.Column("token_version", sa.Integer, server_default="0", nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"superadmin_access IN {ACCESS_MODES}", name="superadmin_access"),
        sa.CheckConstraint(
            "NOT is_superadmin OR superadmin_access IS NOT NULL", name="superadmin_has_access"
        ),
    )
    op.create_index(
        "uq_users_email_live",
        "users",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "projects",
        _uuid_pk(),
        sa.Column("key", sa.Text, nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_by", sa.Text, nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"key ~ '{PROJECT_KEY_REGEX}'", name="key_format"),
    )

    op.create_table(
        "project_members",
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("access", sa.Text, nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"role IN {ROLES}", name="role"),
        sa.CheckConstraint(f"access IN {ACCESS_MODES}", name="access"),
    )
    op.create_index("ix_project_members_user", "project_members", ["user_id"])

    op.create_table(
        "providers",
        _uuid_pk(),
        sa.Column("key", sa.Text, nullable=False, unique=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("driver", sa.Text, nullable=False),
        sa.Column("domains", ARRAY(sa.Text), nullable=False),
        sa.Column("config_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("supports_test", sa.Boolean, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        *_timestamps(),
        sa.CheckConstraint(f"driver IN {DRIVERS}", name="driver"),
        sa.CheckConstraint(f"domains <@ ARRAY{list(DOMAINS)}::text[]", name="domains"),
        sa.CheckConstraint("cardinality(domains) > 0", name="domains_not_empty"),
    )

    op.create_table(
        "provider_projects",
        sa.Column(
            "provider_id", UUID(as_uuid=True), sa.ForeignKey("providers.id"), primary_key=True
        ),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
    )
    op.create_index("ix_provider_projects_project", "provider_projects", ["project_id"])

    op.create_table(
        "model_catalog",
        _uuid_pk(),
        sa.Column("driver", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("capabilities", JSONB, nullable=False),
        sa.Column("input_types", ARRAY(sa.Text), nullable=False),
        sa.Column("context_window", sa.Integer),
        sa.Column("max_output", sa.Integer),
        sa.Column("embed_dim", sa.Integer),
        sa.Column("pricing", JSONB, nullable=False),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("as_of", sa.Text, nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("driver", "model_id", name="uq_model_catalog_driver_model"),
        sa.CheckConstraint(f"driver IN {DRIVERS}", name="driver"),
        sa.CheckConstraint(f"category IN {CATEGORIES}", name="category"),
    )

    op.create_table(
        "models",
        _uuid_pk(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("providers.id"), nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("capabilities", JSONB, nullable=False),
        sa.Column("input_types", ARRAY(sa.Text), nullable=False),
        sa.Column("pricing", JSONB, nullable=False),
        sa.Column("limits", JSONB, nullable=False),
        sa.Column("reasoning_default", sa.Text),
        sa.Column("return_reasoning", sa.Boolean, server_default=sa.false(), nullable=False),
        sa.Column("upstream_api", sa.Text, nullable=False),
        sa.Column("request_policy", JSONB, nullable=False),
        sa.Column("embed_dim", sa.Integer),
        sa.Column("is_active", sa.Boolean, server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.Text, nullable=False),
        *_timestamps(),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"key ~ '{MODEL_KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint(f"category IN {CATEGORIES}", name="category"),
        sa.CheckConstraint("upstream_api IN ('chat', 'responses')", name="upstream_api"),
        sa.CheckConstraint(
            "reasoning_default IN ('none', 'low', 'medium', 'high')", name="reasoning_default"
        ),
        sa.CheckConstraint("embed_dim IS NULL OR embed_dim > 0", name="embed_dim_positive"),
    )
    op.create_index(
        "uq_models_project_key_live",
        "models",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_models_provider", "models", ["provider_id"])


def downgrade() -> None:
    for table in (
        "models",
        "model_catalog",
        "provider_projects",
        "providers",
        "project_members",
        "projects",
        "users",
    ):
        op.drop_table(table)
