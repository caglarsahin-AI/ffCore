"""Providers (tenant level, superadmin) and their connection test."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select

from ffcore.api.common import (
    ERROR_RESPONSES,
    SessionDep,
    conflict,
    invalid,
    not_found,
    path_resource,
)
from ffcore.api.schemas import (
    DriverList,
    ProviderCreate,
    ProviderList,
    ProviderOut,
    ProviderProjectsUpdate,
    ProviderTestRequest,
    ProviderTestResult,
    ProviderUpdate,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_superadmin
from ffcore.core.config import Settings, get_settings
from ffcore.core.secrets import decrypt_json, encrypt_json
from ffcore.models.catalog import Model, Provider, ProviderProject
from ffcore.models.identity import Project
from ffcore.services import providers as drivers
from ffcore.services.catalog_events import CatalogChanged, publish_on_commit

router = APIRouter(tags=["providers"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_superadmin())]
Writer = Annotated[Actor, Depends(require_superadmin(write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ProviderIdDep = Annotated[str, Depends(path_resource("provider_id"))]


async def _project_ids(session, provider_id: UUID) -> list[UUID]:
    rows = await session.scalars(
        select(ProviderProject.project_id)
        .where(ProviderProject.provider_id == provider_id)
        .order_by(ProviderProject.project_id)
    )
    return list(rows)


async def provider_out(session, provider: Provider, settings: Settings) -> ProviderOut:
    config = decrypt_json(provider.config_encrypted, settings)
    return ProviderOut(
        id=provider.id,
        key=provider.key,
        label=provider.label,
        description=provider.description,
        driver=provider.driver,
        domains=provider.domains,
        config=drivers.mask_config(provider.driver, config),
        supports_test=provider.supports_test,
        is_active=provider.is_active,
        project_ids=await _project_ids(session, provider.id),
        created_by=provider.created_by,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


async def _get(session, provider_id: UUID) -> Provider:
    provider = await session.get(Provider, provider_id)
    if provider is None:
        raise not_found("provider")
    return provider


async def _before(session, provider_id: UUID, settings: Settings, **_) -> ProviderOut:
    return await provider_out(session, await _get(session, provider_id), settings)


async def _ensure_unused(session, provider_id: UUID) -> None:
    """Deactivation (DELETE or PATCH is_active=false) waits until no active model uses the
    provider: otherwise those models would break silently at call time (ARCH-06)."""
    used = await session.scalar(
        select(Model.id).where(
            Model.provider_id == provider_id, Model.deleted_at.is_(None), Model.is_active
        )
    )
    if used is not None:
        raise conflict(
            "provider_in_use", "An active model uses this provider; deactivate the model first."
        )


async def _assign(session, provider_id: UUID, project_ids: list[UUID]) -> None:
    wanted = set(project_ids)
    live = set(
        await session.scalars(
            select(Project.id).where(Project.id.in_(wanted), Project.deleted_at.is_(None))
        )
    )
    if live != wanted:
        raise invalid("unknown_project", "Every project must exist.")
    in_use = set(
        await session.scalars(
            select(Model.project_id).where(
                Model.provider_id == provider_id,
                Model.deleted_at.is_(None),
                Model.project_id.not_in(wanted),
            )
        )
    )
    if in_use:
        raise conflict("provider_in_use", "Models of a removed project still use this provider.")
    await session.execute(delete(ProviderProject).where(ProviderProject.provider_id == provider_id))
    session.add_all(ProviderProject(provider_id=provider_id, project_id=p) for p in wanted)
    await session.flush()


@router.get("/provider-drivers", response_model=DriverList, summary="Drivers and their fields")
async def list_drivers(actor: Reader):
    return DriverList(data=drivers.specs())


@router.get("/providers", response_model=ProviderList, summary="List providers")
async def list_providers(actor: Reader, session: SessionDep, settings: SettingsDep):
    rows = await session.scalars(select(Provider).order_by(Provider.key))
    return ProviderList(data=[await provider_out(session, p, settings) for p in rows])


@router.post("/providers", response_model=ProviderOut, status_code=201, summary="Add a provider")
@audited("create_provider", "provider")
async def create_provider(
    body: ProviderCreate,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
):
    """The configuration is stored encrypted; secret fields are never returned."""
    drivers.validate_domains(body.driver, body.domains)
    config = drivers.validate_config(body.driver, body.config)
    if await session.scalar(select(Provider.id).where(Provider.key == body.key)) is not None:
        raise conflict("provider_key_taken", "This provider key is already used.")
    provider = Provider(
        key=body.key,
        label=body.label,
        description=body.description,
        driver=body.driver,
        domains=list(body.domains),
        config_encrypted=encrypt_json(config, settings),
        supports_test=drivers.driver(body.driver).test_call is not None,
        is_active=body.is_active,
        created_by=actor.actor_id,
    )
    session.add(provider)
    await session.flush()
    await _assign(session, provider.id, body.project_ids)
    await session.refresh(provider)
    publish_on_commit(session, CatalogChanged("provider", "created", str(provider.id)))
    return await provider_out(session, provider, settings)


@router.post(
    "/providers/test", response_model=ProviderTestResult, summary="Test a configuration unsaved"
)
@audited("test_provider_config", "provider")
async def test_provider_config(
    body: ProviderTestRequest,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
):
    """A failed test does not block saving. Drivers without a test return supported=false."""
    config = drivers.validate_config(body.driver, body.config)
    return await drivers.test_connection(body.driver, config, settings)


@router.get("/providers/{provider_id}", response_model=ProviderOut, summary="Get a provider")
async def get_provider(
    provider_id: UUID, actor: Reader, session: SessionDep, settings: SettingsDep
):
    return await provider_out(session, await _get(session, provider_id), settings)


@router.patch("/providers/{provider_id}", response_model=ProviderOut, summary="Update a provider")
@audited("update_provider", "provider", load_before=_before)
async def update_provider(
    provider_id: UUID,
    body: ProviderUpdate,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
):
    provider = await _get(session, provider_id)
    changes = body.model_dump(exclude_unset=True)
    if "domains" in changes:
        drivers.validate_domains(provider.driver, changes["domains"])
    if "config" in changes:
        stored = decrypt_json(provider.config_encrypted, settings)
        merged = drivers.merge_config(provider.driver, stored, changes.pop("config"))
        provider.config_encrypted = encrypt_json(merged, settings)
    if changes.get("is_active") is False and provider.is_active:
        await _ensure_unused(session, provider_id)  # same rule as DELETE (review r1 MAJOR-3)
    for field, value in changes.items():
        setattr(provider, field, value)
    await session.flush()
    await session.refresh(provider)
    publish_on_commit(session, CatalogChanged("provider", "updated", str(provider.id)))
    return await provider_out(session, provider, settings)


@router.delete("/providers/{provider_id}", status_code=204, summary="Deactivate a provider")
@audited("delete_provider", "provider", load_before=_before)
async def delete_provider(
    provider_id: UUID,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ProviderIdDep,
) -> None:
    """409 `provider_in_use` while a model uses it."""
    provider = await _get(session, provider_id)
    await _ensure_unused(session, provider_id)
    provider.is_active = False
    publish_on_commit(session, CatalogChanged("provider", "deleted", str(provider.id)))


@router.put(
    "/providers/{provider_id}/projects",
    response_model=ProviderOut,
    summary="Replace the projects a provider is assigned to",
)
@audited("set_provider_projects", "provider", load_before=_before)
async def set_provider_projects(
    provider_id: UUID,
    body: ProviderProjectsUpdate,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
):
    provider = await _get(session, provider_id)
    await _assign(session, provider.id, body.project_ids)
    publish_on_commit(session, CatalogChanged("provider_projects", "updated", str(provider.id)))
    return await provider_out(session, provider, settings)


@router.post(
    "/providers/{provider_id}/test",
    response_model=ProviderTestResult,
    summary="Test the stored configuration",
)
@audited("test_provider", "provider")
async def test_provider(
    provider_id: UUID,
    request: Request,
    actor: Writer,
    session: SessionDep,
    settings: SettingsDep,
    resource_id: ProviderIdDep,
):
    provider = await _get(session, provider_id)
    config = decrypt_json(provider.config_encrypted, settings)
    return await drivers.test_connection(provider.driver, config, settings)
