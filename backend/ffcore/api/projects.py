"""Projects, members and readiness."""

from uuid import UUID

from fastapi import APIRouter

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import (
    MemberCreate,
    MemberList,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectList,
    ProjectOut,
    ProjectUpdate,
    ReadinessOut,
)

router = APIRouter(prefix="/projects", tags=["projects"], responses=ERROR_RESPONSES)


@router.get("", response_model=ProjectList, summary="List projects visible to the caller")
async def list_projects():
    raise not_implemented()


@router.post("", response_model=ProjectOut, status_code=201, summary="Create a project")
async def create_project(body: ProjectCreate):
    """Superadmin with edit access. The key is global, unique and cannot be changed later."""
    raise not_implemented()


@router.get("/{project_id}", response_model=ProjectOut, summary="Get a project")
async def get_project(project_id: UUID):
    raise not_implemented()


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update a project")
async def update_project(project_id: UUID, body: ProjectUpdate):
    raise not_implemented()


@router.delete("/{project_id}", status_code=204, summary="Delete a project (soft delete)")
async def delete_project(project_id: UUID) -> None:
    raise not_implemented()


@router.get(
    "/{project_id}/readiness", response_model=ReadinessOut, summary="Project readiness checks"
)
async def get_readiness(project_id: UUID):
    """Model provider assigned, vector provider assigned, project admin present."""
    raise not_implemented()


@router.get("/{project_id}/members", response_model=MemberList, summary="List members")
async def list_members(project_id: UUID):
    raise not_implemented()


@router.post(
    "/{project_id}/members", response_model=MemberOut, status_code=201, summary="Add a member"
)
async def add_member(project_id: UUID, body: MemberCreate):
    """Only `admin` and `analyst` can be assigned in this release (422 `role_reserved`)."""
    raise not_implemented()


@router.patch(
    "/{project_id}/members/{user_id}", response_model=MemberOut, summary="Change role or access"
)
async def update_member(project_id: UUID, user_id: UUID, body: MemberUpdate):
    raise not_implemented()


@router.delete("/{project_id}/members/{user_id}", status_code=204, summary="Remove a member")
async def remove_member(project_id: UUID, user_id: UUID) -> None:
    raise not_implemented()
