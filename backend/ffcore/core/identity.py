"""Directory identity (17): the sign-in router, JIT provisioning, group mappings, the one
external identity resolver (15 uses it) and the daily `identity_sync`.

Rules (brief 17, KARARLAR '17 plan kararları'):
- The sign-in path is decided by the account row, never by trying one source after another:
  a local row signs in locally, a directory row (or an unknown login while LDAP is on) asks the
  directory. A directory that cannot be asked is 503 `identity_provider_unavailable`; nothing
  falls back to the local password.
- Every refusal of credentials is the same 401 `invalid_credentials`; the reason is audit-only.
- A superadmin is always local and always may sign in locally (LOCAL_LOGIN never locks it out).
- A directory account whose email belongs to another live account is 409 `identity_conflict`
  until a superadmin links the account (S1); a linked account binds its id on first sign-in.
- Group sync touches only `membership_source = 'idp'` rows; a manual membership is
  authoritative (S2).
"""

import logging
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.core.audit import AuditEntry, write_event
from ffcore.core.auth import ROLE_ORDER
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.core.ldap_auth import (
    DirectoryUser,
    InvalidCredentials,
    LdapDirectory,
    ProviderUnavailable,
)
from ffcore.core.passwords import hash_password, needs_rehash, verify_password
from ffcore.models.identity import IdentityGroupMapping, Project, ProjectMember, User

log = logging.getLogger(__name__)

SYSTEM_ACTOR = "identity"


class LoginRefused(ApiError):
    """A refused sign-in: the public error plus what the audit row records."""

    def __init__(
        self,
        status: int,
        error_type: str,
        code: str,
        message: str,
        *,
        reason: str,
        source: str | None,
        user_id: uuid.UUID | None = None,
    ) -> None:
        super().__init__(status, error_type, code, message)
        self.reason = reason
        self.source = source
        self.user_id = user_id


def invalid_credentials(reason: str, source: str | None, user_id=None) -> LoginRefused:
    return LoginRefused(
        401,
        "authentication_error",
        "invalid_credentials",
        "Email or password is incorrect.",
        reason=reason,
        source=source,
        user_id=user_id,
    )


def provider_unavailable(reason: str) -> LoginRefused:
    return LoginRefused(
        503,
        "api_error",
        "identity_provider_unavailable",
        "The organisation's directory cannot be reached; try again later.",
        reason=reason,
        source="ldap",
    )


def _inactive(user: User) -> LoginRefused:
    return LoginRefused(
        403,
        "permission_error",
        "user_inactive",
        "This account is disabled.",
        reason="user_inactive",
        source=user.auth_source,
        user_id=user.id,
    )


@dataclass
class LoginResult:
    user: User
    source: str
    memberships: "MembershipDiff | None" = None


@dataclass
class MembershipDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.added or self.removed or self.changed)


async def _live_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(
        select(User).where(
            func.lower(User.email) == email.strip().lower(), User.deleted_at.is_(None)
        )
    )


async def _live_user_by_external_id(
    session: AsyncSession, provider: str, external_id: str
) -> User | None:
    return await session.scalar(
        select(User).where(
            User.auth_source == provider,
            User.external_id == external_id,
            User.deleted_at.is_(None),
        )
    )


# --- sign-in ---


async def sign_in(
    session: AsyncSession,
    login: str,
    password: str,
    settings: Settings,
    directory: LdapDirectory | None,
) -> LoginResult:
    """The account a login and password belong to, or LoginRefused. Commits nothing."""
    user = await _live_user_by_email(session, login)
    if user is not None and user.auth_source == "local":
        return _local_sign_in(user, password, settings)
    if user is not None and user.auth_source == "oidc":
        # An OIDC account signs in at its provider; the password form never knows it.
        raise invalid_credentials("oidc_account_password_form", "oidc", user.id)
    if user is None and directory is None:
        raise invalid_credentials("user_not_found", "local")
    if directory is None:
        # A directory account while LDAP is switched off: not a wrong password, an outage.
        raise provider_unavailable("ldap_disabled")
    try:
        found = await directory.authenticate(login, password)
    except InvalidCredentials as exc:
        raise invalid_credentials(exc.reason, "ldap", user.id if user else None) from None
    except ProviderUnavailable as exc:
        raise provider_unavailable(exc.reason) from None
    account = await provision(session, found, settings)
    if not account.is_active or not found.active:
        raise _inactive(account)
    diff = await apply_group_mappings(session, account, found.provider, found.groups, settings)
    return LoginResult(account, "ldap", diff)


