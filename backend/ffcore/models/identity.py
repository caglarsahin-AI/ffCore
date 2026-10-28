"""users, projects, project_members (03a).

C3: `users` is global; `projects` is the project itself (no project_id, other common columns
present); `project_members` is a link table. The rule and its exception list live in
tests/contract/test_c3_common_columns.py.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ffcore.models.base import Base

# Order matters: user < analyst < developer < admin (brief 03 R2.4).
ROLES = ("user", "analyst", "developer", "admin")
# PoC assigns only these (A3); the others stay in the enum, reserved.
ASSIGNABLE_ROLES = ("analyst", "admin")
ACCESS_MODES = ("edit", "read")
# Same pattern as the API schema; enforced in the database too.
PROJECT_KEY_REGEX = "^[a-z][a-z0-9-]{1,31}$"


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"superadmin_access IN {ACCESS_MODES}", name="superadmin_access"),
        CheckConstraint(
            "NOT is_superadmin OR superadmin_access IS NOT NULL", name="superadmin_has_access"
        ),
        # One live account per email, compared case-insensitively.
        Index(
            "uq_users_email_live",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    superadmin_access: Mapped[str | None] = mapped_column(Text)
    # Bumped on logout and password change; session tokens carry it and are refused when stale.
    token_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Project(Timestamps, Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint(f"key ~ '{PROJECT_KEY_REGEX}'", name="key_format"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Global and never reused, even after soft delete: it is part of every model name (C1).
    key: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        CheckConstraint(f"role IN {ROLES}", name="role"),
        CheckConstraint(f"access IN {ACCESS_MODES}", name="access"),
        Index("ix_project_members_user", "user_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text)
    access: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
