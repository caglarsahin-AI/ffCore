"""11-2: the end user's vote on an answer and an agent's chat portal settings

Revision ID: 11_0001
Revises: 12_0002
Create Date: 2026-11-21

- `messages.user_feedback jsonb NULL`: the chat user's vote (`POST .../feedback` with
  `source: chat`). It sits beside `messages.feedback`, the expert's review (F9), so a user's vote
  neither takes the run out of the review queue nor is overwritten by the expert (K-11-0005 S1).
- `agents.portal_config jsonb NULL`: welcome text, up to three example questions and an accent
  colour for the chat (S2). Agent level, not versioned; validated by the API schema.

Additive: two nullable columns, no data change.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "11_0001"
down_revision = "12_0002"
branch_labels = ("11",)
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("user_feedback", JSONB(), nullable=True))
    op.add_column("agents", sa.Column("portal_config", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "portal_config")
    op.drop_column("messages", "user_feedback")
