"""Projects, members and readiness."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import any_, func, literal, select

from ffcore.api.auth import user_actor
from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.schemas import (
    MemberCreate,
    MemberList,
    MemberOut,
    MemberUpdate,
    ProjectCreate,
    ProjectList,
    ProjectOut,
    ProjectUpdate,
    ReadinessCheck,
    ReadinessOut,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role, require_superadmin
from ffcore.models.catalog import Provider, ProviderProject
from ffcore.models.identity import ASSIGNABLE_ROLES, Project, ProjectMember, User

router = APIRouter(prefix="/projects", tags=["projects"], responses=ERROR_RESPONSES)

ProjectReader = Annotated[Actor, Depends(require_role("analyst"))]
ProjectAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]
TenantWriter = Annotated[Actor, Depends(require_superadmin(write=True))]
UserActor = Annotated[Actor, Depends(user_actor)]
ProjectIdDep = Annotated[str, Depends(path_resource("project_id"))]
MemberIdDep = Annotated[str, Depends(path_resource("user_id"))]


def project_out(project: Project) -> ProjectOut:
    return ProjectOut.model_validate(project, from_attributes=True)


async def _project(session, project_id: UUID) -> Project:
    project = await session.scalar(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    if project is None:
        raise not_found("project")
    return project


async def _project_before(session, project_id: UUID, **_) -> ProjectOut:
    return project_out(await _project(session, project_id))


def _assignable(role: str | None) -> None:
    if role is not None and role not in ASSIGNABLE_ROLES:
        raise invalid("role_reserved", f"Role '{role}' cannot be assigned in this release.")


async def _member_out(session, project_id: UUID, user_id: UUID) -> MemberOut:
    row = (
        await session.execute(
            select(ProjectMember, User)
            .join(User, User.id == ProjectMember.user_id)
            .where(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        )
    ).first()
    if row is None:
        raise not_found("member")
    member, user = row
    return MemberOut(
        project_id=member.project_id,
        user_id=member.user_id,
        email=user.email,
        full_name=user.full_name,
        role=member.role,
        access=member.access,
    )


async def _member_before(session, project_id: UUID, user_id: UUID, **_) -> MemberOut:
    return await _member_out(session, project_id, user_id)


@router.get("", response_model=ProjectList, summary="List projects visible to the caller")
async def list_projects(actor: UserActor, session: SessionDep):
    """Superadmins see every project; other users see the projects they are members of."""
    user = await session.get(User, UUID(actor.actor_id))
    query = select(Project).where(Project.deleted_at.is_(None)).order_by(Project.key)
    if user is None or not user.is_superadmin:
        query = query.join(ProjectMember, ProjectMember.project_id == Project.id).where(
            ProjectMember.user_id == UUID(actor.actor_id)
        )
    return ProjectList(data=[project_out(p) for p in await session.scalars(query)])


@router.post("", response_model=ProjectOut, status_code=201, summary="Create a project")
@audited("create_project", "project")
async def create_project(
    body: ProjectCreate, request: Request, actor: TenantWriter, session: SessionDep
):
    """Superadmin with edit access. The key is global, unique and cannot be changed later."""
    # Soft-deleted projects keep their key: the name "<key>.<model>" is never reused (C1).
    if await session.scalar(select(Project.id).where(Project.key == body.key)) is not None:
        raise conflict("project_key_taken", "This project key is already used.")
    project = Project(
        key=body.key, name=body.name, description=body.description, created_by=actor.actor_id
    )
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project_out(project)


@router.get("/{project_id}", response_model=ProjectOut, summary="Get a project")
async def get_project(project_id: UUID, actor: ProjectReader, session: SessionDep):
    return project_out(await _project(session, project_id))


@router.patch("/{project_id}", response_model=ProjectOut, summary="Update a project")
@audited("update_project", "project", load_before=_project_before)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
):
    project = await _project(session, project_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await session.flush()
    await session.refresh(project)
    return project_out(project)


@router.delete("/{project_id}", status_code=204, summary="Delete a project (soft delete)")
@audited("delete_project", "project", load_before=_project_before)
async def delete_project(
    project_id: UUID,
    request: Request,
    actor: TenantWriter,
    session: SessionDep,
    resource_id: ProjectIdDep,
) -> None:
    project = await _project(session, project_id)
    project.deleted_at = func.now()


@router.get(
    "/{project_id}/readiness", response_model=ReadinessOut, summary="Project readiness checks"
)
async def get_readiness(project_id: UUID, actor: ProjectReader, session: SessionDep):
    """Model provider assigned, vector provider assigned, project admin present."""
    # 03c adds two checks here: at least one limit, at least one active alert rule.
    await _project(session, project_id)

    async def provider_with(domain: str) -> bool:
        found = await session.scalar(
            select(Provider.id)
            .join(ProviderProject, ProviderProject.provider_id == Provider.id)
            .where(
                ProviderProject.project_id == project_id,
                Provider.is_active,
                literal(domain) == any_(Provider.domains),
            )
            .limit(1)
        )
        return found is not None

    admin = await session.scalar(
        select(ProjectMember.user_id)
        .join(User, User.id == ProjectMember.user_id)
        .where(
            ProjectMember.project_id == project_id,
            ProjectMember.role == "admin",
            User.is_active,
            User.deleted_at.is_(None),
        )
        .limit(1)
    )
    checks = [
        ReadinessCheck(
            key="model_provider",
            ok=await provider_with("model"),
            detail="An active provider serving models is assigned to the project.",
        ),
        ReadinessCheck(
            key="vector_provider",
            ok=await provider_with("vector"),
            detail="An active vector store provider is assigned to the project.",
        ),
        ReadinessCheck(
            key="project_admin",
            ok=admin is not None,
            detail="The project has at least one active member with the admin role.",
        ),
    ]
    return ReadinessOut(
        project_id=project_id,
        passed=sum(c.ok for c in checks),
        total=len(checks),
        checks=checks,
    )


@router.get("/{project_id}/members", response_model=MemberList, summary="List members")
async def list_members(project_id: UUID, actor: ProjectReader, session: SessionDep):
    rows = await session.execute(
        select(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .where(ProjectMember.project_id == project_id, User.deleted_at.is_(None))
        .order_by(func.lower(User.email))
    )
    return MemberList(
        data=[
            MemberOut(
                project_id=m.project_id,
                user_id=m.user_id,
                email=u.email,
                full_name=u.full_name,
                role=m.role,
                access=m.access,
            )
            for m, u in rows
        ]
    )


@router.post(
    "/{project_id}/members", response_model=MemberOut, status_code=201, summary="Add a member"
)
@audited("add_member", "project_member")
async def add_member(
    project_id: UUID,
    body: MemberCreate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
):
    """Only `admin` and `analyst` can be assigned in this release (422 `role_reserved`)."""
    _assignable(body.role)
    user = await session.scalar(
        select(User).where(User.id == body.user_id, User.deleted_at.is_(None))
    )
    if user is None:
        raise not_found("user")
    if await session.get(ProjectMember, (project_id, body.user_id)) is not None:
        raise conflict("member_exists", "The user is already a member of this project.")
    session.add(
        ProjectMember(
            project_id=project_id,
            user_id=body.user_id,
            role=body.role,
            access=body.access,
            created_by=actor.actor_id,
        )
    )
    await session.flush()
    return await _member_out(session, project_id, body.user_id)


@router.patch(
    "/{project_id}/members/{user_id}", response_model=MemberOut, summary="Change role or access"
)
@audited("update_member", "project_member", load_before=_member_before)
async def update_member(
    project_id: UUID,
    user_id: UUID,
    body: MemberUpdate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    resource_id: MemberIdDep,
):
    _assignable(body.role)
    member = await session.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise not_found("member")
    for field, value in body.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(member, field, value)
    await session.flush()
    return await _member_out(session, project_id, user_id)


@router.delete("/{project_id}/members/{user_id}", status_code=204, summary="Remove a member")
@audited("remove_member", "project_member", load_before=_member_before)
async def remove_member(
    project_id: UUID,
    user_id: UUID,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    resource_id: MemberIdDep,
) -> None:
    member = await session.get(ProjectMember, (project_id, user_id))
    if member is None:
        raise not_found("member")
    await session.delete(member)
