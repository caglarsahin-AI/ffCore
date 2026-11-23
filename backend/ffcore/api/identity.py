"""17 identity administration: group mappings, identity provider status and test, CSV import.

Mappings are project-scoped routes (a project admin manages their own project; a superadmin
passes the same check), plus one tenant-wide list for the superadmin's settings screen.
"""

import csv
import io
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy import func, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.identity_schemas import (
    IdentityProvidersOut,
    ImportReport,
    ImportRow,
    ImportSummary,
    LastSync,
    MappingCreate,
    MappingList,
    MappingOut,
    ProviderStatus,
    ProviderTestOut,
    SignInProviders,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.core.identity import affected_members, normalise_group, temporary_password
from ffcore.core.ldap_auth import LdapDirectory, get_ldap_directory
from ffcore.core.passwords import hash_password
from ffcore.models.audit import AuditEvent
from ffcore.models.identity import (
    ACCESS_MODES,
    ASSIGNABLE_ROLES,
    IdentityGroupMapping,
    Project,
    ProjectMember,
    User,
)

router = APIRouter(tags=["identity"], responses=ERROR_RESPONSES)

SettingsDep = Annotated[Settings, Depends(get_settings)]
DirectoryDep = Annotated[LdapDirectory | None, Depends(get_ldap_directory)]
ProjectAdmin = Annotated[Actor, Depends(require_role("admin"))]
ProjectAdminWriter = Annotated[Actor, Depends(require_role("admin", write=True))]
Reader = Annotated[Actor, Depends(require_superadmin())]
Writer = Annotated[Actor, Depends(require_superadmin(write=True))]
MappingIdDep = Annotated[str, Depends(path_resource("mapping_id"))]

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
IMPORT_MAX_BYTES = 1024 * 1024
IMPORT_MAX_ROWS = 5000
IMPORT_COLUMNS = ("email", "full_name", "role", "access", "project_keys")


# --- login screen ---


@router.get(
    "/auth/providers",
    response_model=SignInProviders,
    summary="Sign-in methods this installation offers (login screen)",
)
async def sign_in_providers(settings: SettingsDep):
    """No authentication: flags only, never an address or a setting value. `local` is false
    when LOCAL_LOGIN=off (the same form still signs in the superadmin and directory accounts)."""
    return SignInProviders(
        local=settings.local_login != "off", ldap=settings.ldap_enabled, oidc=False
    )


# --- group mappings ---


def _mapping_out(mapping: IdentityGroupMapping, project_key: str) -> MappingOut:
    return MappingOut(
        id=mapping.id,
        project_id=mapping.project_id,
        project_key=project_key,
        provider=mapping.provider,
        external_group=mapping.external_group,
        role=mapping.role,
        access=mapping.access,
        created_by=mapping.created_by,
        created_at=mapping.created_at,
    )


async def _mappings(session, project_id: uuid.UUID | None) -> list[MappingOut]:
    query = (
        select(IdentityGroupMapping, Project.key)
        .join(Project, Project.id == IdentityGroupMapping.project_id)
        .where(IdentityGroupMapping.deleted_at.is_(None), Project.deleted_at.is_(None))
        .order_by(Project.key, IdentityGroupMapping.provider, IdentityGroupMapping.external_group)
    )
    if project_id is not None:
        query = query.where(IdentityGroupMapping.project_id == project_id)
    return [_mapping_out(m, key) for m, key in await session.execute(query)]


@router.get("/identity-mappings", response_model=MappingList, summary="List all group mappings")
async def list_all_mappings(actor: Reader, session: SessionDep):
    data = await _mappings(session, None)
    count = await session.scalar(
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.membership_source == "idp")
    )
    return MappingList(data=data, affected_members=int(count or 0))


@router.get(
    "/projects/{project_id}/identity-mappings",
    response_model=MappingList,
    summary="List the project's group mappings",
)
async def list_mappings(project_id: uuid.UUID, actor: ProjectAdmin, session: SessionDep):
    return MappingList(
        data=await _mappings(session, project_id),
        affected_members=await affected_members(session, project_id),
    )


