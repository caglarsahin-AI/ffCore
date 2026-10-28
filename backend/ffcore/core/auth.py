"""Caller identity: `resolve_actor()` is the single verification point (CONTRACTS C2).

03b provides the internal service account (`SERVICE_TOKEN`) and `X-On-Behalf-Of` tokens.
03a (user session) and 03c (API keys) add credential resolvers through
`register_credential_resolver`; the verification rules below stay in this one function.
"""

import hmac
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

import jwt
from fastapi import Depends, Request

from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError

OBO_HEADER = "X-On-Behalf-Of"
OBO_MAX_LIFETIME_S = 300
OBO_ALGORITHM = "HS256"
_REQUIRED_CLAIMS = ("sub", "project_id", "aud", "exp", "iat")

ActorType = Literal["user", "api_key", "system"]


@dataclass(frozen=True)
class Actor:
    actor_type: ActorType
    actor_id: str
    project_id: str | None = None
    # True when a service account acts for this user through X-On-Behalf-Of.
    via_service: bool = False
    scopes: frozenset[str] = field(default_factory=frozenset)

    @property
    def may_impersonate(self) -> bool:
        # The service account, or (03c) an API key with the `impersonate` scope.
        return (self.actor_type == "system" and self.actor_id == "service") or (
            self.actor_type == "api_key" and "impersonate" in self.scopes
        )


SERVICE_ACTOR = Actor(actor_type="system", actor_id="service")

CredentialResolver = Callable[[Request, Settings], Awaitable[Actor | None]]


@dataclass(frozen=True)
class OnBehalfOfClaims:
    sub: str
    project_id: str
    aud: str
    iat: int
    exp: int
    jti: str


class OnBehalfOfError(ApiError):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        error_type = "authentication_error" if status_code == 401 else "permission_error"
        super().__init__(status_code, error_type, code, message)


def _bearer(request: Request) -> str | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


async def _service_token_resolver(request: Request, settings: Settings) -> Actor | None:
    token = _bearer(request)
    if token is None:
        return None
    expected = settings.service_token.get_secret_value()
    if hmac.compare_digest(token.encode(), expected.encode()):
        return SERVICE_ACTOR
    return None


_resolvers: list[CredentialResolver] = [_service_token_resolver]


def register_credential_resolver(resolver: CredentialResolver) -> None:
    if resolver not in _resolvers:
        _resolvers.append(resolver)


def unregister_credential_resolver(resolver: CredentialResolver) -> None:
    if resolver is not _service_token_resolver and resolver in _resolvers:
        _resolvers.remove(resolver)


def sign_on_behalf_of(
    *,
    user_id: str,
    project_id: str,
    audience: str,
    settings: Settings,
    now: datetime | None = None,
    ttl_s: int = OBO_MAX_LIFETIME_S,
) -> str:
    """Sign a fresh token for one call; callers re-sign on every tool/service call (C3)."""
    if not 0 < ttl_s <= OBO_MAX_LIFETIME_S:
        raise ValueError(f"on-behalf-of lifetime must be 1..{OBO_MAX_LIFETIME_S} s")
    if not audience:
        raise ValueError("on-behalf-of audience is required")
    issued = now or datetime.now(UTC)
    claims = {
        "sub": user_id,
        "project_id": project_id,
        "aud": audience,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=ttl_s)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.obo_jwt_secret.get_secret_value(), algorithm=OBO_ALGORITHM)


