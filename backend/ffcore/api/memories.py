"""14: user memory API (brief 14 "Kullanıcı kontrolü", "Yönetici kontrolü"; K-14-0003).

A member reads and changes **only their own** items. Nobody else reads an item's text: an
administrator (superadmin included) gets 403 `memory_not_owner` on someone else's item and sees
counts and kinds only (`GET /memories/stats`, no text field). Every mutation is audited without
its content (`@audited(audit_payload=False)`, R10.1): the audit trail says what happened, never
what was remembered.

Own-data mutations (remember, edit, delete, delete all, opt out and back in) stay open in
read-only access mode like deleting one's own conversation (11): memory is the user's own data
and must stay under their control. Settings are an administrator's (`admin`, edit access).

"Remember this" (`POST /memories`) skips the extraction model (`kind=preference`,
`confidence=1`) but never the PII check (C19): a finding answers 400 `memory_pii_blocked`, the
guardrail event is committed before the refusal and the audit row records the error. A text
with the memory block's markers is 400 `memory_text_invalid` (r2 MAJOR-2); without the NER
model every write is 422 `memory_requires_ner` (r2 MINOR-1).

The internal routes (`/internal/memories/...`, service account only) are the worker's: the API
process holds the embedding model and NER (06a), so recall and extraction writes happen here.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.agents_schemas import RUN_INPUT_MAX
from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.internal import ServiceActor
from ffcore.core import db
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.memory import recall as memory_recall
from ffcore.memory import settings as memory_settings
from ffcore.memory import store
from ffcore.memory.pii import check_memory_text
from ffcore.models.agents import Agent
from ffcore.models.audit import AuditEvent
from ffcore.models.catalog import Model
from ffcore.models.memory import (
    DEFAULT_EXTRACTION_MODEL,
    DEFAULT_MAX_ITEMS,
    DEFAULT_TOP_K,
    KINDS,
    Memory,
    MemoryOptOut,
    MemorySetting,
)
from ffcore.models.runs import Run
from ffcore.runtime.contracts import RunStatus

router = APIRouter(prefix="/projects/{project_id}", tags=["memories"], responses=ERROR_RESPONSES)
internal_router = APIRouter(
    prefix="/internal/memories", tags=["memories-internal"], responses=ERROR_RESPONSES
)

Member = Annotated[Actor, Depends(require_role("user"))]
AdminReader = Annotated[Actor, Depends(require_role("admin"))]
AdminWriter = Annotated[Actor, Depends(require_role("admin", write=True))]
MemoryIdDep = Annotated[str, Depends(path_resource("memory_id"))]
SettingsDep = Annotated[Settings, Depends(get_settings)]

Kind = Literal["profile", "preference", "fact", "decision"]
TEXT_MAX = 500
RELATED_ITEMS = 5
# What a delete is counted from in the statistics (S6: rows are really deleted).
DELETE_ACTIONS = ("memory.delete", "memory.delete_all")


# --- schemas -----------------------------------------------------------------------------------


class MemoryOut(BaseModel):
    id: UUID
    kind: Kind
    text: str
    agent_id: UUID | None
    status: Literal["active", "archived"]
    confidence: float
    source_run_id: UUID | None
    supersedes_id: UUID | None
    created_at: datetime
    updated_at: datetime
    last_used_at: datetime | None
    use_count: int


class MemoryList(BaseModel):
    items: list[MemoryOut]


class RememberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=TEXT_MAX)


class MemoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=TEXT_MAX)


class OptOutOut(BaseModel):
    opted_out: bool


class UserStats(BaseModel):
    """One member's counts: no text, no item ids (brief 14: administrators see numbers)."""

    user_id: UUID
    active: int
    archived: int
    by_kind: dict[str, int]
    used: int
    delete_events: int


class MemoryStats(BaseModel):
    users: list[UserStats]
    active: int
    archived: int
    by_kind: dict[str, int]
    # Share of active items used at least once; None without active items.
    use_rate: float | None
    delete_events: int
    opted_out_users: int


class MemorySettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    allowed_kinds: list[Kind] = Field(default_factory=lambda: list(KINDS), min_length=1)
    max_items_per_user: int = Field(default=DEFAULT_MAX_ITEMS, gt=0, le=10_000)
    recall_top_k: int = Field(default=DEFAULT_TOP_K, ge=0, le=50)
    ttl_days: int | None = Field(default=None, gt=0, le=1095)
    extraction_model: str = Field(default=DEFAULT_EXTRACTION_MODEL, min_length=1, max_length=200)


class MemorySettingsOut(MemorySettingsIn):
    agent_id: UUID | None
    # Where the values come from: "agent", "project" or "default" (no row yet).
    source: Literal["agent", "project", "default"]
    # S3: memory can be turned on only where the installation has its NER model.
    ner_ready: bool


class RecallRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    user_id: UUID
    run_id: UUID
    # The recall query (memory.recall.recall_query bounds a longer facade question).
    question: str = Field(max_length=RUN_INPUT_MAX)
    # The budget's memory share in tokens: only the items that fit are marked used (NOTE-2).
    share: int = Field(ge=0)


class RecalledItem(BaseModel):
    id: UUID
    kind: Kind
    text: str


class RecallResponse(BaseModel):
    # None: memory works for this run; otherwise why nothing was recalled.
    off_reason: Literal["off", "opt_out", "no_user"] | None
    items: list[RecalledItem]
    # `related` only: the model the extraction job calls (the effective settings').
    extraction_model: str | None = None
    # `recall` only: the ids that did not fit the share (not marked used).
    dropped: list[UUID] = Field(default_factory=list)


class RelatedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    user_id: UUID
    run_id: UUID
    text: str = Field(max_length=40_000)


class CandidateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Kind
    text: str = Field(min_length=1, max_length=TEXT_MAX)
    confidence: float = Field(ge=0, le=1)
    supersedes_id: str | None = None


class CandidatesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    user_id: UUID
    run_id: UUID
    items: list[CandidateIn] = Field(max_length=3)


class CandidatesResponse(BaseModel):
    written: list[UUID]
    archived: list[UUID]
    rejected: dict[str, int]


# --- helpers -----------------------------------------------------------------------------------


def _user_id(actor: Actor) -> UUID:
    if actor.actor_type != "user":
        raise invalid("memory_user_missing", "Memory belongs to a signed-in user.")
    return UUID(actor.actor_id)


def _out(m: Memory) -> MemoryOut:
    return MemoryOut(
        id=m.id,
        kind=m.kind,
        text=m.text,
        agent_id=m.agent_id,
        status=m.status,
        confidence=m.confidence,
        source_run_id=m.source_run_id,
        supersedes_id=m.supersedes_id,
        created_at=m.created_at,
        updated_at=m.updated_at,
        last_used_at=m.last_used_at,
        use_count=m.use_count,
    )


def _not_owner() -> ApiError:
    return ApiError(
        403, "permission_error", "memory_not_owner", "Only its owner can read or change a memory."
    )


async def _own(session: AsyncSession, project_id: UUID, memory_id: UUID, actor: Actor) -> Memory:
    item = await session.scalar(
        select(Memory).where(Memory.id == memory_id, Memory.project_id == project_id)
    )
    if item is None:
        raise not_found("memory")
    if actor.actor_type != "user" or item.user_id != UUID(actor.actor_id):
        raise _not_owner()
    return item


def _pii_blocked(reference_id: str | None) -> ApiError:
    error = ApiError(
        400,
        "invalid_request_error",
        "memory_pii_blocked",
        "Personal data cannot be stored in memory."
        + (f" Reference: {reference_id}." if reference_id else ""),
    )
    return error


