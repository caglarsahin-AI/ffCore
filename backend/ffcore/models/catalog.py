"""providers, provider_projects, model_catalog, models (03a).

`providers` and `model_catalog` are tenant level (no project_id); `provider_projects` is a
link table; `models` is a project-owned root table with the C3 common columns.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

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
UPSTREAM_APIS = ("chat", "responses")
REASONING_LEVELS = ("none", "low", "medium", "high")
MODEL_KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


def litellm_name(project_key: str, model_key: str) -> str:
    """Virtual model name in LiteLLM: "<project_key>.<model_key>" (CONTRACTS C1)."""
    return f"{project_key}.{model_key}"


class Provider(Timestamps, Base):
    __tablename__ = "providers"
    __table_args__ = (
        CheckConstraint(f"driver IN {DRIVERS}", name="driver"),
        CheckConstraint(f"domains <@ ARRAY{list(DOMAINS)}::text[]", name="domains"),
        CheckConstraint("cardinality(domains) > 0", name="domains_not_empty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(Text, unique=True)
    label: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    driver: Mapped[str] = mapped_column(Text)
    domains: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # Fernet token of the JSON configuration (core/secrets.py); never returned as is.
    config_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    supports_test: Mapped[bool] = mapped_column(Boolean)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[str] = mapped_column(Text)


class ProviderProject(Base):
    __tablename__ = "provider_projects"
    __table_args__ = (Index("ix_provider_projects_project", "project_id"),)

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("providers.id"), primary_key=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True
    )


class ModelCatalogEntry(Base):
    __tablename__ = "model_catalog"
    __table_args__ = (
        UniqueConstraint("driver", "model_id", name="uq_model_catalog_driver_model"),
        CheckConstraint(f"driver IN {DRIVERS}", name="driver"),
        CheckConstraint(f"category IN {CATEGORIES}", name="category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    driver: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    capabilities: Mapped[dict] = mapped_column(JSONB)
    input_types: Mapped[list[str]] = mapped_column(ARRAY(Text))
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output: Mapped[int | None] = mapped_column(Integer)
    embed_dim: Mapped[int | None] = mapped_column(Integer)
    pricing: Mapped[dict] = mapped_column(JSONB)
    # Where the values come from and when they were checked (no unverified numbers, S6).
    source: Mapped[str] = mapped_column(Text)
    as_of: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Model(Timestamps, Base):
    __tablename__ = "models"
    __table_args__ = (
        CheckConstraint(f"key ~ '{MODEL_KEY_REGEX}'", name="key_format"),
        CheckConstraint(f"category IN {CATEGORIES}", name="category"),
        CheckConstraint(f"upstream_api IN {UPSTREAM_APIS}", name="upstream_api"),
        CheckConstraint(f"reasoning_default IN {REASONING_LEVELS}", name="reasoning_default"),
        CheckConstraint("embed_dim IS NULL OR embed_dim > 0", name="embed_dim_positive"),
        Index(
            "uq_models_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_models_provider", "provider_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id"))
    category: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    capabilities: Mapped[dict] = mapped_column(JSONB)
    input_types: Mapped[list[str]] = mapped_column(ARRAY(Text))
    pricing: Mapped[dict] = mapped_column(JSONB)
    limits: Mapped[dict] = mapped_column(JSONB)
    reasoning_default: Mapped[str | None] = mapped_column(Text)
    return_reasoning: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    upstream_api: Mapped[str] = mapped_column(Text)
    request_policy: Mapped[dict] = mapped_column(JSONB)
    embed_dim: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