def verify_on_behalf_of(
    token: str, *, audience: str, settings: Settings, now: datetime | None = None
) -> OnBehalfOfClaims:
    """Verify signature, audience, required claims and the 5-minute lifetime.

    Expired, malformed or over-long tokens are 401; a valid token for another audience is 403.
    """
    try:
        claims = jwt.decode(
            token,
            settings.obo_jwt_secret.get_secret_value(),
            algorithms=[OBO_ALGORITHM],
            audience=audience,
            # Time checks run below against an injectable clock; PyJWT checks the rest.
            options={
                "require": list(_REQUIRED_CLAIMS),
                "verify_exp": False,
                "verify_iat": False,
                "verify_nbf": False,
            },
        )
    except jwt.InvalidAudienceError:
        raise OnBehalfOfError(403, "audience_mismatch", "Token audience mismatch.") from None
    except jwt.MissingRequiredClaimError:
        raise OnBehalfOfError(401, "invalid_token", "Token is missing a required claim.") from None
    except jwt.PyJWTError:
        raise OnBehalfOfError(401, "invalid_token", "Token is invalid.") from None

    try:
        iat, exp = int(claims["iat"]), int(claims["exp"])
    except (TypeError, ValueError):
        raise OnBehalfOfError(401, "invalid_token", "Token times are invalid.") from None
    if not isinstance(claims["sub"], str) or not isinstance(claims["project_id"], str):
        raise OnBehalfOfError(401, "invalid_token", "Token subject is invalid.")
    if exp - iat > OBO_MAX_LIFETIME_S or exp <= iat:
        raise OnBehalfOfError(401, "token_lifetime_exceeded", "Token lifetime exceeds 5 minutes.")
    current = int((now or datetime.now(UTC)).timestamp())
    if current >= exp:
        raise OnBehalfOfError(401, "token_expired", "Token has expired.")
    if iat > current + 30:
        raise OnBehalfOfError(401, "invalid_token", "Token is issued in the future.")
    return OnBehalfOfClaims(
        sub=claims["sub"],
        project_id=claims["project_id"],
        aud=audience,
        iat=iat,
        exp=exp,
        jti=str(claims.get("jti", "")),
    )


# --- Console session tokens (03a); the cookie and resolver are in core/session.py ---

SESSION_AUDIENCE = "ffcore-session"


@dataclass(frozen=True)
class SessionClaims:
    user_id: str
    token_version: int


def issue_session_token(
    user_id: str, token_version: int, settings: Settings, now: datetime | None = None
) -> str:
    """HS256 with SECRET_KEY (not the OBO key); `tv` is the user's token_version."""
    issued = now or datetime.now(UTC)
    claims = {
        "sub": user_id,
        "tv": token_version,
        "aud": SESSION_AUDIENCE,
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=settings.session_ttl_s)).timestamp()),
    }
    return jwt.encode(claims, settings.secret_key.get_secret_value(), algorithm=OBO_ALGORITHM)


def verify_session_token(token: str, settings: Settings) -> SessionClaims | None:
    """None for any invalid, expired or foreign token: the caller is then unauthenticated."""
    try:
        claims = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[OBO_ALGORITHM],
            audience=SESSION_AUDIENCE,
            options={"require": ["sub", "tv", "aud", "iat", "exp"]},
        )
    except jwt.PyJWTError:
        return None
    if not isinstance(claims["sub"], str) or not isinstance(claims["tv"], int):
        return None
    return SessionClaims(user_id=claims["sub"], token_version=claims["tv"])


async def _audit_impersonation_denied(request: Request, actor: Actor | None) -> None:
    from ffcore.core.audit import record_impersonation_denied

    await record_impersonation_denied(request, actor)


