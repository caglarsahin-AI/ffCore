"""Quotas (03c, R2.1): one form for scope, windows, tokens, budget and activation.

Project members from analyst up read; a project admin changes. Enforcement is the backend's
quota engine (services/quota.py, Redis); nothing is written to LiteLLM (A4). A budget is refused
while an active model of the project has no price (FOLLOWUP-69): it would count 0 and never stop.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, invalid, not_found, path_resource
from ffcore.api.quotas_schemas import (
    QuotaBudget,
    QuotaCreate,
    QuotaList,
    QuotaOut,
    QuotaTokens,
    QuotaUpdate,
    QuotaWindows,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.models.catalog import Model
from ffcore.models.identity import ProjectMember
from ffcore.models.keys import ApiKey
from ffcore.models.quota import Quota
from ffcore.services.quota import pricing_missing

router = APIRouter(
    prefix="/projects/{project_id}/quotas", tags=["quotas"], responses=ERROR_RESPONSES
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
Writer = Annotated[Actor, Depends(require_role("admin", write=True))]
QuotaIdDep = Annotated[str, Depends(path_resource("quota_id"))]


def quota_out(row: Quota) -> QuotaOut:
    return QuotaOut(
        id=row.id,
        project_id=row.project_id,
        scope_type=row.scope_type,
        scope_id=row.scope_id,
        label=row.label,
        priority=row.priority,
        windows=QuotaWindows(**(row.windows or {})),
        tokens=QuotaTokens(**(row.tokens or {})),
        budget=QuotaBudget(**(row.budget or {})),
        action=row.action,
        is_active=row.is_active,
        activate_at=row.activate_at,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _parts(windows: QuotaWindows, tokens: QuotaTokens, budget: QuotaBudget) -> dict:
    """JSON columns without the unset limits; money as a string (exact decimal)."""
    money = {k: str(v) for k, v in budget.model_dump(exclude_none=True).items()}
    return {
        "windows": windows.model_dump(exclude_none=True),
        "tokens": tokens.model_dump(exclude_none=True),
        "budget": money,
    }


async def _validate(session, project_id: UUID, scope_type: str, scope_id, parts: dict) -> UUID:
    if not any(parts.values()):
        raise invalid("quota_empty", "A quota needs at least one limit.")
    if scope_type == "project":
        if scope_id not in (None, project_id):
            raise invalid("scope_id_invalid", "A project quota is for this project.")
        scope_id = project_id
    elif scope_id is None:
        raise invalid("scope_id_required", "An api_key or user quota needs scope_id.")
    elif scope_type == "api_key":
        key = await session.scalar(
            select(ApiKey.id).where(
                ApiKey.id == scope_id, ApiKey.project_id == project_id, ApiKey.deleted_at.is_(None)
            )
        )
        if key is None:
            raise invalid("scope_id_invalid", "No such API key in this project.")
    else:
        member = await session.scalar(
            select(ProjectMember.user_id).where(
                ProjectMember.project_id == project_id, ProjectMember.user_id == scope_id
            )
        )
        if member is None:
            raise invalid("scope_id_invalid", "The user is not a member of this project.")
    if parts["budget"]:
        models = await session.scalars(
            select(Model.pricing).where(
                Model.project_id == project_id,
                Model.category == "llm",
                Model.is_active,
                Model.deleted_at.is_(None),
            )
        )
        unpriced = sum(1 for pricing in models if pricing_missing(pricing))
        if unpriced:
            raise invalid(
                "pricing_missing",
                f"{unpriced} active model(s) of the project have no price; set prices before"
                " a USD budget (it would count 0).",
            )
    return scope_id


async def _get(session, project_id: UUID, quota_id: UUID) -> Quota:
    row = await session.scalar(
        select(Quota).where(
            Quota.id == quota_id, Quota.project_id == project_id, Quota.deleted_at.is_(None)
        )
    )
    if row is None:
        raise not_found("quota")
    return row


@router.get("", response_model=QuotaList, summary="List the project's quotas")
async def list_quotas(project_id: UUID, actor: Reader, session: SessionDep):
    rows = await session.scalars(
        select(Quota)
        .where(Quota.project_id == project_id, Quota.deleted_at.is_(None))
        .order_by(Quota.priority.desc(), Quota.created_at, Quota.id)
    )
    return QuotaList(data=[quota_out(r) for r in rows])


@router.post("", response_model=QuotaOut, status_code=201, summary="Create a quota")
@audited("create_quota", "quota")
async def create_quota(
    project_id: UUID, body: QuotaCreate, request: Request, actor: Writer, session: SessionDep
):
    parts = _parts(body.windows, body.tokens, body.budget)
    scope_id = await _validate(session, project_id, body.scope_type, body.scope_id, parts)
    row = Quota(
        project_id=project_id,
        scope_type=body.scope_type.value,
        scope_id=scope_id,
        label=body.label,
        priority=body.priority,
        action=body.action.value,
        is_active=body.is_active,
        activate_at=body.activate_at,
        created_by=actor.actor_id,
        **parts,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return quota_out(row)


@router.get("/{quota_id}", response_model=QuotaOut, summary="Get a quota")
async def get_quota(project_id: UUID, quota_id: UUID, actor: Reader, session: SessionDep):
    return quota_out(await _get(session, project_id, quota_id))


async def _before(project_id, quota_id, session, **_):
    return quota_out(await _get(session, project_id, quota_id))


@router.patch("/{quota_id}", response_model=QuotaOut, summary="Change a quota")
@audited("update_quota", "quota", load_before=_before)
async def update_quota(
    project_id: UUID,
    quota_id: UUID,
    body: QuotaUpdate,
    request: Request,
    actor: Writer,
    session: SessionDep,
):
    row = await _get(session, project_id, quota_id)
    changes = body.model_dump(exclude_unset=True)
    current = quota_out(row)
    parts = _parts(
        body.windows if "windows" in changes else current.windows,
        body.tokens if "tokens" in changes else current.tokens,
        body.budget if "budget" in changes else current.budget,
    )
    await _validate(session, project_id, row.scope_type, row.scope_id, parts)
    for field in ("label", "priority", "is_active", "activate_at"):
        if field in changes:
            setattr(row, field, changes[field])
    if "action" in changes:
        row.action = str(changes["action"])
    row.windows, row.tokens, row.budget = parts["windows"], parts["tokens"], parts["budget"]
    await session.flush()
    await session.refresh(row)
    return quota_out(row)


@router.delete("/{quota_id}", status_code=204, summary="Delete a quota (soft delete)")
@audited("delete_quota", "quota", load_before=_before)
async def delete_quota(
    project_id: UUID,
    quota_id: UUID,
    request: Request,
    actor: Writer,
    session: SessionDep,
    resource_id: QuotaIdDep,
) -> None:
    row = await _get(session, project_id, quota_id)
    row.deleted_at = func.now()
