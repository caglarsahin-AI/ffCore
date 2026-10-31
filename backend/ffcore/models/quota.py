"""quotas and usage_daily (03c, R2.1, C20).

`quotas` is a project-owned root table (C3 common columns). One row limits one subject: the
project itself, one API key or one user, over request windows, token windows, per-request token
sizes and USD budgets. The decision is taken from Redis counters at request time
(`services/quota.py`); `usage_daily` is reporting only (C3 exception: one row per project, day,
model, key and user, upserted as calls finish).
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base
from ffcore.models.identity import Timestamps

# `group`, `model`, `provider` scopes are rejected (KARARLAR C20: no enforcer).
QUOTA_SCOPES = ("project", "api_key", "user")
QUOTA_ACTIONS = ("block", "warn")
WINDOW_FIELDS = ("rpm", "rph", "rpd", "rpm_month", "concurrent")
TOKEN_FIELDS = ("tpm", "tpd", "tpm_month", "max_input", "max_output", "max_total")
BUDGET_FIELDS = ("daily_usd", "monthly_usd")


class Quota(Timestamps, Base):
    __tablename__ = "quotas"
    __table_args__ = (
        CheckConstraint(f"scope_type IN {QUOTA_SCOPES}", name="scope_type"),
        CheckConstraint(f"action IN {QUOTA_ACTIONS}", name="action"),
        Index("ix_quotas_project_scope", "project_id", "scope_type", "scope_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    scope_type: Mapped[str] = mapped_column(Text)
    # The project, API key or user id; for scope_type=project it equals project_id.
    scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    label: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    windows: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    tokens: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    budget: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    action: Mapped[str] = mapped_column(Text, server_default=text("'block'"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    activate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageDaily(Base):
    """Reporting only; budgets are decided from Redis (C20). C3 exception (upserted rows)."""

    __tablename__ = "usage_daily"
    __table_args__ = (
        Index(
            "uq_usage_daily_row",
            "project_id",
            "date",
            "model",
            text("coalesce(api_key_id, '00000000-0000-0000-0000-000000000000'::uuid)"),
            text("coalesce(user_id, '')"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    date: Mapped[date] = mapped_column(Date)
    model: Mapped[str] = mapped_column(Text)
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(18, 8), server_default=text("0"))
    requests: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
