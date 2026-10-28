"""knowledge_bases, documents, attachments, chunks, kb_queries (04a).

`knowledge_bases` and `documents` are project-owned root tables (C3 common columns);
`attachments` and `chunks` are child tables (project through `document_id`/`kb_id`);
`kb_queries` is append-only. `chunks.embedding` holds the pgvector copy of the dense vector:
its dimension is EMBED_DIM at migration time (one model per installation, P5).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy import text as sql_text  # `text` is also a column name of chunks
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

KB_KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"
KB_STATUSES = ("active", "reindexing")
DOCUMENT_STATUSES = (
    "pending",
    "converting",
    "gated",
    "chunking",
    "embedding",
    "indexed",
    "skipped",
    "failed",
    "timeout",
)
GATE_STATUSES = ("ok", "flagged", "skipped")
CHUNK_STATUSES = ("ok", "flagged", "skipped")
# Chunks the search may return (brief 04: only ok and flagged).
SEARCHABLE_CHUNK_STATUSES = ("ok", "flagged")
# Postgres text search configuration of chunks.tsv (brief 04 technical notes).
TSV_CONFIG = "turkish"


def _gate_columns(prefix: str):
    return (
        mapped_column(f"{prefix}_status", Text, nullable=True),
        mapped_column(f"{prefix}_reason", Text, nullable=True),
    )


class KnowledgeBase(Timestamps, Base):
    __tablename__ = "knowledge_bases"
    __table_args__ = (
        CheckConstraint(f"key ~ '{KB_KEY_REGEX}'", name="key_format"),
        CheckConstraint(f"status IN {KB_STATUSES}", name="status"),
        CheckConstraint("chunk_strategy = 'heading'", name="chunk_strategy"),
        CheckConstraint("chunk_size > 0 AND chunk_overlap >= 0", name="chunk_sizes"),
        Index(
            "uq_knowledge_bases_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=sql_text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    # Record of the installation's model; must equal EMBED_MODEL/EMBED_DIM (P5).
    embed_model: Mapped[str] = mapped_column(Text)
    embed_dim: Mapped[int] = mapped_column(Integer)
    chunk_strategy: Mapped[str] = mapped_column(Text, server_default=sql_text("'heading'"))
    chunk_size: Mapped[int] = mapped_column(Integer)
    chunk_overlap: Mapped[int] = mapped_column(Integer)
    hybrid: Mapped[bool] = mapped_column(Boolean)
    rerank: Mapped[bool] = mapped_column(Boolean)
    rerank_model: Mapped[str] = mapped_column(Text)
    default_top_k: Mapped[int] = mapped_column(Integer)
    default_min_score: Mapped[float | None] = mapped_column(Float)
    default_filter: Mapped[dict] = mapped_column(JSONB, server_default=sql_text("'{}'::jsonb"))
    normalizer_config_id: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'active'"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Timestamps, Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="status"),
        *(
            CheckConstraint(f"{gate}_status IS NULL OR {gate}_status IN {GATE_STATUSES}", name=gate)
            for gate in ("gate0", "gate1", "gate2")
        ),
        # One live document per file name in a KB: a re-upload is a new version (brief 04).
        Index(
            "uq_documents_kb_filename_live",
            "kb_id",
            "filename",
            unique=True,
            postgresql_where=sql_text("deleted_at IS NULL"),
        ),
        Index("ix_documents_kb_sha256", "kb_id", "sha256"),
        Index("ix_documents_kb_text_hash", "kb_id", "text_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"))
    filename: Mapped[str] = mapped_column(Text)
    mime_sniffed: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)
    raw_path: Mapped[str] = mapped_column(Text)
    silver_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'pending'"))
    error: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    acl_roles: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sql_text("'{}'"))
    acl_users: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=sql_text("'{}'")
    )
    # "metadata" is reserved on declarative classes; the column keeps the brief's name.
    meta: Mapped[dict] = mapped_column("metadata", JSONB, server_default=sql_text("'{}'::jsonb"))
    version: Mapped[int] = mapped_column(Integer, server_default=sql_text("1"))
    source_item_id: Mapped[str | None] = mapped_column(Text)
    breadcrumb: Mapped[str | None] = mapped_column(Text)
    updated_at_source: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str | None] = mapped_column(Text)
    text_hash: Mapped[str | None] = mapped_column(Text)
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id")
    )
    gate0_status, gate0_reason = _gate_columns("gate0")
    gate1_status, gate1_reason = _gate_columns("gate1")
    gate2_status, gate2_reason = _gate_columns("gate2")
    convert_engine: Mapped[str | None] = mapped_column(Text)
    convert_seconds: Mapped[float | None] = mapped_column(Float)
    normalizer_config_id: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Attachment(Timestamps, Base):
    __tablename__ = "attachments"
    __table_args__ = (
        *(
            CheckConstraint(f"{gate}_status IS NULL OR {gate}_status IN {GATE_STATUSES}", name=gate)
            for gate in ("gate0", "gate2")
        ),
        Index("ix_attachments_document", "document_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    filename: Mapped[str] = mapped_column(Text)
    mime_sniffed: Mapped[str | None] = mapped_column(Text)
    size: Mapped[int] = mapped_column(BigInteger)
    raw_path: Mapped[str] = mapped_column(Text)
    silver_path: Mapped[str | None] = mapped_column(Text)
    gate0_status, gate0_reason = _gate_columns("gate0")
    gate2_status, gate2_reason = _gate_columns("gate2")
    convert_engine: Mapped[str | None] = mapped_column(Text)
    convert_seconds: Mapped[float | None] = mapped_column(Float)
    shared_from: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("attachments.id")
    )


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint(f"chunk_status IN {CHUNK_STATUSES}", name="chunk_status"),
        Index("ix_chunks_document", "document_id"),
        Index("ix_chunks_kb_text_hash", "kb_id", "text_hash", "embedding_model"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"))
    ordinal: Mapped[int] = mapped_column(Integer)
    # Embedded text: breadcrumb + body (brief 04 D5). The hash is over the same text.
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)
    char_count: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(Text)
    breadcrumb: Mapped[str] = mapped_column(Text)
    # The column is vector(EMBED_DIM) in the migration; the ORM type needs no dimension, so
    # importing the models does not depend on settings.
    embedding = mapped_column(Vector(), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    tsv = mapped_column(TSVECTOR, Computed(f"to_tsvector('{TSV_CONFIG}', text)", persisted=True))
    chunk_status: Mapped[str] = mapped_column(Text, server_default=sql_text("'ok'"))
    chunk_reason: Mapped[str | None] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KbQuery(Base):
    """Append-only search log (C12): candidates are the hybrid top-N with both scores."""

    __tablename__ = "kb_queries"
    __table_args__ = (
        Index("ix_kb_queries_kb_ts", "kb_id", "ts"),
        Index("ix_kb_queries_run", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kb_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_bases.id"))
    query: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, server_default=sql_text("'api'"))
    normalizer_config_id: Mapped[str] = mapped_column(Text)
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    candidates: Mapped[list] = mapped_column(JSONB)
    best_embed_score: Mapped[float | None] = mapped_column(Float)
    best_rerank_score: Mapped[float | None] = mapped_column(Float)
    returned: Mapped[int] = mapped_column(Integer)
    threshold_mode: Mapped[str] = mapped_column(Text)
    filtered_by_rerank_floor: Mapped[int] = mapped_column(Integer)
    filtered_by_min_score: Mapped[int] = mapped_column(Integer)
    latency_ms: Mapped[int] = mapped_column(Integer)
    user_id: Mapped[str | None] = mapped_column(Text)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