async def _writable(session, project_id, user_id, agent_id=None):
    effective = await memory_settings.effective(session, project_id, agent_id)
    if not effective.enabled:
        raise conflict("memory_disabled", "Memory is turned off for this project.")
    if await memory_settings.opted_out(session, project_id, user_id):
        raise conflict("memory_opted_out", "You turned memory off.")
    return effective


def _text_invalid() -> ApiError:
    return ApiError(
        400,
        "invalid_request_error",
        "memory_text_invalid",
        "A memory cannot contain the memory block's markers ([USER MEMORY], [/USER MEMORY]).",
    )


def _ner_ready(settings: Settings) -> bool:
    return bool(settings.ner_model and settings.ner_revision)


# --- the member's own items ---------------------------------------------------------------------


@router.get("/memories", response_model=MemoryList)
async def list_memories(
    project_id: UUID,
    actor: Member,
    session: SessionDep,
    ids: Annotated[list[UUID] | None, Query()] = None,
    source_run_id: UUID | None = None,
    status_filter: Annotated[Literal["active", "archived"] | None, Query(alias="status")] = None,
):
    """The caller's own items, newest first. `ids` answers the chat's "taken into account" note
    (run events carry ids only); `source_run_id` its "noted" notice."""
    query = select(Memory).where(Memory.project_id == project_id, Memory.user_id == _user_id(actor))
    if ids:
        query = query.where(Memory.id.in_(ids))
    if source_run_id is not None:
        query = query.where(Memory.source_run_id == source_run_id)
    if status_filter is not None:
        query = query.where(Memory.status == status_filter)
    rows = await session.scalars(query.order_by(Memory.created_at.desc(), Memory.id))
    return MemoryList(items=[_out(m) for m in rows.all()])


@router.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
@audited("memory.create", "memory", audit_payload=False)
async def remember(
    project_id: UUID,
    body: RememberRequest,
    request: Request,
    actor: Member,
    session: SessionDep,
    settings: SettingsDep,
):
    """ "Remember this": no extraction model, `kind=preference`, `confidence=1`; PII checked."""
    user_id = _user_id(actor)
    effective = await _writable(session, project_id, user_id)
    result = await store.write(
        session,
        settings,
        effective,
        project_id=project_id,
        user_id=user_id,
        agent_id=None,
        candidates=[store.Candidate("preference", body.text.strip(), 1.0)],
        min_confidence=0.0,
    )
    if result.rejected["invalid"]:
        raise _text_invalid()
    if result.rejected["pii"]:
        await session.commit()  # the guardrail event stays; the audit row records the error
        raise _pii_blocked(result.pii_reference_id)
    if result.rejected["kind"]:
        raise conflict("memory_kind_not_allowed", "Preferences are not allowed in this project.")
    item = await session.get(Memory, result.written[0])
    await session.flush()
    await session.refresh(item)
    return _out(item)


@router.patch("/memories/{memory_id}", response_model=MemoryOut)
@audited("memory.update", "memory", audit_payload=False)
async def update_memory(
    project_id: UUID,
    memory_id: UUID,
    body: MemoryUpdate,
    request: Request,
    actor: Member,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: MemoryIdDep,
):
    """The owner's correction: the new text is PII-checked and embedded again."""
    item = await _own(session, project_id, memory_id, actor)
    text = body.text.strip()
    if memory_recall.has_marker(text):
        raise _text_invalid()
    checked = await check_memory_text(session, project_id, text)
    if checked.blocked:
        await session.commit()
        raise _pii_blocked(checked.reference_id)
    from ffcore.knowledge.embed import embed

    item.text = text
    item.embedding = (await embed(settings, [text])).dense[0]
    item.updated_at = func.now()
    await session.flush()
    await session.refresh(item)
    return _out(item)


@router.delete("/memories", status_code=status.HTTP_204_NO_CONTENT)
@audited("memory.delete_all", "memory", audit_payload=False)
async def delete_all_memories(
    project_id: UUID, request: Request, actor: Member, session: SessionDep
) -> None:
    """Every item of the caller in this project, active and archived."""
    await session.execute(
        delete(Memory).where(Memory.project_id == project_id, Memory.user_id == _user_id(actor))
    )


