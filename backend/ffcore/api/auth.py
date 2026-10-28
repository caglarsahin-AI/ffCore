"""Login, logout, current user and own password (03a)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.common import ERROR_RESPONSES
from ffcore.api.schemas import (
    CurrentUser,
    LoginRequest,
    Membership,
    MeResponse,
    PasswordChangeRequest,
)
from ffcore.core import db
from ffcore.core.audit import (
    AuditEntry,
    audited,
    request_context,
    write_event,
    write_event_detached,
)
from ffcore.core.auth import ROLE_ORDER, Actor, resolve_actor
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.core.passwords import hash_password, needs_rehash, verify_password
from ffcore.core.session import clear_session_cookie, issue_token, set_session_cookie
from ffcore.models.identity import Project, ProjectMember, User

router = APIRouter(prefix="/auth", tags=["auth"], responses=ERROR_RESPONSES)

SessionDep = Annotated[AsyncSession, Depends(db.get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def user_actor(actor: Annotated[Actor, Depends(resolve_actor)]) -> Actor:
    if actor.actor_type != "user":
        raise ApiError(403, "permission_error", "user_required", "Only users have a profile.")
    return actor


async def session_user_actor(actor: Annotated[Actor, Depends(user_actor)]) -> Actor:
    # A service acting for a user cannot sign the user out or change the password.
    if actor.via_service:
        raise ApiError(403, "permission_error", "session_required", "Requires a console session.")
    return actor


async def _load_user(session: AsyncSession, actor: Actor) -> User:
    user = await session.scalar(
        select(User).where(User.id == uuid.UUID(actor.actor_id), User.deleted_at.is_(None))
    )
    if user is None or not user.is_active:
        raise ApiError(401, "authentication_error", "unauthenticated", "Authentication required.")
    return user


async def me_payload(
    session: AsyncSession, user: User, obo_project: str | None = None
) -> MeResponse:
    """`obo_project`: a call on behalf of the user sees only that project and no superadmin
    rights (K-03a-0007)."""
    query = (
        select(ProjectMember.project_id, Project.key, ProjectMember.role, ProjectMember.access)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(ProjectMember.user_id == user.id, Project.deleted_at.is_(None))
        .order_by(Project.key)
    )
    if obo_project is not None:
        query = query.where(Project.id == uuid.UUID(obo_project))
    memberships = [
        Membership(project_id=pid, project_key=key, role=role, access=access)
        for pid, key, role, access in await session.execute(query)
    ]
    if user.is_superadmin and obo_project is None:
        role, access = "admin", user.superadmin_access
    elif memberships:
        top = max(memberships, key=lambda m: ROLE_ORDER.index(m.role))
        role, access = top.role, top.access
    else:
        role = access = None
    return MeResponse(
        user=CurrentUser(
            id=user.id, email=user.email, full_name=user.full_name, is_superadmin=user.is_superadmin
        ),
        role=role,
        access=access,
        memberships=memberships,
    )


@router.post("/login", response_model=MeResponse, summary="Sign in with email and password")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
):
    """Sets the `ffcore_session` cookie (HttpOnly, SameSite=Strict, Secure). A wrong email or
    password gives the same 401 `invalid_credentials`."""
    request_id, ip = request_context(request)
    user = await session.scalar(
        select(User).where(func.lower(User.email) == body.email.lower(), User.deleted_at.is_(None))
    )
    usable = user is not None and user.is_active
    if not verify_password(user.password_hash if usable else None, body.password):
        # No email in the record: a failed login must not store what someone typed.
        await write_event_detached(
            AuditEntry(
                action="auth.login",
                resource_type="auth",
                outcome="denied",
                actor_type="system",
                actor_id="anonymous",
                after={"code": "invalid_credentials"},
                request_id=request_id,
                ip=ip,
            )
        )
        raise ApiError(
            401, "authentication_error", "invalid_credentials", "Email or password is incorrect."
        )
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    await write_event(
        session,
        AuditEntry(
            action="auth.login",
            resource_type="user",
            outcome="success",
            actor_type="user",
            actor_id=str(user.id),
            resource_id=str(user.id),
            request_id=request_id,
            ip=ip,
        ),
    )
    await session.commit()
    set_session_cookie(response, issue_token(str(user.id), user.token_version, settings), settings)
    return await me_payload(session, user)


@router.post("/logout", status_code=204, summary="Sign out")
@audited("auth.logout", "user")
async def logout(
    request: Request,
    response: Response,
    actor: Annotated[Actor, Depends(session_user_actor)],
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """Clears the cookie and revokes every session token of the user."""
    user = await _load_user(session, actor)
    user.token_version += 1
    clear_session_cookie(response, settings)


@router.get("/me", response_model=MeResponse, summary="Current user, role and access mode")
async def me(actor: Annotated[Actor, Depends(user_actor)], session: SessionDep):
    obo_project = actor.project_id if actor.via_service else None
    return await me_payload(session, await _load_user(session, actor), obo_project)


@router.post("/password", status_code=204, summary="Change own password")
@audited("auth.password_change", "user", audit_payload=False)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    actor: Annotated[Actor, Depends(session_user_actor)],
    session: SessionDep,
    settings: SettingsDep,
) -> None:
    """Allowed in read-only access mode (own data). Revokes other sessions."""
    user = await _load_user(session, actor)
    if not verify_password(user.password_hash, body.current_password):
        raise ApiError(
            400, "invalid_request_error", "invalid_current_password", "Password is incorrect."
        )
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    set_session_cookie(response, issue_token(str(user.id), user.token_version, settings), settings)
