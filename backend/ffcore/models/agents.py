"""agents, agent_versions (06a); agents.external_config (06b-2).

`agents` is a project-owned root table (C3 common columns); `agent_versions` is its child (the
project comes through `agent_id`). A version's `definition` is the C8 document; a published
version is never edited (a new draft is opened instead).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Text,
    UniqueConstraint,
)
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

AGENT_KEY_REGEX = "^[a-z][a-z0-9_-]{0,63}$"
AGENT_STATUSES = ("draft", "published", "inactive")
AGENT_KINDS = ("native", "external")


class Agent(Timestamps, Base):
    __tablename__ = "agents"
    __table_args__ = (
        CheckConstraint(f"key ~ '{AGENT_KEY_REGEX}'", name="key_format"),
        CheckConstraint(f"status IN {AGENT_STATUSES}", name="status"),
        CheckConstraint(f"kind IN {AGENT_KINDS}", name="kind"),
        # An external agent has no versions (06b-2): it is published without one.
        CheckConstraint(
            "kind = 'external' OR status <> 'published' OR current_version_id IS NOT NULL",
            name="published_has_version",
        ),
        CheckConstraint(
            "(kind = 'external' AND external_config IS NOT NULL)"
            " OR (kind <> 'external' AND external_config IS NULL)",
            name="external_config",
        ),
        Index(
            "uq_agents_project_key_live",
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
    description: Mapped[str] = mapped_column(Text, server_default=sql_text("''"))
    status: Mapped[str] = mapped_column(Text, server_default=sql_text("'draft'"))
    kind: Mapped[str] = mapped_column(Text, server_default=sql_text("'native'"))
    # The published version; null while the agent has only drafts.
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_versions.id", use_alter=True, name="fk_agents_current_version"),
    )
    # 06b-2: an external agent's base_url, remote model and api_key, one Fernet token
    # (services/external_config.ExternalConfig); set exactly when kind = external.
    external_config: Mapped[bytes | None] = mapped_column(LargeBinary)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentVersion(Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_agent_versions_agent_version"),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agents.id"))
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSONB)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql_text("now()"), onupdate=sql_text("now()")
    )
    # Set once, when the version is first published; a published version is read-only.
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The exam run that gated publishing (09); null until 09.
    eval_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
