"""API keys (03c): create, list, change and revoke a project's keys.

Every member from analyst up manages their own keys; a project admin sees and revokes all
(`?all=true`). Only an admin grants `impersonate`, and nobody gives a key an `acl_role` above
their own. The raw key is in the create response only; lists and audit show the prefix.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, invalid, not_found
from ffcore.api.keys_schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyList,
    ApiKeyOut,
    ApiKeyUpdate,
)
from ffcore.core.audit import audited
from ffcore.core.auth import ROLE_ORDER, Actor, require_role
from ffcore.core.errors import ApiError
from ffcore.models.keys import ApiKey
from ffcore.services import keys

router = APIRouter(
    prefix="/projects/{project_id}/api-keys", tags=["api-keys"], responses=ERROR_RESPONSES
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
_editor = require_role("analyst", write=True)


async def _console_writer(actor: Annotated[Actor, Depends(_editor)]) -> Actor:
    """Keys are minted, changed and revoked only from the user's own console session: never by a
    service or an impersonating key acting for the user (07's approval_requires_user_session)."""
    if actor.via_service:
        raise ApiError(
            403,
            "permission_error",
            "requires_console_session",
            "API keys are managed from the console session only.",
        )
    return actor


# The 03a mutation scan (test_03a_3) finds the write=True requirement inside _console_writer.
Writer = Annotated[Actor, Depends(_console_writer)]


def key_out(row: ApiKey) -> ApiKeyOut:
    return ApiKeyOut(
        id=row.id,
        project_id=row.project_id,
        name=row.name,
        key_prefix=row.key_prefix,
        scopes=list(row.scopes),
        acl_role=row.acl_role,
        allowed_cidrs=[str(c) for c in row.allowed_cidrs or []],
        expires_at=row.expires_at,
        last_used_at=row.last_used_at,
        revoked_at=row.revoked_at,
        created_by=row.created_by,
        created_at=row.created_at,
    )


def _is_admin(request: Request) -> bool:
    return request.state.grant.role == "admin"


def _check_grants(request: Request, scopes, acl_role) -> None:
    """impersonate is an admin's to give; a key's acl_role never exceeds its creator's role."""
    role = request.state.grant.role
    if scopes is not None and "impersonate" in scopes and role != "admin":
        raise ApiError(
            403, "permission_error", "scope_not_allowed", "Only a project admin grants impersonate."
        )
    if acl_role is not None and ROLE_ORDER.index(acl_role) > ROLE_ORDER.index(role):
        raise ApiError(
            403, "permission_error", "scope_not_allowed", "A key's acl_role exceeds your role."
        )


def _check_cidrs(scopes, cidrs) -> None:
    """The strongest scope is never usable from anywhere (K-03c-0006 item 4)."""
    if "impersonate" in {str(s) for s in scopes} and not cidrs:
        raise invalid(
            "cidrs_required_for_impersonate", "A key with impersonate needs allowed_cidrs."
        )


async def _key(session, project_id: UUID, key_id: UUID, actor: Actor, request: Request) -> ApiKey:
    """A key the caller may see: their own, or any for a project admin; else 404 (no leak)."""
    query = select(ApiKey).where(
        ApiKey.id == key_id, ApiKey.project_id == project_id, ApiKey.deleted_at.is_(None)
    )
    if not _is_admin(request):
        query = query.where(ApiKey.created_by == actor.actor_id)
    row = await session.scalar(query)
    if row is None:
        raise not_found("api_key")
    return row


@router.post("", response_model=ApiKeyCreated, status_code=201, summary="Create an API key")
@audited("create_api_key", "api_key")
async def create_api_key(
    project_id: UUID, body: ApiKeyCreate, request: Request, actor: Writer, session: SessionDep
):
    _check_grants(request, body.scopes, body.acl_role)
    _check_cidrs(body.scopes, body.allowed_cidrs)
    raw, prefix, digest = keys.new_key()
    row = ApiKey(
        project_id=project_id,
        name=body.name,
        key_prefix=prefix,
        key_hash=digest,
        scopes=sorted({s.value for s in body.scopes}),
        acl_role=body.acl_role.value,
        allowed_cidrs=[str(c) for c in body.allowed_cidrs],
        expires_at=body.expires_at,
        created_by=actor.actor_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    # `key` is masked in the audit row by name (core/audit.py SECRET_KEY_MARKERS).
    return ApiKeyCreated(**key_out(row).model_dump(), key=raw)


@router.get("", response_model=ApiKeyList, summary="List API keys (own; all for an admin)")
async def list_api_keys(
    project_id: UUID, request: Request, actor: Reader, session: SessionDep, all: bool = False
):
    if all and not _is_admin(request):
        raise ApiError(
            403, "permission_error", "insufficient_role", "Only a project admin lists all keys."
        )
    query = select(ApiKey).where(ApiKey.project_id == project_id, ApiKey.deleted_at.is_(None))
    if not all:
        query = query.where(ApiKey.created_by == actor.actor_id)
    rows = await session.scalars(query.order_by(ApiKey.created_at, ApiKey.id))
    return ApiKeyList(data=[key_out(r) for r in rows])


@router.get("/{key_id}", response_model=ApiKeyOut, summary="Get an API key")
async def get_api_key(
    project_id: UUID, key_id: UUID, request: Request, actor: Reader, session: SessionDep
):
    return key_out(await _key(session, project_id, key_id, actor, request))


async def _before(project_id, key_id, request, actor, session, **_):
    return key_out(await _key(session, project_id, key_id, actor, request))


@router.patch("/{key_id}", response_model=ApiKeyOut, summary="Change an API key")
@audited("update_api_key", "api_key", load_before=_before)
async def update_api_key(
    project_id: UUID,
    key_id: UUID,
    body: ApiKeyUpdate,
    request: Request,
    actor: Writer,
    session: SessionDep,
):
    row = await _key(session, project_id, key_id, actor, request)
    if row.revoked_at is not None:
        raise conflict("api_key_revoked", "A revoked key cannot be changed.")
    changes = body.model_dump(exclude_unset=True)
    _check_grants(request, changes.get("scopes"), changes.get("acl_role"))
    _check_cidrs(changes.get("scopes", row.scopes), changes.get("allowed_cidrs", row.allowed_cidrs))
    for field, value in changes.items():
        if field == "scopes":
            value = sorted({str(s) for s in value})
        elif field == "allowed_cidrs":
            value = [str(c) for c in value]
        elif field == "acl_role":
            value = str(value)
        setattr(row, field, value)
    await session.flush()
    await session.refresh(row)
    return key_out(row)


@router.post("/{key_id}/revoke", response_model=ApiKeyOut, summary="Revoke an API key")
@audited("revoke_api_key", "api_key", load_before=_before)
async def revoke_api_key(
    project_id: UUID, key_id: UUID, request: Request, actor: Writer, session: SessionDep
):
    row = await _key(session, project_id, key_id, actor, request)
    if row.revoked_at is not None:
        raise conflict("api_key_revoked", "The key is already revoked.")
    row.revoked_at = func.now()
    await session.flush()
    await session.refresh(row)
    return key_out(row)
