"""alert_rules, alerts, notification_settings (03c, R9.1).

`alert_rules` is a project-owned root table (C3); `project_id` NULL is an installation-wide
rule (superadmin). `alerts` is append-only in spirit (C3 list): a fired alert is acked or
resolved, never edited otherwise. `notification_settings`: one row per project or one global
(`project_id` NULL); the SMTP password is in `smtp_encrypted` (Fernet, core/secrets.py).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

# Brief 03 R9.1 list + checkpoint_purge_overdue (FOLLOWUP-123, K-03c-0011 S9). Additive only.
ALERT_KINDS = (
    "budget_threshold",
    "service_down",
    "ingest_error",
    "sync_error",
    "prune_refused",
    "approval_pending_age",
    "guardrail_block_rate",
    "quota_warn",
    "convert_timeout",
    "disk_memory",
    "checkpoint_purge_overdue",
)
ALERT_CHANNELS = ("email", "webhook", "ui")
SEVERITIES = ("info", "warning", "critical")


class AlertRule(Timestamps, Base):
    __tablename__ = "alert_rules"
    __table_args__ = (
        CheckConstraint(f"kind IN {ALERT_KINDS}", name="kind"),
        CheckConstraint(f"channel IN {ALERT_CHANNELS}", name="channel"),
        Index("ix_alert_rules_kind_active", "kind", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    kind: Mapped[str] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    channel: Mapped[str] = mapped_column(Text)
    recipients: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint(f"severity IN {SEVERITIES}", name="severity"),
        Index("ix_alerts_rule_fired", "rule_id", "fired_at"),
        Index("ix_alerts_project_open", "project_id", "acked_at"),
        # One alert per rule and dedupe key (e.g. budget 80% of 2026-10): fired once.
        Index("uq_alerts_rule_dedupe", "rule_id", "dedupe_key", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("alert_rules.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    kind: Mapped[str] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(Text)
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    payload: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    severity: Mapped[str] = mapped_column(Text, server_default=text("'warning'"))
    acked_by: Mapped[str | None] = mapped_column(Text)
    acked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationSettings(Base):
    """C3 exception: settings row, one per project or one global (no soft delete)."""

    __tablename__ = "notification_settings"
    __table_args__ = (
        Index(
            "uq_notification_settings_project",
            text("coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id")
    )
    # {host, port, username, password, starttls}; Fernet, never returned unmasked.
    smtp_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary)
    default_webhook_url: Mapped[str | None] = mapped_column(Text)
    from_address: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), onupdate=text("now()")
    )
    updated_by: Mapped[str] = mapped_column(Text)