@router.post(
    "/projects/{project_id}/identity-mappings",
    response_model=MappingOut,
    status_code=201,
    summary="Map a directory group to a project role",
)
@audited("create_identity_mapping", "identity_mapping")
async def create_mapping(
    project_id: uuid.UUID,
    body: MappingCreate,
    request: Request,
    actor: ProjectAdminWriter,
    session: SessionDep,
):
    """Applied at each member's next sign-in (and to directory accounts created later)."""
    if body.role.value not in ASSIGNABLE_ROLES:
        raise invalid("role_reserved", "This role cannot be assigned yet.")
    group = normalise_group(body.provider, body.external_group)
    if not group:
        raise invalid("external_group_invalid", "The group name is empty.")
    taken = await session.scalar(
        select(IdentityGroupMapping.id).where(
            IdentityGroupMapping.project_id == project_id,
            IdentityGroupMapping.provider == body.provider,
            IdentityGroupMapping.external_group == group,
            IdentityGroupMapping.deleted_at.is_(None),
        )
    )
    if taken is not None:
        raise conflict("mapping_exists", "This group is already mapped in the project.")
    mapping = IdentityGroupMapping(
        project_id=project_id,
        provider=body.provider,
        external_group=group,
        role=body.role.value,
        access=body.access.value,
        created_by=actor.actor_id,
    )
    session.add(mapping)
    await session.flush()
    await session.refresh(mapping)
    key = await session.scalar(select(Project.key).where(Project.id == project_id))
    return _mapping_out(mapping, key)


async def _live_mapping(session, project_id: uuid.UUID, mapping_id: uuid.UUID):
    mapping = await session.scalar(
        select(IdentityGroupMapping).where(
            IdentityGroupMapping.id == mapping_id,
            IdentityGroupMapping.project_id == project_id,
            IdentityGroupMapping.deleted_at.is_(None),
        )
    )
    if mapping is None:
        raise not_found("identity_mapping")
    return mapping


async def _mapping_before(session, project_id: uuid.UUID, mapping_id: uuid.UUID, **_):
    mapping = await _live_mapping(session, project_id, mapping_id)
    return {
        "provider": mapping.provider,
        "external_group": mapping.external_group,
        "role": mapping.role,
        "access": mapping.access,
    }


@router.delete(
    "/projects/{project_id}/identity-mappings/{mapping_id}",
    status_code=204,
    summary="Remove a group mapping",
)
@audited("delete_identity_mapping", "identity_mapping", load_before=_mapping_before)
async def delete_mapping(
    project_id: uuid.UUID,
    mapping_id: uuid.UUID,
    request: Request,
    actor: ProjectAdminWriter,
    session: SessionDep,
    resource_id: MappingIdDep,
) -> None:
    """Memberships it gave are removed at each member's next sign-in (manual ones stay)."""
    mapping = await _live_mapping(session, project_id, mapping_id)
    mapping.deleted_at = func.now()


# --- identity providers ---


@router.get(
    "/identity-providers",
    response_model=IdentityProvidersOut,
    summary="Identity provider status (no secret)",
)
async def identity_providers(actor: Reader, session: SessionDep, settings: SettingsDep):
    counts = dict(
        (
            await session.execute(
                select(User.auth_source, func.count())
                .where(User.deleted_at.is_(None))
                .group_by(User.auth_source)
            )
        ).all()
    )
    transport = None
    if settings.ldap_enabled:
        transport = "ldaps" if settings.ldap_url.lower().startswith("ldaps://") else "ldap"
    last = await session.scalar(
        select(AuditEvent)
        .where(AuditEvent.action == "identity.sync")
        .order_by(AuditEvent.ts.desc())
        .limit(1)
    )
    last_sync = None
    if last is not None:
        after = last.after or {}
        last_sync = LastSync(
            at=last.ts,
            outcome=last.outcome,
            checked=after.get("checked"),
            deactivated=after.get("deactivated"),
            error=after.get("error"),
        )
    return IdentityProvidersOut(
        local_login=settings.local_login,
        providers=[
            ProviderStatus(
                provider="ldap",
                enabled=settings.ldap_enabled,
                transport=transport,
                accounts=int(counts.get("ldap", 0)),
            ),
            ProviderStatus(provider="oidc", enabled=False, accounts=int(counts.get("oidc", 0))),
        ],
        last_sync=last_sync,
    )


@router.post(
    "/identity-providers/ldap/test",
    response_model=ProviderTestOut,
    summary="Test the directory connection with the service account",
)
@audited("test_identity_provider", "identity_provider")
async def test_ldap(request: Request, actor: Writer, session: SessionDep, directory: DirectoryDep):
    """Binds with the service account and reports the time taken; changes nothing."""
    if directory is None:
        raise invalid("identity_provider_disabled", "LDAP is not configured (LDAP_URL).")
    result = await directory.probe()
    return ProviderTestOut(
        provider="ldap", ok=result.ok, elapsed_ms=result.elapsed_ms, code=result.code
    )


# --- CSV import (local accounts) ---


