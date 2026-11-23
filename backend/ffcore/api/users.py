"""Users (superadmin only)."""

import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.schemas import UserCreate, UserList, UserOut, UserUpdate
from ffcore.core.audit import AuditEntry, audited, request_context, write_event
from ffcore.core.auth import Actor, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.core.identity import temporary_password
from ffcore.core.passwords import hash_password
from ffcore.models.identity import User

router = APIRouter(prefix="/users", tags=["users"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_superadmin())]
Writer = Annotated[Actor, Depends(require_superadmin(write=True))]
UserIdDep = Annotated[str, Depends(path_resource("user_id"))]
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def user_out(user: User) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)


async def _get(session, user_id: UUID) -> User:
    user = await session.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise not_found("user")
    return user


async def _before(session, user_id: UUID, **_) -> UserOut:
    return user_out(await _get(session, user_id))


@router.get("", response_model=UserList, summary="List users")
async def list_users(actor: Reader, session: SessionDep):
    users = await session.scalars(
        select(User).where(User.deleted_at.is_(None)).order_by(func.lower(User.email))
    )
    return UserList(data=[user_out(u) for u in users])


@router.post("", response_model=UserOut, status_code=201, summary="Create a user")
@audited("create_user", "user")
async def create_user(body: UserCreate, request: Request, actor: Writer, session: SessionDep):
    if not EMAIL.match(body.email):
        raise invalid("invalid_email", "Email address is not valid.")
    if body.is_superadmin and body.superadmin_access is None:
        raise invalid("superadmin_access_required", "A superadmin needs an access mode.")
    taken = await session.scalar(
        select(User.id).where(
            func.lower(User.email) == body.email.lower(), User.deleted_at.is_(None)
        )
    )
    if taken is not None:
        raise conflict("email_taken", "A user with this email already exists.")
    user = User(
        email=body.email,
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        is_superadmin=body.is_superadmin,
        superadmin_access=body.superadmin_access if body.is_superadmin else None,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user_out(user)


@router.get("/{user_id}", response_model=UserOut, summary="Get a user")
async def get_user(user_id: UUID, actor: Reader, session: SessionDep):
    return user_out(await _get(session, user_id))


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user")
@audited("update_user", "user", load_before=_before)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
):
    user = await _get(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    superadmin = changes.get("is_superadmin", user.is_superadmin)
    access = changes.get("superadmin_access", user.superadmin_access)
    if superadmin and access is None:
        raise invalid("superadmin_access_required", "A superadmin needs an access mode.")
    # 17: a superadmin is always a local account (the recovery account).
    target = changes.pop("auth_source", None)
    source = target or user.auth_source
    if superadmin and source != "local":
        raise invalid("superadmin_must_be_local", "A superadmin must be a local account.")
    temporary = None
    if target is not None and target != user.auth_source:
        if target == "local":
            temporary = await _unlink(session, request, actor, user)
        else:
            await _link(session, request, actor, user, target, settings)
    for field, value in changes.items():
        setattr(user, field, value)
    if not superadmin:
        user.superadmin_access = None
    if changes.get("is_active") is False:
        user.token_version += 1  # signed out everywhere
        user.deactivated_by = "admin"  # 17 r2: never reopened by the directory
    elif changes.get("is_active") is True:
        user.deactivated_by = None
    await session.flush()
    await session.refresh(user)
    out = user_out(user)
    if temporary is not None:
        out.temporary_password = temporary  # this answer only; never stored in clear
    return out


def _provider_configured(target: str, settings: Settings) -> bool:
    # OIDC arrives with 17-2; until then no account can be linked to it.
    return settings.ldap_enabled if target == "ldap" else False


def _audit(request: Request, actor: Actor, user: User, action: str, after: dict) -> AuditEntry:
    request_id, ip = request_context(request)
    return AuditEntry(
        action=action,
        resource_type="user",
        outcome="success",
        actor_type=actor.actor_type,
        actor_id=actor.actor_id,
        resource_id=str(user.id),
        after=after,
        request_id=request_id,
        ip=ip,
    )


async def _link(session, request, actor, user: User, target: str, settings: Settings) -> None:
    """K-17-0002 S1: the password is deleted and every session ends; the next directory
    sign-in with this email binds the account (memberships and history stay)."""
    if user.auth_source != "local":
        raise invalid(
            "auth_source_change_invalid", "Only a local account can be linked to the directory."
        )
    if not _provider_configured(target, settings):
        # r1 MINOR-4: a link nobody can complete would leave the account without any sign-in.
        raise invalid(
            "identity_provider_not_configured",
            f"{target} sign-in is not configured on this installation.",
        )
    user.auth_source = target
    user.password_hash = None
    user.external_id = None
    user.must_change_password = False
    user.token_version += 1
    await write_event(
        session,
        _audit(
            request,
            actor,
            user,
            "user_identity_linked",
            {"auth_source": target, "password_deleted": True},
        ),
    )


async def _unlink(session, request, actor, user: User) -> str:
    """r1 MINOR-4: until the directory has bound the account (no external_id yet) a superadmin
    can take a link back; the account gets a temporary password it must change. Once bound, the
    directory owns the identity and there is no way back."""
    if user.auth_source == "local" or user.external_id is not None:
        raise invalid(
            "auth_source_change_invalid",
            "Only an account linked but not yet signed in through the directory can go back.",
        )
    password = temporary_password()
    previous = user.auth_source
    user.auth_source = "local"
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.token_version += 1
    await write_event(
        session, _audit(request, actor, user, "user_identity_unlinked", {"from": previous})
    )
    return password


@router.delete("/{user_id}", status_code=204, summary="Delete a user (soft delete)")
@audited("delete_user", "user", load_before=_before)
async def delete_user(
    user_id: UUID, request: Request, actor: Writer, session: SessionDep, resource_id: UserIdDep
) -> None:
    user = await _get(session, user_id)
    user.deleted_at = func.now()
    user.token_version += 1
