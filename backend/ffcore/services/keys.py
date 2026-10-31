"""API keys (03c): issuing, hashing and the credential resolver behind resolve_actor (C2).

A key reads `ffk_<8 hex>_<43 urlsafe>`; the first two parts are its public prefix (unique,
shown in lists and audit), the whole string's SHA-256 is stored. The value is random with
256 bits of entropy, so a fast hash is enough; comparison is constant-time.

Every request with a key checks, in this order: the client address's failure budget
(`API_KEY_AUTH_FAILURES_PER_MIN`, Redis, 429), the key itself (unknown prefix, wrong secret,
revoked, expired or deleted project all answer the same 401), then `allowed_cidrs` (403
ip_not_allowed). An unknown prefix still runs one comparison so the answer takes the same time.
"""

import hashlib
import hmac
import ipaddress
import logging
import secrets
import time
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import select, update

from ffcore.core import db
from ffcore.core.auth import Actor, Grant
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.models.identity import Project
from ffcore.models.keys import ApiKey

log = logging.getLogger("ffcore.keys")

KEY_SCHEME = "ffk"
_PREFIX_HEX = 8
# Compared against when the prefix is unknown: same work, never equal to a real digest.
_NO_KEY_HASH = "0" * 64
_FAILURE_WINDOW_S = 60


def new_key() -> tuple[str, str, str]:
    """(raw key, public prefix, key_hash)."""
    prefix = f"{KEY_SCHEME}_{secrets.token_hex(_PREFIX_HEX // 2)}"
    raw = f"{prefix}_{secrets.token_urlsafe(32)}"
    return raw, prefix, key_hash(raw)


def key_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _prefix_of(raw: str) -> str | None:
    scheme, _, rest = raw.partition("_")
    head, sep, secret = rest.partition("_")
    if scheme != KEY_SCHEME or not sep or not secret or len(head) != _PREFIX_HEX:
        return None
    return f"{KEY_SCHEME}_{head}"


def address_allowed(ip: str | None, cidrs) -> bool:
    if not cidrs:
        return True
    try:
        address = ipaddress.ip_address(ip or "")
    except ValueError:
        return False
    return any(address in ipaddress.ip_network(str(c), strict=False) for c in cidrs)


def acl_role_of(actor: Actor, grant: Grant | None) -> str | None:
    """The role a search runs under: the key's acl_role when the key itself is the actor,
    otherwise the user's project role (also after impersonate; K-03c-0004 condition 1)."""
    if actor.actor_type == "api_key":
        return actor.acl_role
    return grant.role if grant is not None else None


def _invalid() -> ApiError:
    return ApiError(401, "authentication_error", "invalid_api_key", "The API key is not valid.")


def _backend_unavailable() -> ApiError:
    # Fail closed: without the failure budget a key cannot be checked safely (r1 MAJOR-1 (3));
    # nothing is written to the audit trail then (it would be unbounded again).
    log.error("auth_backend_unavailable reason=redis")
    return ApiError(503, "api_error", "auth_backend_unavailable", "API key checks are unavailable.")


def _redis(settings: Settings):
    import redis.asyncio as aioredis

    if settings.redis_url is None:
        raise _backend_unavailable()
    return aioredis.from_url(settings.redis_url.get_secret_value())


def _failure_key(ip: str) -> str:
    return f"ffcore:keys:authfail:{ip}:{int(time.time()) // _FAILURE_WINDOW_S}"


async def _rate_limited(request: Request, settings: Settings, failures: int) -> ApiError:
    """At most one audit row per address and minute (r1 MAJOR-1); the next window's row
    carries how many were held back, and all addresses together are capped."""
    from ffcore.core.audit import (
        AuditEntry,
        AuditThrottleUnavailable,
        request_context,
        write_event_throttled,
    )

    request_id, audit_ip = request_context(request)
    entry = AuditEntry(
        action="api_key_auth_rate_limited",
        resource_type="auth",
        outcome="denied",
        actor_type="system",
        actor_id="anonymous",
        after={"path": request.url.path, "failures_at_block": failures},
        request_id=request_id,
        ip=audit_ip,
    )
    try:
        await write_event_throttled(entry, key=f"keys:{audit_ip}", settings=settings)
    except AuditThrottleUnavailable:
        raise _backend_unavailable() from None
    return ApiError(
        429, "rate_limit_error", "too_many_auth_failures", "Too many failed API key attempts."
    )


async def api_key_resolver(request: Request, settings: Settings) -> Actor | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token.startswith(f"{KEY_SCHEME}_"):
        return None
    ip = request.client.host if request.client else ""
    redis = _redis(settings)
    failures = _failure_key(ip)
    try:
        try:
            count = int(await redis.get(failures) or 0)
        except Exception:  # noqa: BLE001 - Redis down: 503, never an unchecked key
            raise _backend_unavailable() from None
        if count >= settings.api_key_auth_failures_per_min:
            raise await _rate_limited(request, settings, count)
        row = await _verify(token)
        if row is None:
            try:
                async with redis.pipeline(transaction=True) as pipe:
                    await pipe.incr(failures).expire(failures, _FAILURE_WINDOW_S).execute()
            except Exception:  # noqa: BLE001
                raise _backend_unavailable() from None
            raise _invalid()
    finally:
        await redis.aclose()
    if not address_allowed(ip, row.allowed_cidrs):
        raise ApiError(
            403, "permission_error", "ip_not_allowed", "This address may not use this API key."
        )
    await _touch(row, settings)
    return Actor(
        actor_type="api_key",
        actor_id=str(row.id),
        project_id=str(row.project_id),
        scopes=frozenset(row.scopes),
        acl_role=row.acl_role,
    )


async def _verify(token: str) -> ApiKey | None:
    prefix = _prefix_of(token)
    row = None
    if prefix is not None:
        async with db.session_scope() as session:
            row = await session.scalar(
                select(ApiKey)
                .join(Project, Project.id == ApiKey.project_id)
                .where(
                    ApiKey.key_prefix == prefix,
                    ApiKey.deleted_at.is_(None),
                    Project.deleted_at.is_(None),
                )
            )
    expected = row.key_hash if row is not None else _NO_KEY_HASH
    matches = hmac.compare_digest(key_hash(token), expected)
    if row is None or not matches:
        return None
    now = datetime.now(UTC)
    if row.revoked_at is not None or (row.expires_at is not None and row.expires_at <= now):
        return None
    return row


async def _touch(row: ApiKey, settings: Settings) -> None:
    now = datetime.now(UTC)
    flush = timedelta(seconds=settings.api_key_last_used_flush_s)
    if row.last_used_at is not None and now - row.last_used_at < flush:
        return
    async with db.session_scope() as session:
        await session.execute(
            update(ApiKey)
            .where(ApiKey.id == row.id)
            .values(last_used_at=now)
            .execution_options(synchronize_session=False)
        )
        await session.commit()
