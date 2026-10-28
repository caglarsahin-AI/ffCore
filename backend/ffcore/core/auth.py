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
