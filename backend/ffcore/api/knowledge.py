"""Knowledge bases: CRUD, documents, reindex, search and test query (package 04a).

Search and test query are POST because the query travels in the body, but they read only:
they stay open in read-only access mode (write-flag scan exemption, like login).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status

from ffcore.api.common import ERROR_RESPONSES, SessionDep, not_implemented
from ffcore.api.knowledge_schemas import (
    DocumentList,
    DocumentOut,
    KnowledgeBaseCreate,
    KnowledgeBaseList,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
    ReindexAccepted,
    ReindexRequest,
    SearchRequest,
    SearchResponse,
    UploadResult,
)
from ffcore.api.schemas import Role
from ffcore.core.auth import Actor, require_role

router = APIRouter(
    prefix="/projects/{project_id}/knowledge-bases",
    tags=["knowledge-bases"],
    responses=ERROR_RESPONSES,
)

Reader = Annotated[Actor, Depends(require_role("analyst"))]
Editor = Annotated[Actor, Depends(require_role("analyst", write=True))]
KbAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]
RunIdHeader = Annotated[
    UUID | None,
    Header(alias="X-Run-Id", description="Run this search belongs to; stored in kb_queries (C12)."),
]


@router.get("", response_model=KnowledgeBaseList)
async def list_knowledge_bases(project_id: UUID, actor: Reader, session: SessionDep):
    raise not_implemented()


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    project_id: UUID,
    body: KnowledgeBaseCreate,
    request: Request,
    actor: KbAdmin,
    session: SessionDep,
):
    raise not_implemented()


@router.get("/{kb_id}", response_model=KnowledgeBaseOut)
async def get_knowledge_base(project_id: UUID, kb_id: UUID, actor: Reader, session: SessionDep):
    raise not_implemented()


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: KnowledgeBaseUpdate,
    request: Request,
    actor: KbAdmin,
    session: SessionDep,
):
    raise not_implemented()


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    project_id: UUID, kb_id: UUID, request: Request, actor: KbAdmin, session: SessionDep
):
    raise not_implemented()


@router.get("/{kb_id}/documents", response_model=DocumentList)
async def list_documents(project_id: UUID, kb_id: UUID, actor: Reader, session: SessionDep):
    raise not_implemented()


@router.post(
    "/{kb_id}/documents", response_model=UploadResult, status_code=status.HTTP_202_ACCEPTED
)
async def upload_documents(
    project_id: UUID,
    kb_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
    files: Annotated[list[UploadFile], File(description="One or more files.")],
    acl_roles: Annotated[
        list[Role] | None,
        Form(
            description="Roles that may read the files. Omitted: analyst (shown in the "
            "response). Send none of acl_roles and acl_users only on purpose: an empty ACL "
            "opens the document to every project member (C15)."
        ),
    ] = None,
    acl_users: Annotated[list[UUID] | None, Form(description="Users that may read.")] = None,
):
    raise not_implemented()


@router.get("/{kb_id}/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    project_id: UUID, kb_id: UUID, document_id: UUID, actor: Reader, session: SessionDep
):
    raise not_implemented()


@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    project_id: UUID,
    kb_id: UUID,
    document_id: UUID,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    raise not_implemented()


@router.post(
    "/{kb_id}/reindex", response_model=ReindexAccepted, status_code=status.HTTP_202_ACCEPTED
)
async def reindex_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: ReindexRequest,
    request: Request,
    actor: Editor,
    session: SessionDep,
):
    raise not_implemented()


@router.post("/{kb_id}/search", response_model=SearchResponse)
async def search_knowledge_base(
    project_id: UUID,
    kb_id: UUID,
    body: SearchRequest,
    actor: Reader,
    session: SessionDep,
    run_id: RunIdHeader = None,
):
    """Hybrid search with ACL applied in the query for the caller (or, through
    X-On-Behalf-Of, the end user)."""
    raise not_implemented()


@router.post("/{kb_id}/test-query", response_model=SearchResponse)
async def test_query(
    project_id: UUID, kb_id: UUID, body: SearchRequest, actor: Reader, session: SessionDep
):
    """Playground: same search, logged with source=playground."""
    raise not_implemented()
