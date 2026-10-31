"""Retention (03c, R2.2): policies, dry run, run and the record of removals. Superadmin only.

`PUT /retention/policies/{data_class}` sets the installation value or, with `project_id`, a
project override; the value must lie within the class's min/max (422 retention_out_of_range).
`POST /retention/dry-run` counts and records; `POST /retention/run` removes now, whatever
RETENTION_DRY_RUN says (brief: "şimdi temizle" always removes); audit partitions still need
RETENTION_AUDIT_DROP_ENABLED. `GET /retention/runs` is the removal record (append-only).
"""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from ffcore.api.common import ERROR_RESPONSES, SessionDep, conflict, invalid, not_found
from ffcore.api.schemas import Strict
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.models.retention import RETENTION_CLASSES, RetentionPolicy, RetentionRun
from ffcore.services import retention_job

router = APIRouter(prefix="/retention", tags=["retention"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_superadmin())]
Writer = Annotated[Actor, Depends(require_superadmin(write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
DataClass = StrEnum("DataClass", {k: k for k in RETENTION_CLASSES})


class PolicyOut(BaseModel):
    data_class: DataClass
    project_id: UUID | None = Field(description="Null: the installation value; set: an override.")
    keep_days: int
    min_days: int
    max_days: int
    expiry_behavior: str = Field(description="delete, or clear_content (content: text only).")
    source: str = Field(description="default (the brief's value) or override.")
    updated_at: datetime
    updated_by: str


class PolicyList(BaseModel):
    dry_run_default: bool = Field(description="RETENTION_DRY_RUN: the daily job only counts.")
    audit_drop_enabled: bool = Field(description="RETENTION_AUDIT_DROP_ENABLED.")
    data: list[PolicyOut]


class PolicyUpdate(Strict):
    keep_days: int
    project_id: UUID | None = None


class RunResult(BaseModel):
    data_class: DataClass
    project_id: UUID | None
    cutoff: datetime | None
    counts: dict[str, Any]
    status: str
    error_code: str | None


class RunResults(BaseModel):
    dry_run: bool
    data: list[RunResult]


class RunRecord(RunResult):
    id: UUID
    ts: datetime
    trigger: str
    dry_run: bool
    actor_id: str


class RunRecords(BaseModel):
    data: list[RunRecord]


def policy_out(row: RetentionPolicy) -> PolicyOut:
    keep, *_ = RETENTION_CLASSES[row.data_class]
    source = "override" if row.project_id is not None or row.keep_days != keep else "default"
    return PolicyOut(
        data_class=row.data_class,
        project_id=row.project_id,
        keep_days=row.keep_days,
        min_days=row.min_days,
        max_days=row.max_days,
        expiry_behavior=row.expiry_behavior,
        source=source,
        updated_at=row.updated_at,
        updated_by=row.updated_by,
    )


@router.get("/policies", response_model=PolicyList, summary="Retention classes and overrides")
async def list_policies(actor: Reader, session: SessionDep, settings: SettingsDep):
    rows = await session.scalars(
        select(RetentionPolicy).order_by(
            RetentionPolicy.data_class, RetentionPolicy.project_id.nulls_first()
        )
    )
    return PolicyList(
        dry_run_default=settings.retention_dry_run,
        audit_drop_enabled=settings.retention_audit_drop_enabled,
        data=[policy_out(r) for r in rows],
    )


@router.put("/policies/{data_class}", response_model=PolicyOut, summary="Set a retention period")
@audited("update_retention_policy", "retention_policy")
async def put_policy(
    data_class: DataClass, body: PolicyUpdate, request: Request, actor: Writer, session: SessionDep
):
    _, low, high, behavior = RETENTION_CLASSES[data_class.value]
    if not low <= body.keep_days <= high:
        raise invalid("retention_out_of_range", f"{data_class.value} keeps {low}..{high} days.")
    if body.project_id is not None:
        from ffcore.models.identity import Project

        live = await session.scalar(
            select(Project.id).where(Project.id == body.project_id, Project.deleted_at.is_(None))
        )
        if live is None:
            raise not_found("project")
    query = select(RetentionPolicy).where(RetentionPolicy.data_class == data_class.value)
    query = query.where(
        RetentionPolicy.project_id == body.project_id
        if body.project_id
        else RetentionPolicy.project_id.is_(None)
    )
    row = await session.scalar(query)
    if row is None:
        row = RetentionPolicy(
            data_class=data_class.value,
            project_id=body.project_id,
            min_days=low,
            max_days=high,
            expiry_behavior=behavior,
            keep_days=body.keep_days,
        )
        session.add(row)
    row.keep_days, row.updated_by = body.keep_days, actor.actor_id
    await session.flush()
    await session.refresh(row)
    return policy_out(row)


@router.delete(
    "/policies/{data_class}/overrides/{project_id}",
    status_code=204,
    summary="Remove a project override",
)
@audited("delete_retention_override", "retention_policy")
async def delete_override(
    data_class: DataClass, project_id: UUID, request: Request, actor: Writer, session: SessionDep
) -> None:
    result = await session.execute(
        delete(RetentionPolicy).where(
            RetentionPolicy.data_class == data_class.value,
            RetentionPolicy.project_id == project_id,
        )
    )
    if not result.rowcount:
        raise not_found("retention_override")


async def _execute(settings, actor, dry_run: bool) -> RunResults:
    try:
        results = await retention_job.execute(
            settings,
            dry_run=dry_run,
            trigger="dry_run" if dry_run else "manual",
            actor_id=actor.actor_id,
        )
    except retention_job.RetentionBusy:
        raise conflict("retention_running", "A retention pass is running.") from None
    return RunResults(
        dry_run=dry_run,
        data=[
            RunResult(
                data_class=r.data_class,
                project_id=r.project_id,
                cutoff=r.cutoff,
                counts=r.counts,
                status=r.status,
                error_code=r.error_code,
            )
            for r in results
        ],
    )


@router.post("/dry-run", response_model=RunResults, summary="Count what a run would remove")
@audited("retention_dry_run", "retention")
async def dry_run(request: Request, actor: Writer, session: SessionDep, settings: SettingsDep):
    return await _execute(settings, actor, True)


@router.post("/run", response_model=RunResults, summary="Remove expired data now")
@audited("retention_run", "retention")
async def run(request: Request, actor: Writer, session: SessionDep, settings: SettingsDep):
    return await _execute(settings, actor, False)


@router.get("/runs", response_model=RunRecords, summary="The removal record, newest first")
async def list_runs(actor: Reader, session: SessionDep, limit: int = 200):
    rows = await session.scalars(
        select(RetentionRun).order_by(RetentionRun.ts.desc()).limit(min(max(limit, 1), 1000))
    )
    return RunRecords(
        data=[
            RunRecord(
                id=r.id,
                ts=r.ts,
                trigger=r.trigger,
                dry_run=r.dry_run,
                actor_id=r.actor_id,
                data_class=r.data_class,
                project_id=r.project_id,
                cutoff=r.cutoff,
                counts=r.counts,
                status=r.status,
                error_code=r.error_code,
            )
            for r in rows
        ]
    )
