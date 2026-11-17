"""mcp_servers, mcp_server_calls (05b): OpenAPI documents and remote MCP servers published as MCP
servers under `/mcp/{key}/`.

`mcp_servers` is a project-owned root table with the C3 common columns; its key is unique across
the installation (the endpoint path has no project). `mcp_server_calls` is its child table
(C3: the project comes through server_id): one row per tools/call, never arguments or results.
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps
from ffcore.models.tools import TOOL_KEY_REGEX

SOURCE_KINDS = ("openapi", "remote_mcp")
# A2 identities for a third-party upstream; forward_user goes only to FFCore services (C3), and
# those are never an upstream (RESERVED_HOSTS).
UPSTREAM_AUTH_TYPES = ("none", "bearer", "header", "basic")
SERVER_ACCESS = ("token", "internal")
GUARDRAIL_MODES = ("off", "monitor", "enforce")
# draft: saved, not served; active: served at /mcp/{key}/; disabled: kept, not served.
SERVER_STATUSES = ("draft", "active", "disabled")
PROTOCOLS = ("streamable_http",)
# ok: the upstream answered 2xx; error: it did not, or the call could not be made; blocked: a
# guardrail stopped it; denied: quota refused it.
CALL_STATUSES = ("ok", "error", "blocked", "denied")
SERVER_KEY_REGEX = TOOL_KEY_REGEX


class McpServer(Timestamps, Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        CheckConstraint(f"source_kind IN {SOURCE_KINDS}", name="source_kind"),
        CheckConstraint(f"upstream_auth_type IN {UPSTREAM_AUTH_TYPES}", name="upstream_auth_type"),
        CheckConstraint(f"access IN {SERVER_ACCESS}", name="access"),
        CheckConstraint(f"guardrail_mode IN {GUARDRAIL_MODES}", name="guardrail_mode"),
        CheckConstraint(f"status IN {SERVER_STATUSES}", name="status"),
        CheckConstraint(f"key ~ '{SERVER_KEY_REGEX}'", name="key_format"),
        CheckConstraint(
            "(source_kind = 'openapi' AND spec_encrypted IS NOT NULL)"
            " OR (source_kind <> 'openapi' AND spec_encrypted IS NULL)",
            name="spec_for_openapi",
        ),
        Index(
            "uq_mcp_servers_key_live",
            "key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    key: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    source_kind: Mapped[str] = mapped_column(Text)
    # Fernet token of the OpenAPI document (core/secrets.py); openapi only.
    spec_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    upstream_base_url: Mapped[str] = mapped_column(Text)
    upstream_auth_type: Mapped[str] = mapped_column(Text)
    upstream_auth_encrypted: Mapped[bytes] = mapped_column(LargeBinary)
    # The catalog from the document (openapi) or the upstream's tools/list (remote_mcp): name,
    # method, path, description, input_schema, exposable, reason, alias, alias_description.
    operations: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    exposed_operations: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{}'::text[]")
    )
    protocols: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=text("'{streamable_http}'::text[]")
    )
    access: Mapped[str] = mapped_column(Text, server_default=text("'internal'"))
    guardrail_mode: Mapped[str] = mapped_column(Text, server_default=text("'monitor'"))
    guardrail_policy_key: Mapped[str] = mapped_column(Text, server_default=text("'default'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'draft'"))
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class McpServerCall(Base):
    __tablename__ = "mcp_server_calls"
    __table_args__ = (
        CheckConstraint(f"status IN {CALL_STATUSES}", name="status"),
        Index("ix_mcp_server_calls_server_ts", "server_id", text("ts DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_type: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
    # The strongest guardrail action of the call (allow, mask, block, ...), None when none ran.
    guardrail_action: Mapped[str | None] = mapped_column(Text)