async def resolve_actor(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> Actor:
    actor: Actor | None = None
    for resolver in list(_resolvers):
        actor = await resolver(request, settings)
        if actor is not None:
            break

    obo_token = request.headers.get(OBO_HEADER)
    if obo_token:
        if actor is not None and actor.may_impersonate:
            claims = verify_on_behalf_of(
                obo_token, audience=settings.obo_audience, settings=settings
            )
            actor = Actor(
                actor_type="user",
                actor_id=claims.sub,
                project_id=claims.project_id,
                via_service=True,
            )
        else:
            # Ignored, not silently: every rejected impersonation is an audit event (R2.5).
            await _audit_impersonation_denied(request, actor)

    if actor is None:
        raise ApiError(401, "authentication_error", "unauthenticated", "Authentication required.")
    request.state.actor = actor
    return actor


# --- Authorization (03a): role and access mode, checked after resolve_actor ---

# Ascending: user < analyst < developer < admin (brief 03 R2.4).
ROLE_ORDER = ("user", "analyst", "developer", "admin")


@dataclass(frozen=True)
class Grant:
    role: str
    access: str
    is_superadmin: bool


class RoleRequirement:
    """FastAPI dependency: the caller holds at least `min_role`; with `write=True` also `edit`.

    `scope="project"` reads `project_id` from the path; `scope="tenant"` needs a superadmin.
    A denial is written to the audit trail (detached) before the 403. The `write` attribute is
    what the CI scan looks for on every mutation route (brief 03 acceptance).
    """

    def __init__(self, min_role: str, *, write: bool, scope: Literal["project", "tenant"]):
        if min_role not in ROLE_ORDER:
            raise ValueError(f"unknown role {min_role!r}")
        self.min_role = min_role
        self.write = write
        self.scope = scope

    async def __call__(self, request: Request, actor: Annotated[Actor, Depends(resolve_actor)]):
        project_id = request.path_params.get("project_id") if self.scope == "project" else None
        return await authorize(request, actor, project_id, self)


async def authorize(
    request: Request, actor: Actor, project_id: str | None, need: RoleRequirement
) -> Actor:
    """The check behind RoleRequirement, for routes whose project comes from elsewhere (query)."""
    grant, code = await _grant(actor, project_id)
    if grant is not None and code is None:
        if ROLE_ORDER.index(grant.role) < ROLE_ORDER.index(need.min_role):
            code = "insufficient_role"
        elif need.write and grant.access != "edit":
            code = "read_only_access"
    if code == "project_not_found":
        raise ApiError(404, "not_found_error", code, "Project not found.")
    if code is not None:
        await _audit_denied(request, actor, project_id, code, need)
        message = {
            "read_only_access": "Your access mode is read-only.",
            "obo_project_scope": "A call on behalf of a user is limited to the token's project.",
        }.get(code, "Your role does not allow this.")
        raise ApiError(403, "permission_error", code, message)
    request.state.grant = grant
    return Actor(
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        project_id=str(project_id) if project_id else actor.project_id,
        via_service=actor.via_service,
        scopes=actor.scopes,
    )


def require_role(min_role: str, *, write: bool = False) -> RoleRequirement:
    """Project-scoped check (brief: require_role(project_id, min_role, write))."""
    return RoleRequirement(min_role, write=write, scope="project")


def require_superadmin(*, write: bool = False) -> RoleRequirement:
    """Tenant-level check (users, providers, catalog, unscoped audit)."""
    return RoleRequirement("admin", write=write, scope="tenant")


async def _grant(actor: Actor, project_id: str | None) -> tuple[Grant | None, str | None]:
    """The caller's role and access for the project (or tenant). (grant, None) or (None, code)."""
    from sqlalchemy import select

    from ffcore.core import db
    from ffcore.models.identity import Project, ProjectMember, User

    if actor.actor_type != "user":
        return None, "insufficient_role"
    try:
        user_id = uuid.UUID(actor.actor_id)
        project_uuid = uuid.UUID(project_id) if project_id else None
    except ValueError:
        return None, "insufficient_role" if project_id is None else "project_not_found"
    # The project in an X-On-Behalf-Of token bounds the whole call (K-03a-0007, decision A):
    # no tenant administration and no other project, whatever the user may do in the console.
    if actor.via_service and (project_uuid is None or actor.project_id != str(project_uuid)):
        return None, "obo_project_scope"

    async with db.session_scope() as session:
        user = await session.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None), User.is_active)
        )
        if user is None:
            return None, "insufficient_role"
        if project_uuid is not None:
            live = await session.scalar(
                select(Project.id).where(Project.id == project_uuid, Project.deleted_at.is_(None))
            )
            if live is None:
                return None, "project_not_found" if user.is_superadmin else "insufficient_role"
        # Superadmin rights belong to the console session; under OBO only membership counts.
        if user.is_superadmin and not actor.via_service:
            return Grant("admin", user.superadmin_access or "read", True), None
        if project_uuid is None:
            return None, "insufficient_role"
        member = await session.scalar(
            select(ProjectMember).where(
                ProjectMember.project_id == project_uuid, ProjectMember.user_id == user_id
            )
        )
    if member is None:
        return None, "insufficient_role"
    return Grant(member.role, member.access, False), None


async def _audit_denied(
    request: Request, actor: Actor, project_id: str | None, code: str, need: RoleRequirement
) -> None:
    from ffcore.core.audit import AuditEntry, request_context, write_event_detached

    route = request.scope.get("route")
    request_id, ip = request_context(request)
    try:
        valid_project = str(uuid.UUID(project_id)) if project_id else None
    except ValueError:
        valid_project = None
    await write_event_detached(
        AuditEntry(
            action=getattr(route, "name", request.url.path),
            resource_type="route",
            outcome="denied",
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            project_id=valid_project,
            after={
                "method": request.method,
                "path": getattr(route, "path", request.url.path),
                "code": code,
                "min_role": need.min_role,
                "write": need.write,
            },
            request_id=request_id,
            ip=ip,
        )
    )