@router.get("/memories/opt-out", response_model=OptOutOut)
async def get_opt_out(project_id: UUID, actor: Member, session: SessionDep):
    return OptOutOut(
        opted_out=await memory_settings.opted_out(session, project_id, _user_id(actor))
    )


@router.put("/memories/opt-out", response_model=OptOutOut)
@audited("memory.opt_out", "memory", audit_payload=False)
async def opt_out(project_id: UUID, request: Request, actor: Member, session: SessionDep):
    """Memory off for the caller: nothing is written or recalled until they turn it on again.
    Existing items stay (the caller may delete them)."""
    user_id = _user_id(actor)
    if not await memory_settings.opted_out(session, project_id, user_id):
        session.add(MemoryOptOut(project_id=project_id, user_id=user_id))
    return OptOutOut(opted_out=True)


@router.delete("/memories/opt-out", response_model=OptOutOut)
@audited("memory.opt_in", "memory", audit_payload=False)
async def opt_in(project_id: UUID, request: Request, actor: Member, session: SessionDep):
    await session.execute(
        delete(MemoryOptOut).where(
            MemoryOptOut.project_id == project_id, MemoryOptOut.user_id == _user_id(actor)
        )
    )
    return OptOutOut(opted_out=False)


# After the fixed paths (`/memories/opt-out`): a path parameter would take them first.
@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("memory.delete", "memory", audit_payload=False)
async def delete_memory(
    project_id: UUID,
    memory_id: UUID,
    request: Request,
    actor: Member,
    session: SessionDep,
    resource_id: MemoryIdDep,
) -> None:
    """Immediate and permanent (brief 14; S6): the row is deleted, not marked."""
    item = await _own(session, project_id, memory_id, actor)
    await session.delete(item)


# --- administrators: numbers and settings --------------------------------------------------------


@router.get("/memories/stats", response_model=MemoryStats)
async def memory_stats(project_id: UUID, actor: AdminReader, session: SessionDep):
    """Counts per member and kind, use and delete numbers; never a text (brief 14)."""
    rows = (
        await session.execute(
            select(
                Memory.user_id,
                Memory.status,
                Memory.kind,
                func.count(),
                func.count().filter(Memory.use_count > 0),
            )
            .where(Memory.project_id == project_id)
            .group_by(Memory.user_id, Memory.status, Memory.kind)
        )
    ).all()
    deletes = dict(
        (
            await session.execute(
                select(AuditEvent.actor_id, func.count())
                .where(
                    AuditEvent.project_id == project_id,
                    AuditEvent.action.in_(DELETE_ACTIONS),
                    AuditEvent.outcome == "success",
                )
                .group_by(AuditEvent.actor_id)
            )
        ).all()
    )
    users: dict[UUID, UserStats] = {}

    def entry_of(user_id: UUID) -> UserStats:
        return users.setdefault(
            user_id,
            UserStats(
                user_id=user_id,
                active=0,
                archived=0,
                by_kind={},
                used=0,
                delete_events=int(deletes.get(str(user_id), 0)),
            ),
        )

    # A member whose items were all deleted is listed with the delete count (NOTE-5); the
    # delete routes are user-only (`_user_id`), so every actor id is a user id.
    for actor_id in deletes:
        entry_of(UUID(str(actor_id)))
    for user_id, state, kind, count, used in rows:
        entry = entry_of(user_id)
        if state == "active":
            entry.active += count
            entry.used += used
            entry.by_kind[kind] = entry.by_kind.get(kind, 0) + count
        else:
            entry.archived += count
    active = sum(u.active for u in users.values())
    by_kind: dict[str, int] = {}
    for u in users.values():
        for kind, count in u.by_kind.items():
            by_kind[kind] = by_kind.get(kind, 0) + count
    opted = await session.scalar(select(func.count()).where(MemoryOptOut.project_id == project_id))
    return MemoryStats(
        users=sorted(users.values(), key=lambda u: str(u.user_id)),
        active=active,
        archived=sum(u.archived for u in users.values()),
        by_kind=by_kind,
        use_rate=(sum(u.used for u in users.values()) / active) if active else None,
        delete_events=int(sum(deletes.values())),
        opted_out_users=int(opted or 0),
    )


