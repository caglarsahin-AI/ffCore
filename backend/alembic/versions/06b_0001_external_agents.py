"""06b-2: external agents (kind = external) keep their endpoint in agents.external_config

Revision ID: 06b_0001
Revises: 57_0002
Create Date: 2026-11-02

K-06b2-0002: an external agent is an OpenAI-compatible agent elsewhere; its base URL, remote
model and API key are one Fernet token in `agents.external_config` (nullable; set exactly when
kind = external). It has no versions (no C8 definition), so a published external agent is
exempt from `published_has_version`. Downgrade refuses while external agents exist: dropping
the column would leave rows whose endpoint is gone (fail-loud, no silent data loss).
"""

import sqlalchemy as sa
from alembic import op

revision = "06b_0001"
down_revision = "57_0002"
branch_labels = ("06b",)
depends_on = None

# Full names: the naming convention already ran when 06a_0001 created the table.
PUBLISHED = "ck_agents_published_has_version"
CONFIG = "ck_agents_external_config"


def upgrade() -> None:
    op.add_column("agents", sa.Column("external_config", sa.LargeBinary()))
    op.drop_constraint(op.f(PUBLISHED), "agents", type_="check")
    op.create_check_constraint(
        op.f(PUBLISHED),
        "agents",
        "kind = 'external' OR status <> 'published' OR current_version_id IS NOT NULL",
    )
    op.create_check_constraint(
        op.f(CONFIG),
        "agents",
        "(kind = 'external' AND external_config IS NOT NULL)"
        " OR (kind <> 'external' AND external_config IS NULL)",
    )


def downgrade() -> None:
    external = op.get_bind().scalar(sa.text("SELECT count(*) FROM agents WHERE kind = 'external'"))
    if external:
        raise RuntimeError(
            f"{external} external agent(s) exist; delete them before downgrading below 06b_0001"
        )
    op.drop_constraint(op.f(CONFIG), "agents", type_="check")
    op.drop_constraint(op.f(PUBLISHED), "agents", type_="check")
    op.create_check_constraint(
        op.f(PUBLISHED), "agents", "status <> 'published' OR current_version_id IS NOT NULL"
    )
    op.drop_column("agents", "external_config")
