"""04b: chunks.sparse (bge-m3 lexical weights beside the dense vector)

Revision ID: 04b_0001
Revises: 05b_0001
Create Date: 2026-11-19

K-04B-0002 S2 A: the sparse weights are kept in Postgres like the dense vector, so a reused
vector carries them (no re-embedding on Qdrant) and `migrate-vectors` copies pgvector to Qdrant
without recomputing embeddings. Additive: a nullable jsonb column, existing rows stay NULL;
`migrate-vectors` computes the sparse weights of such a row only, and counts them.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "04b_0001"
down_revision = "05b_0001"
branch_labels = ("04b",)
depends_on = None


def upgrade() -> None:
    op.add_column("chunks", sa.Column("sparse", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("chunks", "sparse")