async def _agent(session, project_id: UUID, agent_id: UUID | None) -> None:
    if agent_id is None:
        return
    found = await session.scalar(
        select(Agent.id).where(
            Agent.id == agent_id, Agent.project_id == project_id, Agent.deleted_at.is_(None)
        )
    )
    if found is None:
        raise not_found("agent")


def _settings_out(effective, agent_id, settings: Settings) -> MemorySettingsOut:
    return MemorySettingsOut(
        enabled=effective.enabled,
        allowed_kinds=list(effective.allowed_kinds),
        max_items_per_user=effective.max_items_per_user,
        recall_top_k=effective.recall_top_k,
        ttl_days=effective.ttl_days,
        extraction_model=effective.extraction_model,
        agent_id=agent_id,
        source=effective.source,
        ner_ready=_ner_ready(settings),
    )


@router.get("/memories/settings", response_model=MemorySettingsOut)
async def get_memory_settings(
    project_id: UUID,
    actor: AdminReader,
    session: SessionDep,
    settings: SettingsDep,
    agent_id: UUID | None = None,
):
    """The effective settings of the project (no `agent_id`) or of one agent."""
    await _agent(session, project_id, agent_id)
    effective = await memory_settings.effective(session, project_id, agent_id)
    return _settings_out(effective, agent_id, settings)


async def _catalog_model(session, project_id: UUID, key: str) -> None:
    """The extraction model must be an active chat model of the project (NOTE-2): an unknown
    key is refused here, not at the first extraction."""
    found = await session.scalar(
        select(Model.id).where(
            Model.project_id == project_id,
            Model.key == key,
            Model.category == "llm",
            Model.is_active.is_(True),
            Model.deleted_at.is_(None),
        )
    )
    if found is None:
        raise ApiError(
            400,
            "invalid_request_error",
            "model_not_found",
            f"No active chat model {key} in this project.",
        )


@router.put("/memories/settings", response_model=MemorySettingsOut)
@audited("memory.settings_update", "memory_settings", audit_payload=False)
async def put_memory_settings(
    project_id: UUID,
    body: MemorySettingsIn,
    request: Request,
    actor: AdminWriter,
    session: SessionDep,
    settings: SettingsDep,
    agent_id: UUID | None = None,
):
    """The project's row (no `agent_id`) or the agent's own. Turning memory on needs NER (S3)."""
    await _agent(session, project_id, agent_id)
    if body.enabled and not _ner_ready(settings):
        raise invalid(
            "memory_requires_ner",
            "Memory needs the installation's NER model (NER_MODEL, NER_REVISION) to keep "
            "person names out; set it up first (docs/hafiza.md).",
        )
    # Checked when memory is turned on or the model is changed (14-2 NOTE-2); turning memory off
    # with the model in use always works, even when the catalog no longer holds it.
    current = await memory_settings.effective(session, project_id, agent_id)
    if body.enabled or body.extraction_model != current.extraction_model:
        await _catalog_model(session, project_id, body.extraction_model)
    row = await memory_settings.setting_row(session, project_id, agent_id)
    if row is None:
        row = MemorySetting(id=uuid.uuid4(), project_id=project_id, agent_id=agent_id)
        session.add(row)
    row.enabled = body.enabled
    row.allowed_kinds = list(dict.fromkeys(body.allowed_kinds))
    row.max_items_per_user = body.max_items_per_user
    row.recall_top_k = body.recall_top_k
    row.ttl_days = body.ttl_days
    row.extraction_model = body.extraction_model
    row.updated_by = actor.actor_id
    await session.flush()
    effective = await memory_settings.effective(session, project_id, agent_id)
    return _settings_out(effective, agent_id, settings)