def _read_csv(raw: bytes) -> list[dict]:
    if len(raw) > IMPORT_MAX_BYTES:
        raise invalid("import_too_large", "The file is larger than 1 MiB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise invalid("import_encoding", "The file must be UTF-8 CSV.") from None
    reader = csv.DictReader(io.StringIO(text))
    header = [name.strip().lower() for name in reader.fieldnames or []]
    if tuple(header) != IMPORT_COLUMNS:
        raise invalid(
            "import_header_invalid",
            f"The first line must be: {','.join(IMPORT_COLUMNS)}.",
        )
    reader.fieldnames = header
    rows = list(reader)
    if len(rows) > IMPORT_MAX_ROWS:
        raise invalid("import_too_many_rows", f"At most {IMPORT_MAX_ROWS} rows per file.")
    return rows


def _row_error(line: int, email: str | None, code: str) -> ImportRow:
    return ImportRow(line=line, email=email, action="error", code=code)


@router.post("/users/import", response_model=ImportReport, summary="Import local users (CSV)")
@audited("user_imported", "user", redact_fields=("rows",))
async def import_users(
    request: Request,
    actor: Writer,
    session: SessionDep,
    file: Annotated[UploadFile, File(description="CSV: email,full_name,role,access,project_keys")],
    dry_run: Annotated[bool, Query(description="Report only; nothing is written.")] = True,
):
    """Columns `email, full_name, role, access, project_keys` (keys separated by `;`). A bad
    row never stops the file: it is reported with its line number and skipped. A new account
    gets a temporary password, returned once in the applied answer and never stored in clear or
    audited; it must be changed at first sign-in. Directory accounts are refused: the directory
    manages them."""
    rows = _read_csv(await file.read())
    keys = {
        key: pid
        for key, pid in await session.execute(
            select(Project.key, Project.id).where(Project.deleted_at.is_(None))
        )
    }
    report: list[ImportRow] = []
    seen: set[str] = set()
    plans: list[tuple[ImportRow, dict]] = []
    for index, row in enumerate(rows, start=2):
        email = (row.get("email") or "").strip()
        full_name = (row.get("full_name") or "").strip()
        role = (row.get("role") or "").strip().lower()
        access = (row.get("access") or "").strip().lower()
        project_keys = [k.strip() for k in (row.get("project_keys") or "").split(";") if k.strip()]
        if None in row:
            report.append(_row_error(index, email or None, "row_columns"))
            continue
        if not EMAIL.match(email):
            report.append(_row_error(index, email or None, "invalid_email"))
            continue
        if email.lower() in seen:
            report.append(_row_error(index, email, "duplicate_email"))
            continue
        seen.add(email.lower())
        if not 1 <= len(full_name) <= 200:
            report.append(_row_error(index, email, "invalid_full_name"))
            continue
        if role not in ASSIGNABLE_ROLES:
            report.append(_row_error(index, email, "invalid_role"))
            continue
        if access not in ACCESS_MODES:
            report.append(_row_error(index, email, "invalid_access"))
            continue
        unknown = [k for k in project_keys if k not in keys]
        if unknown:
            report.append(_row_error(index, email, "unknown_project"))
            continue
        existing = await session.scalar(
            select(User).where(func.lower(User.email) == email.lower(), User.deleted_at.is_(None))
        )
        if existing is not None and existing.auth_source != "local":
            report.append(_row_error(index, email, "external_identity"))
            continue
        item = ImportRow(line=index, email=email, action="update" if existing else "create")
        report.append(item)
        plans.append(
            (
                item,
                {
                    "user": existing,
                    "full_name": full_name,
                    "role": role,
                    "access": access,
                    "projects": [keys[k] for k in project_keys],
                },
            )
        )
    if not dry_run:
        for item, plan in plans:
            user = plan["user"]
            if user is None:
                password = temporary_password()
                user = User(
                    email=item.email,
                    full_name=plan["full_name"],
                    password_hash=hash_password(password),
                    must_change_password=True,
                )
                session.add(user)
                await session.flush()
                item.temporary_password = password
            elif user.full_name != plan["full_name"]:
                user.full_name = plan["full_name"]
            for project_id in plan["projects"]:
                member = await session.get(ProjectMember, (project_id, user.id))
                if member is None:
                    session.add(
                        ProjectMember(
                            project_id=project_id,
                            user_id=user.id,
                            role=plan["role"],
                            access=plan["access"],
                            created_by=actor.actor_id,
                            membership_source="manual",
                        )
                    )
                else:
                    member.role, member.access = plan["role"], plan["access"]
                    member.membership_source = "manual"
        await session.flush()
    summary = ImportSummary(
        create=sum(1 for r in report if r.action == "create"),
        update=sum(1 for r in report if r.action == "update"),
        error=sum(1 for r in report if r.action == "error"),
    )
    return ImportReport(dry_run=dry_run, summary=summary, rows=report)
