"""tools, tool_actions, schema_descriptions, few_shots (05a).

`tools` and `schema_descriptions` are project-owned root tables with the C3 common columns;
`tool_actions` (via tool_id) and `few_shots` are child tables (C3 exceptions).
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

TOOL_KINDS = ("mcp", "openapi")
AUTH_TYPES = ("none", "bearer", "header", "basic", "forward_user")
# registered: saved, never discovered; discovered: tools/list answered; error: last discovery
# failed (last_error_code says why).
TOOL_STATUSES = ("registered", "discovered", "error")
# available: listed by the server at the last discovery; missing: no longer listed (kept,
# disabled, never deleted silently).
ACTION_STATUSES = ("available", "missing")
TOOL_KEY_REGEX = "^[a-z][a-z0-9-]{1,63}$"


class Tool(Timestamps, Base):
    __tablename__ = "tools"
    __table_args__ = (
        CheckConstraint(f"kind IN {TOOL_KINDS}", name="kind"),
        CheckConstraint(f"auth_type IN {AUTH_TYPES}", name="auth_type"),
        CheckConstraint(f"status IN {TOOL_STATUSES}", name="status"),
        CheckConstraint(f"key ~ '{TOOL_KEY_REGEX}'", name="key_format"),
        Index(
            "uq_tools_project_key_live",
            "project_id",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    endpoint_url: Mapped[str] = mapped_column(Text)
    # Not secret: decides pooling (U5) and the internal-host rule (C3).
    auth_type: Mapped[str] = mapped_column(Text)
    # Fernet token of the auth fields (core/secrets.py); never returned as is.
    auth_config_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(Text, server_default=text("'registered'"))
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolAction(Timestamps, Base):
    __tablename__ = "tool_actions"
    __table_args__ = (
        UniqueConstraint("tool_id", "name", name="uq_tool_actions_tool_name"),
        CheckConstraint(f"status IN {ACTION_STATUSES}", name="status"),
        CheckConstraint("max_calls_per_run IS NULL OR max_calls_per_run > 0", name="max_calls"),
        CheckConstraint("timeout_s IS NULL OR timeout_s BETWEEN 1 AND 600", name="timeout"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tools.id"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    input_schema: Mapped[dict] = mapped_column(JSONB)
    needs_approval: Mapped[bool] = mapped_column(Boolean)
    enabled: Mapped[bool] = mapped_column(Boolean)
    max_calls_per_run: Mapped[int | None] = mapped_column(Integer)
    timeout_s: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, server_default=text("'available'"))


class SchemaDescription(Timestamps, Base):
    __tablename__ = "schema_descriptions"
    __table_args__ = (
        Index(
            "uq_schema_descriptions_live",
            "project_id",
            "table_name",
            text("coalesce(column_name, '')"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    table_name: Mapped[str] = mapped_column(Text)
    # NULL: the row describes the table itself.
    column_name: Mapped[str | None] = mapped_column(Text)
    # Business-language description in the data's own language (13a: Turkish).
    description: Mapped[str] = mapped_column(Text)
    sample_values: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    is_metric: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    formula: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FewShot(Base):
    __tablename__ = "few_shots"
    __table_args__ = (Index("ix_few_shots_project", "project_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    question: Mapped[str] = mapped_column(Text)
    sql: Mapped[str] = mapped_column(Text)
    # vector(EMBED_DIM), created by the migration with the installation's dimension (as chunks).
    embedding = mapped_column(Vector(), nullable=False)
    approved_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
