"""Audit trail: every mutation writes exactly one audit_events row (PLAN 5, 03b).

`@audited` wraps a FastAPI mutation endpoint. The endpoint declares three parameters by name:
`request: Request`, `actor` (from `resolve_actor` or a role dependency) and `session`
(`db.get_session`). On success the decorator writes the event in the endpoint's transaction and
commits both together, so endpoints under `@audited` do not commit themselves. A denial (401/403)
or an error rolls the endpoint's work back and records the outcome in a separate transaction, so
the record survives the rollback.
"""

import functools
import inspect
import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from ffcore.core import db
from ffcore.core.errors import ApiError
from ffcore.models.audit import AuditEvent

MASK = "***"
# A key containing any of these (case-insensitive) is masked, at any depth.
SECRET_KEY_MARKERS = ("password", "key", "token", "secret")
_REQUIRED_PARAMS = ("request", "actor", "session")


@dataclass(frozen=True)
class AuditEntry:
    action: str
    resource_type: str
    outcome: str
    actor_type: str
    actor_id: str
    project_id: str | None = None
    resource_id: str | None = None
    before: Any = None
    after: Any = None
    request_id: str | None = None
    ip: str | None = None


def mask(value: Any, redact_fields: Iterable[str] = ()) -> Any:
    extra = {field.lower() for field in redact_fields}

    def walk(item: Any) -> Any:
        if isinstance(item, dict):
            return {
                key: MASK
                if isinstance(key, str)
                and (key.lower() in extra or any(m in key.lower() for m in SECRET_KEY_MARKERS))
                else walk(child)
                for key, child in item.items()
            }
        if isinstance(item, list | tuple):
            return [walk(child) for child in item]
        return item

    return walk(value)


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return jsonable_encoder(value)


def _event(entry: AuditEntry) -> AuditEvent:
    return AuditEvent(
        id=uuid.uuid4(),
        ts=datetime.now(UTC),
        actor_type=entry.actor_type,
        actor_id=entry.actor_id,
        project_id=uuid.UUID(entry.project_id) if entry.project_id else None,
        action=entry.action,
        resource_type=entry.resource_type,
        resource_id=entry.resource_id,
        outcome=entry.outcome,
        before=entry.before,
        after=entry.after,
        request_id=entry.request_id,
        ip=entry.ip,
    )


async def write_event(session: AsyncSession, entry: AuditEntry) -> None:
    """Add the event to the caller's transaction (committed with the mutation)."""
    session.add(_event(entry))
    await session.flush()


async def write_event_detached(entry: AuditEntry) -> None:
    """Write the event in its own transaction (denials, errors, security events)."""
    async with db.session_scope() as session:
        session.add(_event(entry))
        await session.commit()


def request_context(request: Request) -> tuple[str, str | None]:
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    ip = request.client.host if request.client else None
    try:
        import ipaddress

        ipaddress.ip_address(ip or "")
    except ValueError:
        ip = None
    return request_id, ip


async def record_impersonation_denied(request: Request, actor) -> None:
    request_id, ip = request_context(request)
    await write_event_detached(
        AuditEntry(
            action="impersonation_denied",
            resource_type="auth",
            outcome="denied",
            actor_type=actor.actor_type if actor else "system",
            actor_id=actor.actor_id if actor else "anonymous",
            project_id=actor.project_id if actor else None,
            after={"path": request.url.path, "header": "X-On-Behalf-Of"},
            request_id=request_id,
            ip=ip,
        )
    )


def _status_of(exc: Exception) -> int | None:
    if isinstance(exc, ApiError | HTTPException):
        return exc.status_code
    return None


def audited(
    action: str,
    resource_type: str,
    *,
    redact_fields: Iterable[str] = (),
    audit_payload: bool = True,
    load_before: Callable[..., Awaitable[Any]] | None = None,
):
    """Record one audit event per call of the wrapped mutation endpoint.

    `audit_payload=False` records the event without before/after content (14: memory text).
    """
    redact = tuple(redact_fields)

    def decorate(endpoint):
        if not inspect.iscoroutinefunction(endpoint):
            raise TypeError(f"@audited needs an async endpoint: {endpoint.__name__}")
        missing = [p for p in _REQUIRED_PARAMS if p not in inspect.signature(endpoint).parameters]
        if missing:
            raise TypeError(f"@audited endpoint {endpoint.__name__} lacks parameters {missing}")

        @functools.wraps(endpoint)
        async def wrapper(*args, **kwargs):
            request: Request = kwargs["request"]
            actor = kwargs["actor"]
            session: AsyncSession = kwargs["session"]
            request_id, ip = request_context(request)

            def entry(outcome: str, before=None, after=None) -> AuditEntry:
                resource_id = kwargs.get("resource_id")
                if resource_id is None and isinstance(after, dict):
                    resource_id = after.get("id")
                project_id = actor.project_id
                if isinstance(after, dict) and after.get("project_id"):
                    project_id = str(after["project_id"])
                return AuditEntry(
                    action=action,
                    resource_type=resource_type,
                    outcome=outcome,
                    actor_type=actor.actor_type,
                    actor_id=actor.actor_id,
                    project_id=project_id,
                    resource_id=str(resource_id) if resource_id is not None else None,
                    before=mask(before, redact) if audit_payload else None,
                    after=mask(after, redact) if audit_payload else None,
                    request_id=request_id,
                    ip=ip,
                )

            before = _jsonable(await load_before(**kwargs)) if load_before else None
            try:
                result = await endpoint(*args, **kwargs)
            except Exception as exc:
                await session.rollback()
                status = _status_of(exc)
                outcome = "denied" if status in (401, 403) else "error"
                await write_event_detached(entry(outcome, before=before))
                raise
            after = _jsonable(result)
            await write_event(session, entry("success", before=before, after=after))
            await session.commit()
            return result

        return wrapper

    return decorate


async def ensure_audit_partitions(months: int = 2) -> list[str]:
    """Create this month's partition and the next `months - 1` (idempotent); returns their names."""
    if months < 1:
        raise ValueError("months must be at least 1")
    today = datetime.now(UTC).date().replace(day=1)
    names = []
    async with db.session_scope() as session:
        for offset in range(months):
            month = today
            for _ in range(offset):
                month = (month + timedelta(days=32)).replace(day=1)
            result = await session.execute(
                text("SELECT ffcore_audit_ensure_partition(:month)"), {"month": month}
            )
            names.append(result.scalar_one())
        await session.commit()
    return names
