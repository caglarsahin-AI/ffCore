"""Data sources (16): register, test, sync, follow runs and items, map permissions.

Developers and above register and sync sources (the console's Data sources screen, minimum role
developer); permission mappings and a forced delete are the project admin's (they decide who
reads the documents, as a document ACL change is, 04b-1 r1). Credentials are stored encrypted
and returned as `***`; a field sent back as `***` keeps its stored value. A kind no driver
serves, or an internet deployment while OFFLINE=true, is 422 `source_kind_unavailable` (the
profile difference is the OFFLINE value). A network folder's root must stay inside
FS_SOURCES_BASE (400 `path_outside_base`, C5).

A sync request queues one run; a second request while a run of the same source is queued or
running is 409 `sync_running` (one active run per source, D3).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.sources_schemas import (
    AclMappingList,
    AclMappingOut,
    AclMappingsPut,
    ActiveRun,
    DataSourceCreate,
    DataSourceList,
    DataSourceOut,
    DataSourceUpdate,
    SourceAttachmentOut,
    SourceConnectionTest,
    SourceItemList,
    SourceItemOut,
    SyncRequest,
    SyncRunList,
    SyncRunOut,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, authorize, require_role, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.core.secrets import decrypt_json, encrypt_json
from ffcore.knowledge import jobs, raw_staging
from ffcore.models.identity import ProjectMember
from ffcore.models.knowledge import Document, KnowledgeBase
from ffcore.models.sources import (
    AclMapping,
    DataSource,
    SourceAttachment,
    SourceItem,
    SyncRun,
)
from ffcore.sources import engine, paths, policy, registry, scheduler
from ffcore.sources.base import SourceError
from ffcore.sources.schedule import Schedule

router = APIRouter(
    prefix="/projects/{project_id}/data-sources",
    tags=["data-sources"],
    responses=ERROR_RESPONSES,
)

Reader = Annotated[Actor, Depends(require_role("developer"))]
Editor = Annotated[Actor, Depends(require_role("developer", write=True))]
Admin = Annotated[Actor, Depends(require_role("admin", write=True))]
FORCE_PRUNE = require_role("admin", write=True)
# 16-1 r1 MAJOR-1 (A): who registers each kind and changes what it reads (sources/policy.py).
REGISTRARS = {
    policy.SUPERADMIN: require_superadmin(write=True),
    policy.PROJECT_ADMIN: require_role("admin", write=True),
}
SettingsDep = Annotated[Settings, Depends(get_settings)]
SourceIdDep = Annotated[str, Depends(path_resource("source_id"))]
MASK = "***"
# Audit payloads: the configuration may name internal hosts and paths; credentials never reach
# the response, so they never reach the audit row either.
AUDIT_MASKED = ("config", "secret", "last_error")


def ingest_queue_dependency(settings: SettingsDep) -> jobs.JobQueue:
    return jobs.get_queue(settings)


def sync_queue_dependency(settings: SettingsDep):
    return scheduler.get_sync_queue(settings)


IngestQueueDep = Annotated[jobs.JobQueue, Depends(ingest_queue_dependency)]
SyncQueueDep = Annotated[object, Depends(sync_queue_dependency)]


async def _require_registrar(request: Request, actor: Actor, project_id, kind: str) -> None:
    """A network folder is the installation's (one FS_SOURCES_BASE for every project): only the
    superadmin registers it or changes its root/filters (403 fs_source_superadmin_only). The
    other kinds bring the project's own credentials: the project admin. The refusal is the
    audit row's `denied` outcome (authorize records its reason)."""
    rule = policy.registrar(kind)
    scope = None if rule == policy.SUPERADMIN else str(project_id)
    try:
        await authorize(request, actor, scope, REGISTRARS[rule])
    except ApiError as exc:
        if rule != policy.SUPERADMIN or exc.status_code != 403:
            raise
        error = ApiError(
            403,
            "permission_error",
            "fs_source_superadmin_only",
            "A network folder is shared by the whole installation: its source and its root or "
            "filters are set by a superadmin.",
        )
        if getattr(exc, "audit_detail", None) is not None:
            error.audit_detail = exc.audit_detail
        raise error from None


def _source_error(exc: SourceError) -> ApiError:
    if exc.code == "path_outside_base":
        return ApiError(400, "invalid_request_error", exc.code, exc.detail)
    return invalid(exc.code, exc.detail)


