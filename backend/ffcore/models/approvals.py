"""approvals (07): the human gate on tool calls that need approval.

A project-owned root table with the C3 common columns. One row per interrupted tool call of a
run (run_id, tool_call_id). `arguments` is the masked payload 06a already wrote on the
`approval_requested` event (08-lite masks); raw arguments never reach this table. `run_id`
gets its foreign key to runs when 06a is on main (plan S5).
"""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

# expired: APPROVAL_TTL_MIN passed without a decision; the run is closed (approval_expired).
APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired")
# Roles that may be asked to decide; `user` never approves (brief 07, R6.1).
APPROVER_ROLES = ("analyst", "developer", "admin")


class Approval(Timestamps, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(f"status IN {APPROVAL_STATUSES}", name="status"),
        CheckConstraint(f"assigned_role IN {APPROVER_ROLES}", name="assigned_role"),
        CheckConstraint(
            "(status = 'pending') = (resolved_at IS NULL)", name="resolved_at_matches_status"
        ),
        CheckConstraint("args_hash ~ '^[0-9a-f]{64}$'", name="args_hash_format"),
        Index("uq_approvals_run_tool_call", "run_id", "tool_call_id", unique=True),
        Index(
            "ix_approvals_pending_expires_at",
            "expires_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_approvals_project_status", "project_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    tool_call_id: Mapped[str] = mapped_column(Text)
    # Model-facing tool name `<tool_key>__<action>` (C7).
    action: Mapped[str] = mapped_column(Text)
    arguments: Mapped[dict] = mapped_column(JSONB)
    # SHA-256 of the canonical JSON of the arguments; same run + action + hash is not asked twice.
    args_hash: Mapped[str] = mapped_column(Text)
    reason_from_model: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    assigned_role: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(Text)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
