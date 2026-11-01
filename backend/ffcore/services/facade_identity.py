"""Who calls the facade (06b): an API key, or a user an `impersonate` key acts for.

`resolve_actor()` (C2) stays the single verification point: it has already checked the key and,
with `X-On-Behalf-Of`, turned it into the user. This module adds what only the facade has, the
OpenAI `user` field (an e-mail), after resolve_actor and with the same rules (B7, S1):

- without the `impersonate` scope the field is only a log label; the refusal is audited;
- with it, the e-mail must name an active user who is a member of the key's project; anything
  else answers the one `403 impersonation_denied` resolve_actor uses, byte for byte, so an
  outsider cannot tell an unknown e-mail from a non-member (the reason is in the audit row).
"""

import uuid
from dataclasses import dataclass, replace

from fastapi import Request
from sqlalchemy import func, select

from ffcore.core import db
from ffcore.core.auth import Actor, _impersonation_denied
from ffcore.core.config import Settings
from ffcore.core.errors import ApiError
from ffcore.models.identity import ProjectMember, User
from ffcore.models.keys import ApiKey


@dataclass(frozen=True)
class FacadeCaller:
    actor: Actor  # who acts: the key itself, or the user it acts for
    key_id: str
    project_id: str
    scopes: frozenset[str]  # the key's scopes (also when it acts for a user)
    label: str | None = None  # the client's `user` value when it is not an actor

    @property
    def user_id(self) -> str | None:
        return self.actor.actor_id if self.actor.actor_type == "user" else None


def api_key_required() -> ApiError:
    return ApiError(
        401, "authentication_error", "api_key_required", "The facade accepts API keys only."
    )


def scope_missing(scope: str) -> ApiError:
    return ApiError(
        403, "permission_error", "scope_missing", f"The API key lacks the '{scope}' scope."
    )


def require_scope(caller: FacadeCaller, scope: str) -> None:
    if scope not in caller.scopes:
        raise scope_missing(scope)


async def _key_scopes(key_id: str) -> frozenset[str]:
    async with db.session_scope() as session:
        scopes = await session.scalar(select(ApiKey.scopes).where(ApiKey.id == uuid.UUID(key_id)))
    return frozenset(scopes or ())


async def _denied(request: Request, key: Actor, reason: str, settings: Settings) -> None:
    from ffcore.core.audit import record_impersonation_denied

    # The e-mail is not written: the audit row names the key, the field and why.
    await record_impersonation_denied(
        request, key, {"header": "user", "reason": reason}, settings=settings
    )


async def _member_user(email: str, project_id: str) -> tuple[str | None, str]:
    """(user id, reason): the reason is `user_not_mapped` or `not_member` when id is None."""
    async with db.session_scope() as session:
        user_id = await session.scalar(
            select(User.id).where(
                func.lower(User.email) == email.strip().lower(),
                User.deleted_at.is_(None),
                User.is_active,
            )
        )
        if user_id is None:
            return None, "user_not_mapped"
        member = await session.scalar(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == uuid.UUID(project_id),
                ProjectMember.user_id == user_id,
            )
        )
    return (str(user_id), "") if member is not None else (None, "not_member")


async def facade_caller(
    request: Request, actor: Actor, settings: Settings, user_field: str | None
) -> FacadeCaller:
    if actor.actor_type == "api_key":
        key = actor
        caller = FacadeCaller(
            actor=key, key_id=key.actor_id, project_id=key.project_id or "", scopes=key.scopes
        )
    elif actor.actor_type == "user" and actor.via_key_id is not None:
        # X-On-Behalf-Of through an impersonate key (resolve_actor); the key's scopes still bound
        # what the call may do. The `user` field is then only a label.
        return FacadeCaller(
            actor=actor,
            key_id=actor.via_key_id,
            project_id=actor.project_id or "",
            scopes=await _key_scopes(actor.via_key_id),
            label=user_field,
        )
    else:
        # A console session or the service account: not a facade client.
        raise api_key_required()

    if not user_field:
        return caller
    if not key.may_impersonate:
        await _denied(request, key, "scope_missing", settings)
        return replace(caller, label=user_field)
    user_id, reason = await _member_user(user_field, caller.project_id)
    if user_id is None:
        await _denied(request, key, reason, settings)
        raise _impersonation_denied()
    return replace(
        caller,
        actor=Actor(
            actor_type="user",
            actor_id=user_id,
            project_id=caller.project_id,
            via_service=True,
            via_key_id=key.actor_id,
        ),
    )
