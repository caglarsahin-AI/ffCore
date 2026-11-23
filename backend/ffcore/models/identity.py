"""users, projects, project_members (03a); directory identity and group mappings (17).

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
# PoC assigned analyst and admin (A3); 17 opens `user` (end users). `developer` stays reserved.
ASSIGNABLE_ROLES = ("user", "analyst", "admin")
ACCESS_MODES = ("edit", "read")
# 17: where an account's identity lives. A superadmin is always local (recovery account).
AUTH_SOURCES = ("local", "ldap", "oidc")
EXTERNAL_PROVIDERS = ("ldap", "oidc")
# 17 (K-17-0002 S2): a manual membership is authoritative; group sync only touches `idp` rows.
MEMBERSHIP_SOURCES = ("manual", "idp")
# 17 r2: who switched an account off. identity_sync's own deactivation reopens when the
# directory shows the account again; an administrator's never does by itself.
DEACTIVATED_BY = ("identity_sync", "admin")
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
        CheckConstraint(f"auth_source IN {AUTH_SOURCES}", name="auth_source"),
        # 17: only a local account has a password; a directory account never does.
        CheckConstraint(
            "(auth_source = 'local') = (password_hash IS NOT NULL)", name="password_only_local"
        ),
        CheckConstraint("NOT is_superadmin OR auth_source = 'local'", name="superadmin_is_local"),
        CheckConstraint(
            f"deactivated_by IS NULL OR deactivated_by IN {DEACTIVATED_BY}", name="deactivated_by"
        ),
        Index(
            "uq_users_external_id_live",
            "auth_source",
            "external_id",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL AND deleted_at IS NULL"),
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
    # NULL for directory accounts (17); argon2 for local ones.
    password_hash: Mapped[str | None] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_superadmin: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    superadmin_access: Mapped[str | None] = mapped_column(Text)
    # Bumped on logout and password change; session tokens carry it and are refused when stale.
    token_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # --- 17 ---
    auth_source: Mapped[str] = mapped_column(Text, server_default=text("'local'"))
    # objectGUID / entryUUID (LDAP) or `sub` (OIDC); NULL while a superadmin-linked account
    # waits for its first directory sign-in (K-17-0002 S1).
    external_id: Mapped[str | None] = mapped_column(Text)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by the CSV import (temporary password); the console forces a password change.
    must_change_password: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    deactivated_by: Mapped[str | None] = mapped_column(Text)


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
        CheckConstraint(f"membership_source IN {MEMBERSHIP_SOURCES}", name="membership_source"),
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
    membership_source: Mapped[str] = mapped_column(Text, server_default=text("'manual'"))


class IdentityGroupMapping(Timestamps, Base):
    """17: a directory group (LDAP DN, stored lower-case) or an OIDC group claim value gives its
    members a role in one project (K-17-0002 S3: project_id is required). Common C3 columns;
    removal is a soft delete like other root tables."""

    __tablename__ = "identity_group_mappings"
    __table_args__ = (
        CheckConstraint(f"provider IN {EXTERNAL_PROVIDERS}", name="provider"),
        CheckConstraint(f"role IN {ASSIGNABLE_ROLES}", name="role"),
        CheckConstraint(f"access IN {ACCESS_MODES}", name="access"),
        CheckConstraint("length(external_group) BETWEEN 1 AND 1024", name="external_group"),
        Index(
            "uq_identity_group_mappings_live",
            "provider",
            "external_group",
            "project_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    provider: Mapped[str] = mapped_column(Text)
    external_group: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    access: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