def _validate(kind: str, deployment: str | None, config: dict, secret: dict | None, settings):
    """The driver for (kind, deployment), the validated configuration and credentials."""
    try:
        driver = registry.driver_for(kind, deployment, settings)
    except SourceError as exc:
        raise _source_error(exc) from None
    if kind == "fs":
        try:
            root = paths.check_root(str(config.get("root", "")))
        except SourceError as exc:
            raise _source_error(exc) from None
        if raw_staging.personnel_data(f"fs:{root}", f"{root}/x"):
            raise invalid(
                "prsim_requires_ner",
                "This folder holds personnel data; it is indexed once names are masked (08).",
            )
    try:
        normalized = driver.config_model.model_validate(config).model_dump(mode="json")
    except ValidationError as exc:
        raise invalid("config_invalid", _first_error(exc)) from None
    if driver.secret_model is None:
        if secret:
            raise invalid("secret_unexpected", f"{kind} sources take no credentials.")
        clean_secret = None
    else:
        if not secret:
            raise invalid("secret_required", f"{kind} sources need credentials.")
        try:
            clean_secret = driver.secret_model.model_validate(secret).model_dump(mode="json")
        except ValidationError as exc:
            raise invalid("secret_invalid", _first_error(exc, values=False)) from None
    if kind == "fs":
        try:
            paths.resolve_root(settings.fs_sources_base, normalized["root"])
        except SourceError as exc:
            raise _source_error(exc) from None
    return driver, normalized, clean_secret


def _first_error(exc: ValidationError, *, values: bool = True) -> str:
    error = exc.errors()[0]
    where = ".".join(str(p) for p in error.get("loc", ())) or "body"
    message = error.get("msg", "invalid")
    return f"{where}: {message}" if values else f"{where}: invalid value"


async def _source(session, project_id: UUID, source_id: UUID) -> DataSource:
    source = await session.scalar(
        select(DataSource).where(
            DataSource.id == source_id,
            DataSource.project_id == project_id,
            DataSource.deleted_at.is_(None),
        )
    )
    if source is None:
        raise not_found("data_source")
    return source


def _masked(source: DataSource, settings: Settings) -> dict[str, str] | None:
    if source.secret_encrypted is None:
        return None
    return dict.fromkeys(sorted(decrypt_json(source.secret_encrypted, settings)), MASK)


