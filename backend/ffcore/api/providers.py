"""Providers (tenant level, superadmin) and their connection test."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from ffcore.api.common import ERROR_RESPONSES, not_implemented
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
from ffcore.core.auth import Actor, require_superadmin

router = APIRouter(tags=["providers"], responses=ERROR_RESPONSES)

Reader = Annotated[Actor, Depends(require_superadmin())]
Writer = Annotated[Actor, Depends(require_superadmin(write=True))]


@router.get("/provider-drivers", response_model=DriverList, summary="Drivers and their fields")
async def list_drivers(actor: Reader):
    raise not_implemented()


@router.get("/providers", response_model=ProviderList, summary="List providers")
async def list_providers(actor: Reader):
    raise not_implemented()


@router.post("/providers", response_model=ProviderOut, status_code=201, summary="Add a provider")
async def create_provider(body: ProviderCreate, actor: Writer):
    """The configuration is stored encrypted; secret fields are never returned."""
    raise not_implemented()


@router.post(
    "/providers/test", response_model=ProviderTestResult, summary="Test a configuration unsaved"
)
async def test_provider_config(body: ProviderTestRequest, actor: Writer):
    """A failed test does not block saving. Drivers without a test return supported=false."""
    raise not_implemented()


@router.get("/providers/{provider_id}", response_model=ProviderOut, summary="Get a provider")
async def get_provider(provider_id: UUID, actor: Reader):
    raise not_implemented()


@router.patch("/providers/{provider_id}", response_model=ProviderOut, summary="Update a provider")
async def update_provider(provider_id: UUID, body: ProviderUpdate, actor: Writer):
    raise not_implemented()


@router.delete("/providers/{provider_id}", status_code=204, summary="Deactivate a provider")
async def delete_provider(provider_id: UUID, actor: Writer) -> None:
    """409 `provider_in_use` while a model uses it."""
    raise not_implemented()


@router.put(
    "/providers/{provider_id}/projects",
    response_model=ProviderOut,
    summary="Replace the projects a provider is assigned to",
)
async def set_provider_projects(provider_id: UUID, body: ProviderProjectsUpdate, actor: Writer):
    raise not_implemented()


@router.post(
    "/providers/{provider_id}/test",
    response_model=ProviderTestResult,
    summary="Test the stored configuration",
)
async def test_provider(provider_id: UUID, actor: Writer):
    raise not_implemented()
