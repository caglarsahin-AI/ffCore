"""Model catalog (static, read only) and project models."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import (
    CatalogList,
    ModelCreate,
    ModelList,
    ModelOut,
    ModelUpdate,
    ProviderDriver,
)
from ffcore.core.auth import Actor, require_role, require_superadmin

router = APIRouter(tags=["models"], responses=ERROR_RESPONSES)

CatalogReader = Annotated[Actor, Depends(require_superadmin())]
ProjectReader = Annotated[Actor, Depends(require_role("analyst"))]
ProjectAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]


@router.get("/model-catalog", response_model=CatalogList, summary="Static model catalog")
async def list_catalog(
    actor: CatalogReader, driver: ProviderDriver | None = None, model_id: str | None = None
):
    """Used by "fill from catalog". An empty result means the model is not in the catalog."""
    raise not_implemented()


@router.get("/projects/{project_id}/models", response_model=ModelList, summary="List models")
async def list_models(project_id: UUID, actor: ProjectReader):
    raise not_implemented()


@router.post(
    "/projects/{project_id}/models",
    response_model=ModelOut,
    status_code=201,
    summary="Register a model",
)
async def create_model(project_id: UUID, body: ModelCreate, actor: ProjectAdmin):
    """Embedding models: `embed_dim` is measured through the provider and must equal EMBED_DIM
    (400 `embed_dim_mismatch`); 409 `embedding_probe_unavailable` if it cannot be measured."""
    raise not_implemented()


@router.get(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Get a model"
)
async def get_model(project_id: UUID, model_id: UUID, actor: ProjectReader):
    raise not_implemented()


@router.patch(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Update a model"
)
async def update_model(project_id: UUID, model_id: UUID, body: ModelUpdate, actor: ProjectAdmin):
    raise not_implemented()


@router.delete(
    "/projects/{project_id}/models/{model_id}",
    status_code=204,
    summary="Delete a model (soft delete)",
)
async def delete_model(project_id: UUID, model_id: UUID, actor: ProjectAdmin) -> None:
    raise not_implemented()