# --- the worker's internal routes ---------------------------------------------------------------


InternalSession = Annotated[AsyncSession, Depends(db.get_session)]


async def _run_of(session, body) -> Run:
    """The run the worker acts for: in the project, of this user (never trusted from the body
    alone)."""
    run = await session.scalar(
        select(Run).where(Run.id == body.run_id, Run.project_id == body.project_id)
    )
    if run is None or run.user_id != body.user_id:
        raise not_found("run")
    return run


@internal_router.post("/recall", response_model=RecallResponse)
async def internal_recall(
    body: RecallRequest, actor: ServiceActor, session: InternalSession, settings: SettingsDep
):
    """`prepare`'s recall: off reason or the items (profile always, then `recall_top_k`)."""
    run = await _run_of(session, body)
    reason = await memory_settings.off_reason(session, body.project_id, run.agent_id, body.user_id)
    if reason is not None:
        return RecallResponse(off_reason=reason, items=[])
    effective = await memory_settings.effective(session, body.project_id, run.agent_id)
    found = await store.recall(
        session,
        settings,
        project_id=body.project_id,
        user_id=body.user_id,
        agent_id=run.agent_id,
        question=body.question,
        top_k=effective.recall_top_k,
        kinds=effective.allowed_kinds,
    )
    items = [{"id": str(i.id), "kind": i.kind, "text": i.text} for i in found]
    kept, dropped, _ = memory_recall.fit(items, body.share)
    await store.mark_used(session, [i["id"] for i in kept])
    await session.commit()
    return RecallResponse(
        off_reason=None,
        items=[RecalledItem(**i) for i in kept],
        dropped=[UUID(i) for i in dropped],
    )


@internal_router.post("/related", response_model=RecallResponse)
async def internal_related(
    body: RelatedRequest, actor: ServiceActor, session: InternalSession, settings: SettingsDep
):
    """The extraction's context: the items closest to the turn (not marked used)."""
    run = await _run_of(session, body)
    reason = await memory_settings.off_reason(session, body.project_id, run.agent_id, body.user_id)
    if reason is not None:
        return RecallResponse(off_reason=reason, items=[])
    effective = await memory_settings.effective(session, body.project_id, run.agent_id)
    items = await store.related(
        session,
        settings,
        project_id=body.project_id,
        user_id=body.user_id,
        agent_id=run.agent_id,
        text=body.text,
        n=RELATED_ITEMS,
        kinds=effective.allowed_kinds,
    )
    return RecallResponse(
        off_reason=None,
        items=[RecalledItem(id=i.id, kind=i.kind, text=i.text) for i in items],
        extraction_model=effective.extraction_model,
    )


@internal_router.post("/candidates", response_model=CandidatesResponse)
async def internal_candidates(
    body: CandidatesRequest, actor: ServiceActor, session: InternalSession, settings: SettingsDep
):
    """The extraction job's candidates, written by the store's rules. Memory turned off or the
    user opted out while the job waited: 409, nothing is written."""
    run = await _run_of(session, body)
    if run.status != RunStatus.completed:
        raise conflict("memory_run_not_completed", "Only a completed run teaches memory.")
    effective = await _writable(session, body.project_id, body.user_id, run.agent_id)
    result = await store.write(
        session,
        settings,
        effective,
        project_id=body.project_id,
        user_id=body.user_id,
        agent_id=run.agent_id,
        candidates=[
            store.Candidate(c.kind, c.text.strip(), c.confidence, c.supersedes_id)
            for c in body.items
        ],
        source_run_id=run.id,
        min_confidence=settings.memory_min_confidence,
    )
    await session.commit()
    return CandidatesResponse(
        written=result.written, archived=result.archived, rejected=result.rejected
    )
