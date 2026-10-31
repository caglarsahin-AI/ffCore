"""api_keys (03c): the credential an external client brings to the facade (06b).

A project-owned root table with the C3 common columns. The raw key is shown once in the create
response; the table keeps its public prefix and its SHA-256 (`key_hash`). `scopes` is the C2
enum; `acl_role` is the role the key's own searches run under when it is the actor (B7).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, CIDR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

# C2: new scopes are additive; an existing scope's meaning never changes.
API_KEY_SCOPES = ("chat_direct", "agents", "impersonate", "kb_search", "tools_invoke")
# `user` is reserved (17) and never the role of a key.
API_KEY_ACL_ROLES = ("analyst", "developer", "admin")


class ApiKey(Timestamps, Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(f"scopes <@ ARRAY{list(API_KEY_SCOPES)}::text[]", name="scopes"),
        CheckConstraint("cardinality(scopes) > 0", name="scopes_not_empty"),
        CheckConstraint(f"acl_role IN {API_KEY_ACL_ROLES}", name="acl_role"),
        CheckConstraint("key_hash ~ '^[0-9a-f]{64}$'", name="key_hash_format"),
        Index("uq_api_keys_key_prefix", "key_prefix", unique=True),
        Index("ix_api_keys_project_created_by", "project_id", "created_by"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    key_prefix: Mapped[str] = mapped_column(Text)
    key_hash: Mapped[str] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text))
    acl_role: Mapped[str] = mapped_column(Text, server_default=text("'analyst'"))
    # Empty: from anywhere. Checked against the client address on every request.
    allowed_cidrs: Mapped[list[str]] = mapped_column(
        ARRAY(CIDR), server_default=text("'{}'::cidr[]")
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