async def _out(session, source: DataSource, settings: Settings) -> DataSourceOut:
    await session.flush()
    await session.refresh(source)
    active = await session.scalar(
        select(SyncRun).where(
            SyncRun.data_source_id == source.id, SyncRun.status.in_(("queued", "running"))
        )
    )
    items = await session.scalar(
        select(func.count())
        .select_from(SourceItem)
        .where(SourceItem.data_source_id == source.id, SourceItem.state == "active")
    )
    return DataSourceOut(
        id=source.id,
        project_id=source.project_id,
        kb_id=source.kb_id,
        key=source.key,
        name=source.name,
        kind=source.kind,
        deployment=source.deployment,
        config=source.config,
        secret=_masked(source, settings),
        schedule=Schedule.model_validate(source.schedule),
        sync_mode=source.sync_mode,
        prune_max_ratio=source.prune_max_ratio,
        effective_prune_max_ratio=source.prune_max_ratio or settings.prune_max_ratio,
        status=source.status,
        last_sync_at=source.last_sync_at,
        last_error=source.last_error,
        active_run=ActiveRun(
            id=active.id, layer=active.layer, mode=active.mode, status=active.status
        )
        if active
        else None,
        items=items or 0,
        created_by=source.created_by,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


async def _before(project_id: UUID, source_id: UUID, session, settings, **_):
    return await _out(session, await _source(session, project_id, source_id), settings)


@router.get("", response_model=DataSourceList, summary="List data sources")
async def list_sources(project_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep):
    rows = (
        await session.scalars(
            select(DataSource)
            .where(DataSource.project_id == project_id, DataSource.deleted_at.is_(None))
            .order_by(DataSource.key)
        )
    ).all()
    return DataSourceList(data=[await _out(session, r, settings) for r in rows])


@router.post("", response_model=DataSourceOut, status_code=201, summary="Register a data source")
@audited("create_data_source", "data_source", redact_fields=AUDIT_MASKED)
async def create_source(
    project_id: UUID,
    body: DataSourceCreate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
):
    """The knowledge base must be in the project. The key is unique among the project's live
    sources (409 data_source_key_taken). Who may register which kind: sources/policy.py."""
    await _require_registrar(request, actor, project_id, body.kind.value)
    kb = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == body.kb_id,
            KnowledgeBase.project_id == project_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    if kb is None:
        raise not_found("knowledge_base")
    deployment = body.deployment.value if body.deployment else None
    _, config, secret = _validate(body.kind.value, deployment, body.config, body.secret, settings)
    taken = await session.scalar(
        select(DataSource.id).where(
            DataSource.project_id == project_id,
            DataSource.key == body.key,
            DataSource.deleted_at.is_(None),
        )
    )
    if taken is not None:
        raise conflict("data_source_key_taken", "This data source key is already used.")
    source = DataSource(
        project_id=project_id,
        kb_id=kb.id,
        key=body.key,
        name=body.name,
        kind=body.kind.value,
        deployment=deployment,
        config=config,
        secret_encrypted=encrypt_json(secret, settings) if secret else None,
        schedule=body.schedule.model_dump(exclude_none=True),
        sync_mode=body.sync_mode.value,
        prune_max_ratio=body.prune_max_ratio,
        status="active",
        created_by=actor.actor_id,
    )
    session.add(source)
    return await _out(session, source, settings)


@router.get("/{source_id}", response_model=DataSourceOut, summary="Get a data source")
async def get_source(
    project_id: UUID, source_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep
):
    return await _out(session, await _source(session, project_id, source_id), settings)


@router.patch("/{source_id}", response_model=DataSourceOut, summary="Update a data source")
@audited("update_data_source", "data_source", redact_fields=AUDIT_MASKED, load_before=_before)
async def update_source(
    project_id: UUID,
    source_id: UUID,
    body: DataSourceUpdate,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
):
    """Kind, deployment and knowledge base are fixed (register a new source to change them).
    Changing what the source reads (config, credentials) needs its kind's registrar."""
    source = await _source(session, project_id, source_id)
    if policy.config_change_needs_registrar(body.model_dump()):
        await _require_registrar(request, actor, project_id, source.kind)
    if body.config is not None or body.secret is not None:
        stored = decrypt_json(source.secret_encrypted, settings) if source.secret_encrypted else {}
        secret = stored
        if body.secret is not None:
            secret = {k: (stored.get(k) if v == MASK else v) for k, v in body.secret.items()}
        config = body.config if body.config is not None else dict(source.config)
        _, config, secret = _validate(
            source.kind, source.deployment, config, secret or None, settings
        )
        source.config = config
        source.secret_encrypted = encrypt_json(secret, settings) if secret else None
    if body.name is not None:
        source.name = body.name
    if body.schedule is not None:
        source.schedule = body.schedule.model_dump(exclude_none=True)
    if body.sync_mode is not None:
        source.sync_mode = body.sync_mode.value
    if body.clear_prune_max_ratio:
        source.prune_max_ratio = None
    elif body.prune_max_ratio is not None:
        source.prune_max_ratio = body.prune_max_ratio
    if body.status is not None:
        source.status = body.status.value
    return await _out(session, source, settings)


@router.delete(
    "/{source_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a data source"
)
@audited("delete_data_source", "data_source", redact_fields=AUDIT_MASKED, load_before=_before)
async def delete_source(
    project_id: UUID,
    source_id: UUID,
    request: Request,
    actor: Admin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: SourceIdDep,
) -> None:
    """Only a source without indexed items is deleted (409 data_source_has_items): its documents
    leave the index through a full run (narrow the filter, or empty the folder) so the safe
    delete rule applies; deleting the source never removes documents silently."""
    source = await _source(session, project_id, source_id)
    active = await session.scalar(
        select(func.count())
        .select_from(SourceItem)
        .where(
            SourceItem.data_source_id == source.id,
            SourceItem.state == "active",
            SourceItem.document_id.is_not(None),
        )
    )
    if active:
        raise conflict(
            "data_source_has_items",
            f"{active} documents still come from this source; remove them with a full run first.",
        )
    running = await session.scalar(
        select(SyncRun.id).where(
            SyncRun.data_source_id == source.id, SyncRun.status.in_(("queued", "running"))
        )
    )
    if running is not None:
        raise conflict("sync_running", "A run of this source is queued or running.")
    source.deleted_at = func.now()
    source.status = "paused"


@router.post("/{source_id}/test", response_model=SourceConnectionTest, summary="Test a data source")
async def test_source(
    project_id: UUID, source_id: UUID, actor: Editor, session: SessionDep, settings: SettingsDep
):
    """Reaches the source with the stored configuration and returns its item count; a failure
    is `reachable: false` with the error code (never the credentials)."""
    source = await _source(session, project_id, source_id)
    try:
        driver = engine.make_driver(source, settings)
    except SourceError as exc:
        return SourceConnectionTest(reachable=False, error_code=exc.code, detail=exc.detail)
    try:
        result = await driver.test_connection()
    finally:
        await driver.aclose()
    return SourceConnectionTest(
        reachable=result.reachable,
        count=result.count,
        error_code=result.error_code,
        detail=result.detail,
    )


@router.post(
    "/{source_id}/sync",
    response_model=SyncRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a sync run",
)
@audited("sync_data_source", "data_source")
async def sync_source(
    project_id: UUID,
    source_id: UUID,
    body: SyncRequest,
    request: Request,
    actor: Editor,
    session: SessionDep,
    sync_queue: SyncQueueDep,
    ingest_queue: IngestQueueDep,
    resource_id: SourceIdDep,
):
    source = await _source(session, project_id, source_id)
    if source.status != "active":
        raise conflict("data_source_paused", "This source is paused; set status=active first.")
    mode = body.mode.value if body.mode else source.sync_mode
    if body.force_prune:
        if body.layer.value != "raw" or mode != "full":
            raise invalid("force_prune_requires_full", "force_prune applies to a full raw run.")
        await authorize(request, actor, str(project_id), FORCE_PRUNE)
    try:
        run = await engine.create_run(
            session,
            source,
            layer=body.layer.value,
            mode=mode,
            trigger="manual",
            requested_by=actor.actor_id,
            force_prune=body.force_prune,
        )
    except SourceError as exc:
        raise conflict(exc.code, exc.detail) from None
    await session.commit()
    try:
        await engine.enqueue_run(run, sync_queue=sync_queue, ingest_queue=ingest_queue)
    except Exception:
        await engine.fail_queued(run.id, "enqueue_failed")
        raise ApiError(
            503, "api_error", "queue_unavailable", "The sync queue is unavailable; try again."
        ) from None
    await session.refresh(run)
    return _run_out(run)


def _run_out(run: SyncRun) -> SyncRunOut:
    return SyncRunOut.model_validate(run, from_attributes=True)


@router.get("/{source_id}/runs", response_model=SyncRunList, summary="List sync runs")
async def list_runs(
    project_id: UUID,
    source_id: UUID,
    actor: Reader,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    source = await _source(session, project_id, source_id)
    rows = (
        await session.scalars(
            select(SyncRun)
            .where(SyncRun.data_source_id == source.id)
            .order_by(SyncRun.created_at.desc())
            .limit(limit)
        )
    ).all()
    return SyncRunList(data=[_run_out(r) for r in rows])


async def _run(session, source: DataSource, run_id: UUID) -> SyncRun:
    run = await session.scalar(
        select(SyncRun).where(SyncRun.id == run_id, SyncRun.data_source_id == source.id)
    )
    if run is None:
        raise not_found("sync_run")
    return run


@router.get("/{source_id}/runs/{run_id}", response_model=SyncRunOut, summary="Get a sync run")
async def get_run(
    project_id: UUID, source_id: UUID, run_id: UUID, actor: Reader, session: SessionDep
):
    return _run_out(await _run(session, await _source(session, project_id, source_id), run_id))


@router.post(
    "/{source_id}/runs/{run_id}/cancel", response_model=SyncRunOut, summary="Cancel a sync run"
)
@audited("cancel_sync_run", "sync_run")
async def cancel_run(
    project_id: UUID,
    source_id: UUID,
    run_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    """A queued run is cancelled at once; a running raw run stops between two items (no delete,
    no cursor move). Silver and gold runs finish their current document."""
    run = await _run(session, await _source(session, project_id, source_id), run_id)
    if run.status == "queued":
        run.status, run.ended_at = "cancelled", func.now()
    elif run.status == "running":
        run.cancel_requested = True
    else:
        raise conflict("sync_run_finished", f"This run is already {run.status}.")
    await session.flush()
    await session.refresh(run)
    return _run_out(run)


@router.get("/{source_id}/items", response_model=SourceItemList, summary="List source items")
async def list_items(
    project_id: UUID,
    source_id: UUID,
    actor: Reader,
    session: SessionDep,
    state: Annotated[str | None, Query(pattern="^(active|deleted)$")] = None,
    errors: Annotated[bool, Query(description="Only items whose last run failed them.")] = False,
    skipped: Annotated[bool, Query(description="Only items Kapı 0 skipped.")] = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    source = await _source(session, project_id, source_id)
    conditions = [SourceItem.data_source_id == source.id]
    if state is not None:
        conditions.append(SourceItem.state == state)
    if errors:
        conditions.append(SourceItem.last_error.is_not(None))
    if skipped:
        conditions.append(SourceItem.gate0_status == "skipped")
    total = await session.scalar(select(func.count()).select_from(SourceItem).where(*conditions))
    rows = (
        await session.execute(
            select(SourceItem, Document.status)
            .outerjoin(Document, Document.id == SourceItem.document_id)
            .where(*conditions)
            .order_by(SourceItem.external_id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    ids = [item.id for item, _ in rows]
    ledgers: dict = {}
    if ids:
        for ledger in (
            await session.scalars(
                select(SourceAttachment)
                .where(SourceAttachment.source_item_id.in_(ids))
                .order_by(SourceAttachment.name)
            )
        ).all():
            ledgers.setdefault(ledger.source_item_id, []).append(
                SourceAttachmentOut(
                    name=ledger.name,
                    size=ledger.size,
                    gate0_status=ledger.gate0_status,
                    gate0_reason=ledger.gate0_reason,
                    shared=ledger.shared_from is not None,
                )
            )
    data = [
        SourceItemOut(
            id=item.id,
            external_id=item.external_id,
            external_url=item.external_url,
            title=item.title,
            external_updated_at=item.external_updated_at,
            state=item.state,
            gate0_status=item.gate0_status,
            gate0_reason=item.gate0_reason,
            last_error=item.last_error,
            document_id=item.document_id,
            document_status=document_status,
            default_admin=bool((item.acl_source or {}).get("default_admin")),
            updated_at=item.updated_at,
            attachments=ledgers.get(item.id, []),
        )
        for item, document_status in rows
    ]
    return SourceItemList(data=data, total=total or 0)


def _mapping_out(row: AclMapping) -> AclMappingOut:
    return AclMappingOut.model_validate(row, from_attributes=True)


@router.get("/{source_id}/acl-mappings", response_model=AclMappingList, summary="List ACL mappings")
async def list_mappings(project_id: UUID, source_id: UUID, actor: Reader, session: SessionDep):
    source = await _source(session, project_id, source_id)
    rows = (
        await session.scalars(
            select(AclMapping)
            .where(AclMapping.data_source_id == source.id)
            .order_by(AclMapping.external_group, AclMapping.role, AclMapping.user_id)
        )
    ).all()
    return AclMappingList(data=[_mapping_out(r) for r in rows])


@router.put(
    "/{source_id}/acl-mappings", response_model=AclMappingList, summary="Replace ACL mappings"
)
@audited("update_acl_mappings", "data_source")
async def put_mappings(
    project_id: UUID,
    source_id: UUID,
    body: AclMappingsPut,
    request: Request,
    actor: Admin,
    session: SessionDep,
    resource_id: SourceIdDep,
):
    """Replaces the whole list. Each row maps one group to one role or one project member;
    an unmapped group stays admin-only. Takes effect on the next raw run (C15)."""
    source = await _source(session, project_id, source_id)
    seen = set()
    for row in body.mappings:
        if (row.role is None) == (row.user_id is None):
            raise invalid("acl_mapping_target", "Each mapping names exactly one role or user.")
        key = (row.external_group, row.role, row.user_id)
        if key in seen:
            raise invalid("acl_mapping_duplicate", f"{row.external_group} is mapped twice.")
        seen.add(key)
    users = {r.user_id for r in body.mappings if r.user_id is not None}
    if users:
        members = set(
            (
                await session.scalars(
                    select(ProjectMember.user_id).where(
                        ProjectMember.project_id == project_id, ProjectMember.user_id.in_(users)
                    )
                )
            ).all()
        )
        if users - members:
            raise invalid("acl_mapping_user_not_member", "A mapped user is not a project member.")
    await session.execute(
        AclMapping.__table__.delete().where(AclMapping.data_source_id == source.id)
    )
    for row in body.mappings:
        session.add(
            AclMapping(
                data_source_id=source.id,
                external_group=row.external_group,
                role=row.role,
                user_id=row.user_id,
                created_by=actor.actor_id,
            )
        )
    await session.flush()
    rows = (
        await session.scalars(
            select(AclMapping)
            .where(AclMapping.data_source_id == source.id)
            .order_by(AclMapping.external_group, AclMapping.role, AclMapping.user_id)
        )
    ).all()
    return AclMappingList(data=[_mapping_out(r) for r in rows])
