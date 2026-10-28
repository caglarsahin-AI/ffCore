"""04a: knowledge_bases, documents, attachments, chunks, kb_queries, ingest_gate_stats

Revision ID: 04a_0001
Revises: 0001
Depends on: 03a_0001 (foreign keys to projects)
Create Date: 2026-10-28

`chunks.embedding` is vector(EMBED_DIM) with EMBED_DIM read at migration time: one embedding
model per installation (P5). Changing EMBED_DIM later needs a new migration and a gold reindex;
/readyz reports a mismatch between the column and EMBED_DIM (never silently ignored).
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

revision = "04a_0001"
down_revision = "0001"
branch_labels = ("04a",)
depends_on = "03a_0001"

# Frozen copies of the value lists at this revision; later revisions change them explicitly.
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
TSV_CONFIG = "turkish"


def _embed_dim() -> int:
    raw = os.environ.get("EMBED_DIM")
    if not raw or not raw.isdigit() or int(raw) <= 0:
        raise RuntimeError("EMBED_DIM must be set to a positive integer to create chunks.embedding")
    return int(raw)


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


def _gate(prefix: str):
    return [
        sa.Column(f"{prefix}_status", sa.Text, nullable=True),
        sa.Column(f"{prefix}_reason", sa.Text, nullable=True),
        sa.CheckConstraint(
            f"{prefix}_status IS NULL OR {prefix}_status IN {GATE_STATUSES}", name=prefix
        ),
    ]


def upgrade() -> None:
    dim = _embed_dim()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "knowledge_bases",
        _uuid_pk(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("key", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("embed_model", sa.Text, nullable=False),
        sa.Column("embed_dim", sa.Integer, nullable=False),
        sa.Column("chunk_strategy", sa.Text, server_default=sa.text("'heading'"), nullable=False),
        sa.Column("chunk_size", sa.Integer, nullable=False),
        sa.Column("chunk_overlap", sa.Integer, nullable=False),
        sa.Column("hybrid", sa.Boolean, nullable=False),
        sa.Column("rerank", sa.Boolean, nullable=False),
        sa.Column("rerank_model", sa.Text, nullable=False),
        sa.Column("default_top_k", sa.Integer, nullable=False),
        sa.Column("default_min_score", sa.Float),
        sa.Column("default_filter", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("normalizer_config_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, server_default=sa.text("'active'"), nullable=False),
        *_timestamps(),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"key ~ '{KB_KEY_REGEX}'", name="key_format"),
        sa.CheckConstraint(f"status IN {KB_STATUSES}", name="status"),
        sa.CheckConstraint("chunk_strategy = 'heading'", name="chunk_strategy"),
        sa.CheckConstraint("chunk_size > 0 AND chunk_overlap >= 0", name="chunk_sizes"),
    )
    op.create_index(
        "uq_knowledge_bases_project_key_live",
        "knowledge_bases",
        ["project_id", "key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "documents",
        _uuid_pk(),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kb_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("mime_sniffed", sa.Text),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column("raw_path", sa.Text, nullable=False),
        sa.Column("silver_path", sa.Text),
        sa.Column("status", sa.Text, server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("page_count", sa.Integer),
        sa.Column("acl_roles", ARRAY(sa.Text), server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "acl_users", ARRAY(UUID(as_uuid=True)), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("version", sa.Integer, server_default=sa.text("1"), nullable=False),
        sa.Column("source_item_id", sa.Text),
        sa.Column("breadcrumb", sa.Text),
        sa.Column("updated_at_source", sa.DateTime(timezone=True)),
        sa.Column("language", sa.Text),
        sa.Column("text_hash", sa.Text),
        sa.Column("duplicate_of", UUID(as_uuid=True), sa.ForeignKey("documents.id")),
        *_gate("gate0"),
        *_gate("gate1"),
        *_gate("gate2"),
        sa.Column("convert_engine", sa.Text),
        sa.Column("convert_seconds", sa.Float),
        sa.Column("normalizer_config_id", sa.Text),
        *_timestamps(),
        sa.Column("created_by", sa.Text, nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(f"status IN {DOCUMENT_STATUSES}", name="status"),
    )
    op.create_index(
        "uq_documents_kb_filename_live",
        "documents",
        ["kb_id", "filename"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_documents_kb_sha256", "documents", ["kb_id", "sha256"])
    op.create_index("ix_documents_kb_text_hash", "documents", ["kb_id", "text_hash"])

    op.create_table(
        "attachments",
        _uuid_pk(),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.Text, nullable=False),
        sa.Column("mime_sniffed", sa.Text),
        sa.Column("size", sa.BigInteger, nullable=False),
        sa.Column("raw_path", sa.Text, nullable=False),
        sa.Column("silver_path", sa.Text),
        *_gate("gate0"),
        *_gate("gate2"),
        sa.Column("convert_engine", sa.Text),
        sa.Column("convert_seconds", sa.Float),
        sa.Column("shared_from", UUID(as_uuid=True), sa.ForeignKey("attachments.id")),
        *_timestamps(),
    )
    op.create_index("ix_attachments_document", "attachments", ["document_id"])

    op.create_table(
        "chunks",
        _uuid_pk(),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kb_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("ordinal", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("char_count", sa.Integer, nullable=False),
        sa.Column("page", sa.Integer),
        sa.Column("section_path", sa.Text),
        sa.Column("breadcrumb", sa.Text, nullable=False),
        sa.Column("embedding_model", sa.Text),
        sa.Column("chunk_status", sa.Text, server_default=sa.text("'ok'"), nullable=False),
        sa.Column("chunk_reason", sa.Text),
        sa.Column("text_hash", sa.Text, nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(f"chunk_status IN {CHUNK_STATUSES}", name="chunk_status"),
    )
    # Raw DDL: the vector dimension and the generated tsvector are not portable column types.
    op.execute(f"ALTER TABLE chunks ADD COLUMN embedding vector({dim})")
    op.execute(
        f"ALTER TABLE chunks ADD COLUMN tsv tsvector "
        f"GENERATED ALWAYS AS (to_tsvector('{TSV_CONFIG}', text)) STORED"
    )
    op.create_index("ix_chunks_document", "chunks", ["document_id"])
    op.create_index("ix_chunks_kb_text_hash", "chunks", ["kb_id", "text_hash", "embedding_model"])
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv)")

    op.create_table(
        "kb_queries",
        _uuid_pk(),
        sa.Column("kb_id", UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id"), nullable=False),
        sa.Column("query", sa.Text, nullable=False),
        sa.Column("source", sa.Text, server_default=sa.text("'api'"), nullable=False),
        sa.Column("normalizer_config_id", sa.Text, nullable=False),
        sa.Column("run_id", UUID(as_uuid=True)),
        sa.Column("candidates", JSONB, nullable=False),
        sa.Column("best_embed_score", sa.Float),
        sa.Column("best_rerank_score", sa.Float),
        sa.Column("returned", sa.Integer, nullable=False),
        sa.Column("threshold_mode", sa.Text, nullable=False),
        sa.Column("filtered_by_rerank_floor", sa.Integer, nullable=False),
        sa.Column("filtered_by_min_score", sa.Integer, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Text),
        sa.Column("ts", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "threshold_mode IN ('rerank_floor', 'min_score')", name="threshold_mode"
        ),
    )
    op.create_index("ix_kb_queries_kb_ts", "kb_queries", ["kb_id", "ts"])
    op.create_index("ix_kb_queries_run", "kb_queries", ["run_id"])

    # Source x gate x reason counts (report screen in 04b/10). Every document appears once per
    # gate column, so per gate the counts add up to the number of live documents (brief D1).
    op.execute(
        """
        CREATE VIEW ingest_gate_stats AS
        SELECT d.project_id, d.kb_id,
               COALESCE(d.metadata->>'source', 'upload') AS source,
               g.gate, g.status, g.reason, count(*) AS documents
        FROM documents d
        CROSS JOIN LATERAL (VALUES
            ('gate0', d.gate0_status, d.gate0_reason),
            ('gate1', d.gate1_status, d.gate1_reason),
            ('gate2', d.gate2_status, d.gate2_reason)
        ) AS g(gate, status, reason)
        WHERE d.deleted_at IS NULL
        GROUP BY d.project_id, d.kb_id, source, g.gate, g.status, g.reason
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS ingest_gate_stats")
    op.drop_table("kb_queries")
    op.drop_table("chunks")
    op.drop_table("attachments")
    op.drop_table("documents")
    op.drop_table("knowledge_bases")
    # The vector extension stays: other packages (05 few-shots, 14 memory) use it too.
