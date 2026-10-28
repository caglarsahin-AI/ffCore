"""audit_events: append-only, monthly range partitions on ts (03b).

C3 exception (append-only event table): no project-owned common columns. The table, its
partition helper and the append-only triggers are created by migration 03b_0001.
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base

ACTOR_TYPES = ("user", "api_key", "system")
OUTCOMES = ("success", "denied", "error")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint(f"actor_type IN {ACTOR_TYPES}", name="actor_type"),
        CheckConstraint(f"outcome IN {OUTCOMES}", name="outcome"),
        Index("ix_audit_events_project_ts", "project_id", "ts"),
        Index("ix_audit_events_resource", "resource_type", "resource_id", "ts"),
        {"postgresql_partition_by": "RANGE (ts)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Partition key; part of the primary key because Postgres requires it.
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    actor_type: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(Text)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text)
    resource_type: Mapped[str] = mapped_column(Text)
    resource_id: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    before: Mapped[dict | None] = mapped_column(JSONB)
    after: Mapped[dict | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(INET)
