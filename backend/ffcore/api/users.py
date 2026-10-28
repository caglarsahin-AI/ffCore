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
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_superadmin
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
    user_id: UUID, body: UserUpdate, request: Request, actor: Writer, session: SessionDep
):
    user = await _get(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    superadmin = changes.get("is_superadmin", user.is_superadmin)
    access = changes.get("superadmin_access", user.superadmin_access)
    if superadmin and access is None:
        raise invalid("superadmin_access_required", "A superadmin needs an access mode.")
    for field, value in changes.items():
        setattr(user, field, value)
    if not superadmin:
        user.superadmin_access = None
    if changes.get("is_active") is False:
        user.token_version += 1  # signed out everywhere
    await session.flush()
    await session.refresh(user)
    return user_out(user)


@router.delete("/{user_id}", status_code=204, summary="Delete a user (soft delete)")
@audited("delete_user", "user", load_before=_before)
async def delete_user(
    user_id: UUID, request: Request, actor: Writer, session: SessionDep, resource_id: UserIdDep
) -> None:
    user = await _get(session, user_id)
    user.deleted_at = func.now()
    user.token_version += 1
