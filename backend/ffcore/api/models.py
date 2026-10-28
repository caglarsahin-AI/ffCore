"""Model catalog (static, read only) and project models."""

from uuid import UUID

from fastapi import APIRouter

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.schemas import (
    CatalogList,
    ModelCreate,
    ModelList,
    ModelOut,
    ModelUpdate,
    ProviderDriver,
)

router = APIRouter(tags=["models"], responses=ERROR_RESPONSES)


@router.get("/model-catalog", response_model=CatalogList, summary="Static model catalog")
async def list_catalog(driver: ProviderDriver | None = None, model_id: str | None = None):
    """Used by "fill from catalog". An empty result means the model is not in the catalog."""
    raise not_implemented()


@router.get("/projects/{project_id}/models", response_model=ModelList, summary="List models")
async def list_models(project_id: UUID):
    raise not_implemented()


@router.post(
    "/projects/{project_id}/models",
    response_model=ModelOut,
    status_code=201,
    summary="Register a model",
)
async def create_model(project_id: UUID, body: ModelCreate):
    """Embedding models: `embed_dim` is measured through the provider and must equal EMBED_DIM
    (400 `embed_dim_mismatch`); 409 `embedding_probe_unavailable` if it cannot be measured."""
    raise not_implemented()


@router.get(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Get a model"
)
async def get_model(project_id: UUID, model_id: UUID):
    raise not_implemented()


@router.patch(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Update a model"
)
async def update_model(project_id: UUID, model_id: UUID, body: ModelUpdate):
    raise not_implemented()


@router.delete(
    "/projects/{project_id}/models/{model_id}",
    status_code=204,
    summary="Delete a model (soft delete)",
)
async def delete_model(project_id: UUID, model_id: UUID) -> None:
    raise not_implemented()
