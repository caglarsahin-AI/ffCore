"""Knowledge bases: CRUD, documents, reindex, search and test query (package 04a).

Search and test query are POST because the query travels in the body, but they read only:
they stay open in read-only access mode (write-flag scan exemption, like login).
ACL is applied in the query for the caller, or through X-On-Behalf-Of for the end user: the
caller's role and every role below it, plus the caller's own id; a document with no ACL is open
to the project's members (C15).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.knowledge_schemas import (
    DocumentList,
    DocumentOut,
    GateDecision,
    KnowledgeBaseCreate,
    KnowledgeBaseList,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    ReindexAccepted,
    ReindexRequest,
    SearchHit,
    SearchRequest,
    SearchResponse,
    UploadedDocument,
    UploadResult,
)
from ffcore.api.schemas import Role
from ffcore.core.audit import audited
from ffcore.core.auth import ROLE_ORDER, Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.knowledge import ingest, jobs, search
from ffcore.knowledge.chunking import ChunkSettings
from ffcore.knowledge.normalize import NORMALIZER_CONFIG_ID
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorStoreError
from ffcore.models.knowledge import Chunk, Document, KnowledgeBase

router = APIRouter(
    prefix="/projects/{project_id}/knowledge-bases",
    tags=["knowledge-bases"],
    responses=ERROR_RESPONSES,
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
Editor = Annotated[Actor, Depends(require_role("analyst", write=True))]
KbAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
KbIdDep = Annotated[str, Depends(path_resource("kb_id"))]
DocumentIdDep = Annotated[str, Depends(path_resource("document_id"))]
RunIdHeader = Annotated[
    UUID | None,
    Header(alias="X-Run-Id", description="Run this search belongs to; stored in kb_queries (C12)."),
]
# A manual upload without an ACL gets this, shown in the response (brief 04, C15).
DEFAULT_UPLOAD_ROLES = ["analyst"]


def queue_dependency(settings: Annotated[Settings, Depends(get_settings)]) -> jobs.JobQueue:
    return jobs.get_queue(settings)


QueueDep = Annotated[jobs.JobQueue, Depends(queue_dependency)]


async def _kb(session, project_id: UUID, kb_id: UUID) -> KnowledgeBase:
    kb = await session.scalar(
        select(KnowledgeBase).where(
            KnowledgeBase.id == kb_id,
            KnowledgeBase.project_id == project_id,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    if kb is None:
        raise not_found("knowledge_base")
    return kb


async def _kb_out(session, kb: KnowledgeBase) -> KnowledgeBaseOut:
    documents = await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.kb_id == kb.id, Document.deleted_at.is_(None))
    )
    chunks = await session.scalar(
        select(func.count())
        .select_from(Chunk)
        .join(Document, Document.id == Chunk.document_id)
        .where(Chunk.kb_id == kb.id, Document.deleted_at.is_(None))
    )
    data = {c.key: getattr(kb, c.key) for c in KnowledgeBase.__table__.columns}
    return KnowledgeBaseOut(
        **data,
        chunk_max_tokens=ChunkSettings.from_kb(kb.chunk_size, kb.chunk_overlap).max_tokens,
        document_count=documents,
        chunk_count=chunks,
    )


async def _kb_before(session, project_id: UUID, kb_id: UUID, **_) -> KnowledgeBaseOut:
    return await _kb_out(session, await _kb(session, project_id, kb_id))


def _document_out(document: Document, chunk_count: int) -> DocumentOut:
    return DocumentOut(
        id=document.id,
        kb_id=document.kb_id,
        filename=document.filename,
        mime_sniffed=document.mime_sniffed,
        size=document.size,
        sha256=document.sha256,
        status=document.status,
        error=document.error,
        page_count=document.page_count,
        acl_roles=document.acl_roles,
        acl_users=document.acl_users,
        metadata=document.meta,
        version=document.version,
        breadcrumb=document.breadcrumb,
        language=document.language,
        duplicate_of=document.duplicate_of,
        gate0=GateDecision(status=document.gate0_status, reason=document.gate0_reason),
        gate1=GateDecision(status=document.gate1_status, reason=document.gate1_reason),
        gate2=GateDecision(status=document.gate2_status, reason=document.gate2_reason),
        convert_engine=document.convert_engine,
        convert_seconds=document.convert_seconds,
        chunk_count=chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


async def _chunk_counts(session, document_ids: list[UUID]) -> dict[UUID, int]:
    if not document_ids:
        return {}
    rows = await session.execute(
        select(Chunk.document_id, func.count())
        .where(Chunk.document_id.in_(document_ids))
        .group_by(Chunk.document_id)
    )
    return dict(rows.all())


def _check_installation_model(body: KnowledgeBaseCreate, settings: Settings) -> None:
    """One embedding model per installation (P5): a different choice is refused, not ignored."""
    if body.embed_dim is not None and body.embed_dim != settings.embed_dim:
        raise ApiError(
            400,
            "invalid_request_error",
            "embed_dim_mismatch",
            f"embed_dim {body.embed_dim} differs from EMBED_DIM {settings.embed_dim}.",
        )
    if body.embed_model is not None and body.embed_model != settings.embed_model:
        raise ApiError(
            400,
            "invalid_request_error",
            "embed_model_mismatch",
            f"This installation embeds with {settings.embed_model} only.",
        )


def _check_chunking(chunk_size: int, chunk_overlap: int) -> None:
    try:
        ChunkSettings.from_kb(chunk_size, chunk_overlap)
    except ValueError:
        raise invalid(
            "chunk_overlap_unsupported", "Chunk overlap is not supported; it must be 0."
        ) from None


def _vector_error(exc: VectorStoreError) -> ApiError:
    return ApiError(503, "api_error", exc.code, str(exc))


@router.get("", response_model=KnowledgeBaseList)
async def list_knowledge_bases(project_id: UUID, actor: Reader, session: SessionDep):
    kbs = (
        await session.scalars(
            select(KnowledgeBase)
            .where(KnowledgeBase.project_id == project_id, KnowledgeBase.deleted_at.is_(None))
            .order_by(KnowledgeBase.key)
        )
    ).all()
    return KnowledgeBaseList(data=[await _kb_out(session, kb) for kb in kbs])


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
@audited("create_knowledge_base", "knowledge_base")
async def create_knowledge_base(
    project_id: UUID,
    body: KnowledgeBaseCreate,
    request: Request,
    actor: KbAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    _check_installation_model(body, settings)
    _check_chunking(body.chunk_size, body.chunk_overlap)
    taken = await session.scalar(
        select(KnowledgeBase.id).where(
            KnowledgeBase.project_id == project_id,
            KnowledgeBase.key == body.key,
            KnowledgeBase.deleted_at.is_(None),
        )
    )
    if taken is not None:
        raise conflict("knowledge_base_key_taken", "This knowledge base key is already used.")
    kb = KnowledgeBase(
        project_id=project_id,
        key=body.key,
        name=body.name,
        description=body.description,
        embed_model=settings.embed_model,
        embed_dim=settings.embed_dim,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        hybrid=body.hybrid,
        rerank=body.rerank,
        rerank_model=settings.rerank_model,
        default_top_k=body.default_top_k,
        default_min_score=body.default_min_score,
        default_filter=body.default_filter,
        normalizer_config_id=NORMALIZER_CONFIG_ID,
        created_by=actor.actor_id,
    )
    session.add(kb)
    await session.flush()
    await session.refresh(kb)
    return await _kb_out(session, kb)


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(project_id: UUID, kb_id: UUID, actor: Reader, session: SessionDep):
    return await _kb_out(session, await _kb(session, project_id, kb_id))


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
@audited("update_knowledge_base", "knowledge_base", load_before=_kb_before)
async def update_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
    request: Request,
    actor: KbAdmin,
    session: SessionDep,
):
    kb = await _kb(session, project_id, kb_id)
    changes = body.model_dump(exclude_unset=True)
    _check_chunking(changes.get("chunk_size", kb.chunk_size), changes.get("chunk_overlap", 0))
    for field, value in changes.items():
        setattr(kb, field, value)
    await session.flush()
    await session.refresh(kb)
    return await _kb_out(session, kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("delete_knowledge_base", "knowledge_base", load_before=_kb_before)
async def delete_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    request: Request,
    actor: KbAdmin,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: KbIdDep,
) -> None:
    kb = await _kb(session, project_id, kb_id)
    # Vector store first, for the same reason as delete_document.
    try:
        await jobs.get_vector_store(settings).drop_collection(kb.id)
    except VectorStoreError as exc:
        raise _vector_error(exc) from None
    kb.deleted_at = func.now()
    await session.execute(
        Document.__table__.update()
        .where(Document.kb_id == kb.id, Document.deleted_at.is_(None))
        .values(deleted_at=func.now())
    )


@router.get("/{kb_id}/documents", response_model=DocumentList)
async def list_documents(project_id: UUID, kb_id: UUID, actor: Reader, session: SessionDep):
    kb = await _kb(session, project_id, kb_id)
    documents = (
        await session.scalars(
            select(Document)
            .where(Document.kb_id == kb.id, Document.deleted_at.is_(None))
            .order_by(Document.filename)
        )
    ).all()
    counts = await _chunk_counts(session, [d.id for d in documents])
    return DocumentList(data=[_document_out(d, counts.get(d.id, 0)) for d in documents])


@router.post(
    "/{kb_id}/documents", response_model=UploadResult, status_code=status.HTTP_202_ACCEPTED
)
@audited("upload_documents", "document")
async def upload_documents(
    project_id: UUID,
    kb_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    queue: QueueDep,
    resource_id: KbIdDep,
    files: Annotated[list[UploadFile], File(description="One or more files.")],
    acl_roles: Annotated[
        list[Role] | None,
        Form(
            description="Roles that may read the files. Omitted: analyst (shown in the "
            "response). An empty ACL is only set with acl_open=true (C15)."
        ),
    ] = None,
    acl_users: Annotated[list[UUID] | None, Form(description="Users that may read.")] = None,
    acl_open: Annotated[
        bool,
        Form(description="Open the files to every project member (empty ACL), on purpose."),
    ] = False,
):
    kb = await _kb(session, project_id, kb_id)
    roles = [r.value for r in acl_roles or []]
    users = list(acl_users or [])
    if acl_open and (roles or users):
        raise invalid("acl_conflict", "acl_open cannot be combined with acl_roles or acl_users.")
    if not acl_open and not roles and not users:
        roles = list(DEFAULT_UPLOAD_ROLES)
    uploaded = []
    for upload in files:
        document, outcome = await ingest.register_upload(
            session,
            kb.id,
            filename=upload.filename or "upload",
            data=await upload.read(),
            acl_roles=roles,
            acl_users=users,
            created_by=actor.actor_id,
            settings=settings,
        )
        uploaded.append((document, outcome))
    out = []
    for document, outcome in uploaded:
        # The worker re-reads the row; a job for a row not committed yet retries (worker.py).
        if outcome != "unchanged" and document.status == "pending":
            await queue.enqueue("ingest_document_job", str(document.id))
        out.append(UploadedDocument(outcome=outcome, document=_document_out(document, 0)))
    return UploadResult(data=out)


async def _document(session, project_id: UUID, kb_id: UUID, document_id: UUID) -> Document:
    kb = await _kb(session, project_id, kb_id)
    document = await session.scalar(
        select(Document).where(
            Document.id == document_id, Document.kb_id == kb.id, Document.deleted_at.is_(None)
        )
    )
    if document is None:
        raise not_found("document")
    return document


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    project_id: UUID, kb_id: UUID, document_id: UUID, actor: Reader, session: SessionDep
):
    document = await _document(session, project_id, kb_id, document_id)
    counts = await _chunk_counts(session, [document.id])
    return _document_out(document, counts.get(document.id, 0))


@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
@audited("delete_document", "document")
async def delete_document(
    project_id: UUID,
    kb_id: UUID,
    document_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: DocumentIdDep,
) -> None:
    """Soft delete: the document leaves search at once (chunks removed); raw stays (D3)."""
    document = await _document(session, project_id, kb_id, document_id)
    # Vector store first: the pgvector driver writes chunks in its own session, which would wait
    # forever on rows this request already deleted (and Qdrant must not keep points of a
    # document that is gone). A store failure leaves the document as it was (503).
    try:
        await jobs.get_vector_store(settings).delete_by_document(document.id)
    except VectorStoreError as exc:
        raise _vector_error(exc) from None
    document.deleted_at = func.now()
    await session.execute(Chunk.__table__.delete().where(Chunk.document_id == document.id))


@router.post(
    "/{kb_id}/reindex", response_model=ReindexAccepted, status_code=status.HTTP_202_ACCEPTED
)
@audited("reindex_knowledge_base", "knowledge_base")
async def reindex_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: ReindexRequest,
    request: Request,
    actor: Editor,
    session: SessionDep,
    queue: QueueDep,
    resource_id: KbIdDep,
):
    kb = await _kb(session, project_id, kb_id)
    documents = await session.scalar(
        select(func.count())
        .select_from(Document)
        .where(Document.kb_id == kb.id, Document.deleted_at.is_(None))
    )
    job_id = await queue.enqueue("reindex_job", str(kb.id), body.layer.value, body.full)
    return ReindexAccepted(job_id=job_id, layer=body.layer, full=body.full, documents=documents)


def acl_for(request: Request, actor: Actor) -> VectorFilters:
    """The caller's role and every role below it, plus the caller's id."""
    grant = request.state.grant
    roles = ROLE_ORDER if grant.is_superadmin else ROLE_ORDER[: ROLE_ORDER.index(grant.role) + 1]
    return VectorFilters(acl_roles=tuple(roles), acl_users=(actor.actor_id,))


async def _search(request, actor, session, settings, project_id, kb_id, body, run_id, source):
    kb = await _kb(session, project_id, kb_id)
    acl = acl_for(request, actor)
    filters = VectorFilters(
        document_ids=tuple(body.filters.document_ids),
        acl_roles=acl.acl_roles,
        acl_users=acl.acl_users,
        metadata=tuple(sorted(body.filters.metadata.items())),
    )
    try:
        result = await search.search(
            session,
            kb,
            body.query,
            filters=filters,
            top_k=body.top_k,
            hybrid=body.hybrid,
            run_id=run_id,
            user_id=actor.actor_id,
            source=source,
            settings=settings,
            store=jobs.get_vector_store(settings),
        )
    except VectorStoreError as exc:
        raise _vector_error(exc) from None
    await session.commit()
    return SearchResponse(
        query_id=result.query_id,
        hits=[SearchHit(**hit.__dict__) for hit in result.hits],
        threshold_mode=result.threshold_mode,
        filtered_by_rerank_floor=result.filtered_by_rerank_floor,
        filtered_by_min_score=result.filtered_by_min_score,
        normalizer_config_id=result.normalizer_config_id,
        latency_ms=result.latency_ms,
    )


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: SearchRequest,
    request: Request,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
    run_id: RunIdHeader = None,
):
    """Hybrid search with ACL applied in the query for the caller (or, through
    X-On-Behalf-Of, the end user)."""
    return await _search(request, actor, session, settings, project_id, kb_id, body, run_id, "api")


@router.post("/{kb_id}/test-query", response_model=SearchResponse)
async def test_query(
    project_id: UUID,
    kb_id: UUID,
    body: SearchRequest,
    request: Request,
    actor: Reader,
    session: SessionDep,
    settings: SettingsDep,
):
    """Playground: same search, logged with source=playground."""
    return await _search(
        request, actor, session, settings, project_id, kb_id, body, None, "playground"
    )