def _local_sign_in(user: User, password: str, settings: Settings) -> LoginResult:
    if not verify_password(user.password_hash, password):
        raise invalid_credentials("wrong_password", "local", user.id)
    if not user.is_active:
        raise _inactive(user)
    if not user.is_superadmin and settings.local_login != "all":
        raise LoginRefused(
            403,
            "permission_error",
            "local_login_disabled",
            "Sign in with your organisation account.",
            reason="local_login_disabled",
            source="local",
            user_id=user.id,
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    return LoginResult(user, "local")


def record_sign_in(user: User) -> None:
    user.last_login_at = datetime.now(UTC)


# --- JIT provisioning ---


async def provision(session: AsyncSession, found: DirectoryUser, settings: Settings) -> User:
    """The platform account of a directory user: found by id, bound after a superadmin link, or
    created (JIT). Profile fields follow the directory. Flushes; commits nothing."""
    user = await _live_user_by_external_id(session, found.provider, found.external_id)
    email = (found.email or "").strip()
    if user is None:
        if not email:
            raise LoginRefused(
                403,
                "permission_error",
                "identity_email_missing",
                "Your directory account has no email address; ask your administrator.",
                reason="identity_email_missing",
                source=found.provider,
            )
        same_email = await _live_user_by_email(session, email)
        if same_email is not None:
            if same_email.auth_source == found.provider and same_email.external_id is None:
                same_email.external_id = found.external_id
                user = same_email
                await write_event(
                    session,
                    _system_entry("user_identity_bound", user, {"provider": found.provider}),
                )
            else:
                raise LoginRefused(
                    409,
                    "conflict_error",
                    "identity_conflict",
                    "An account with this email already exists; ask your administrator to "
                    "link it to the directory.",
                    reason=f"email_taken_by_{same_email.auth_source}",
                    source=found.provider,
                    user_id=same_email.id,
                )
        else:
            user = User(
                email=email,
                full_name=found.full_name or email,
                password_hash=None,
                auth_source=found.provider,
                external_id=found.external_id,
            )
            session.add(user)
            await session.flush()
            await write_event(
                session, _system_entry("user_provisioned", user, {"provider": found.provider})
            )
            return user
    if email and email.lower() != user.email.lower():
        other = await _live_user_by_email(session, email)
        if other is not None and other.id != user.id:
            raise LoginRefused(
                409,
                "conflict_error",
                "identity_conflict",
                "An account with this email already exists; ask your administrator to link "
                "it to the directory.",
                reason="email_change_taken",
                source=found.provider,
                user_id=other.id,
            )
        user.email = email
    if found.full_name and found.full_name != user.full_name:
        user.full_name = found.full_name
    await session.flush()
    return user


def _system_entry(action: str, user: User, after: dict | None = None) -> AuditEntry:
    return AuditEntry(
        action=action,
        resource_type="user",
        outcome="success",
        actor_type="system",
        actor_id=SYSTEM_ACTOR,
        resource_id=str(user.id),
        after=after,
    )


# --- group mappings ---


def normalise_group(provider: str, group: str) -> str:
    """LDAP DNs compare case-insensitively (stored lower-case); OIDC claim values as given."""
    group = group.strip()
    return group.lower() if provider == "ldap" else group


async def _default_project(session: AsyncSession, settings: Settings) -> uuid.UUID | None:
    key = settings.default_project_for_new_users
    if not key:
        return None
    project_id = await session.scalar(
        select(Project.id).where(Project.key == key, Project.deleted_at.is_(None))
    )
    if project_id is None:
        # Fail loud: a configured default that does not exist is a setup error, not "none".
        raise ApiError(
            503,
            "api_error",
            "default_project_missing",
            "DEFAULT_PROJECT_FOR_NEW_USERS names a project that does not exist.",
        )
    return project_id


def _better(a: tuple[str, str], b: tuple[str, str]) -> tuple[str, str]:
    """Highest role wins; at the same role edit beats read."""
    role = max(a[0], b[0], key=ROLE_ORDER.index)
    access = "edit" if "edit" in (a[1], b[1]) else "read"
    return role, access


async def desired_memberships(
    session: AsyncSession, provider: str, groups: Iterable[str], settings: Settings
) -> dict[uuid.UUID, tuple[str, str]]:
    names = {normalise_group(provider, g) for g in groups if g and g.strip()}
    desired: dict[uuid.UUID, tuple[str, str]] = {}
    if names:
        rows = await session.execute(
            select(
                IdentityGroupMapping.project_id,
                IdentityGroupMapping.role,
                IdentityGroupMapping.access,
            )
            .join(Project, Project.id == IdentityGroupMapping.project_id)
            .where(
                IdentityGroupMapping.provider == provider,
                IdentityGroupMapping.external_group.in_(names),
                IdentityGroupMapping.deleted_at.is_(None),
                Project.deleted_at.is_(None),
            )
        )
        for project_id, role, access in rows:
            current = desired.get(project_id)
            desired[project_id] = (
                (role, access) if current is None else _better(current, (role, access))
            )
    default = await _default_project(session, settings)
    if default is not None and default not in desired:
        desired[default] = ("user", "read")
    return desired


async def apply_group_mappings(
    session: AsyncSession,
    user: User,
    provider: str,
    groups: Iterable[str],
    settings: Settings,
) -> MembershipDiff:
    """Make the user's `idp` memberships equal to what the groups map to; manual rows are left
    exactly as they are, even where a group maps the same project (S2). Flushes; audits."""
    desired = await desired_memberships(session, provider, groups, settings)
    rows = (
        await session.scalars(select(ProjectMember).where(ProjectMember.user_id == user.id))
    ).all()
    diff = MembershipDiff()
    seen: set[uuid.UUID] = set()
    for row in rows:
        seen.add(row.project_id)
        if row.membership_source != "idp":
            continue
        want = desired.get(row.project_id)
        if want is None:
            await session.delete(row)
            diff.removed.append(str(row.project_id))
        elif (row.role, row.access) != want:
            row.role, row.access = want
            diff.changed.append(str(row.project_id))
    for project_id, (role, access) in desired.items():
        if project_id in seen:
            continue
        session.add(
            ProjectMember(
                project_id=project_id,
                user_id=user.id,
                role=role,
                access=access,
                created_by=f"idp:{provider}",
                membership_source="idp",
            )
        )
        diff.added.append(str(project_id))
    await session.flush()
    if diff:
        await write_event(
            session,
            _system_entry(
                "membership_synced",
                user,
                {
                    "provider": provider,
                    "added": diff.added,
                    "removed": diff.removed,
                    "changed": diff.changed,
                },
            ),
        )
    return diff


async def affected_members(session: AsyncSession, project_id: uuid.UUID) -> int:
    """How many directory-sourced members a project's mappings currently feed (a number for the
    mapping screen, never names)."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(ProjectMember)
            .where(ProjectMember.project_id == project_id, ProjectMember.membership_source == "idp")
        )
        or 0
    )


# --- the one resolver (15) ---


async def resolve_external_identity(
    session: AsyncSession,
    *,
    email: str | None = None,
    upn: str | None = None,
    external_id: str | None = None,
    provider: str | None = None,
    settings: Settings,
    directory: LdapDirectory | None = None,
) -> User | None:
    """The live, active platform account behind a channel or widget identity, or None (the
    caller refuses politely, brief 15). With AUTO_PROVISION_FROM_CHANNELS on and a directory, a
    user found there by email gets an account (JIT, group mappings applied); off, never."""
    if external_id is not None:
        if provider not in ("ldap", "oidc"):
            raise ValueError("external_id needs provider ldap or oidc")
        user = await _live_user_by_external_id(session, provider, external_id)
        return user if user is not None and user.is_active else None
    value = email or upn
    if not value or not value.strip():
        return None
    user = await _live_user_by_email(session, value)
    if user is not None:
        return user if user.is_active else None
    if not settings.auto_provision_from_channels or directory is None:
        return None
    try:
        found = await directory.find_by_email(value)
    except ProviderUnavailable:
        raise provider_unavailable("directory_unreachable") from None
    if found is None or not found.active:
        return None
    account = await provision(session, found, settings)
    await apply_group_mappings(session, account, found.provider, found.groups, settings)
    return account


# --- local import helpers ---


def temporary_password() -> str:
    """Shown once in the import answer; 20 url-safe characters (above the 12-character rule)."""
    return secrets.token_urlsafe(15)


# --- identity_sync (daily, background worker) ---


@dataclass
class SyncReport:
    checked: int = 0
    deactivated: list[str] = field(default_factory=list)
    error: str | None = None


async def deactivate(session: AsyncSession, user: User, reason: str) -> None:
    user.is_active = False
    user.token_version += 1  # every open session drops
    await write_event(session, _system_entry("user_deactivated", user, {"reason": reason}))


async def run_identity_sync(
    session: AsyncSession,
    settings: Settings,
    directory: LdapDirectory | None,
    *,
    now: datetime | None = None,
) -> SyncReport:
    """Deactivate directory accounts the directory no longer has or has disabled, and OIDC
    accounts unused for OIDC_INACTIVE_AFTER_DAYS. All directory answers are gathered first: an
    unreachable directory changes nothing (no partial run). Commits."""
    now = now or datetime.now(UTC)
    report = SyncReport()
    decisions: list[tuple[User, str]] = []
    if directory is not None:
        users = (
            await session.scalars(
                select(User).where(
                    User.auth_source == "ldap",
                    User.external_id.is_not(None),
                    User.is_active,
                    User.deleted_at.is_(None),
                )
            )
        ).all()
        try:
            for user in users:
                found = await directory.find(user.external_id)
                report.checked += 1
                if found is None:
                    decisions.append((user, "directory_missing"))
                elif not found.active:
                    decisions.append((user, "directory_disabled"))
        except ProviderUnavailable as exc:
            report.error = exc.reason
            decisions = []
    if report.error is None:
        cutoff = now - timedelta(days=settings.oidc_inactive_after_days)
        idle = (
            await session.scalars(
                select(User).where(
                    User.auth_source == "oidc",
                    User.is_active,
                    User.deleted_at.is_(None),
                    func.coalesce(User.last_login_at, User.created_at) < cutoff,
                )
            )
        ).all()
        report.checked += len(idle)
        decisions.extend((user, "oidc_inactive") for user in idle)
        for user, reason in decisions:
            await deactivate(session, user, reason)
            report.deactivated.append(str(user.id))
    await write_event(
        session,
        AuditEntry(
            action="identity.sync",
            resource_type="identity",
            outcome="error" if report.error else "success",
            actor_type="system",
            actor_id=SYSTEM_ACTOR,
            after={
                "checked": report.checked,
                "deactivated": len(report.deactivated),
                **({"error": report.error} if report.error else {}),
            },
        ),
    )
    await session.commit()
    return report


async def identity_sync(ctx) -> str:
    """arq cron (background worker, C9): the daily identity_sync."""
    from ffcore.core import db
    from ffcore.core.config import get_settings

    settings = get_settings()
    directory = LdapDirectory(settings) if settings.ldap_enabled else None
    async with db.session_scope() as session:
        report = await run_identity_sync(session, settings, directory)
    if report.error:
        log.error("identity_sync stopped: directory %s; nothing changed", report.error)
        return "error"
    log.info("identity_sync: %d checked, %d deactivated", report.checked, len(report.deactivated))
    return "ok"
