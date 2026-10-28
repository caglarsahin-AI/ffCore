"""Model catalog (static, read only) and project models."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

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
    CatalogEntryOut,
    CatalogList,
    ModelCreate,
    ModelList,
    ModelOut,
    ModelUpdate,
    ProviderDriver,
)
from ffcore.core.audit import audited
from ffcore.core.auth import Actor, require_role
from ffcore.core.config import Settings, get_settings
from ffcore.core.secrets import decrypt_json
from ffcore.models.catalog import Model, ModelCatalogEntry, Provider, ProviderProject, litellm_name
from ffcore.models.identity import Project
from ffcore.services import providers as drivers
from ffcore.services.catalog_events import CatalogChanged, publish_on_commit

router = APIRouter(tags=["models"], responses=ERROR_RESPONSES)

# The catalog is static and holds no secrets: any signed-in user may read it.
CatalogReader = Annotated[Actor, Depends(user_actor)]
ProjectReader = Annotated[Actor, Depends(require_role("analyst"))]
ProjectAdmin = Annotated[Actor, Depends(require_role("admin", write=True))]
SettingsDep = Annotated[Settings, Depends(get_settings)]
ModelIdDep = Annotated[str, Depends(path_resource("model_id"))]


def _domain(category: str) -> str:
    return "embedding" if category == "embedding" else "model"


def model_out(model: Model, project_key: str) -> ModelOut:
    data = {c.key: getattr(model, c.key) for c in Model.__table__.columns}
    return ModelOut(**data, litellm_name=litellm_name(project_key, model.key))


async def _project_key(session, project_id: UUID) -> str:
    key = await session.scalar(select(Project.key).where(Project.id == project_id))
    if key is None:
        raise not_found("project")
    return key


async def _get(session, project_id: UUID, model_id: UUID) -> Model:
    model = await session.scalar(
        select(Model).where(
            Model.id == model_id, Model.project_id == project_id, Model.deleted_at.is_(None)
        )
    )
    if model is None:
        raise not_found("model")
    return model


async def _before(session, project_id: UUID, model_id: UUID, **_) -> ModelOut:
    return model_out(
        await _get(session, project_id, model_id), await _project_key(session, project_id)
    )


async def _provider_for(session, project_id: UUID, provider_id: UUID, category: str) -> Provider:
    provider = await session.scalar(
        select(Provider)
        .join(ProviderProject, ProviderProject.provider_id == Provider.id)
        .where(Provider.id == provider_id, ProviderProject.project_id == project_id)
    )
    if provider is None or not provider.is_active:
        raise invalid("provider_not_assigned", "The provider is not active in this project.")
    if _domain(category) not in provider.domains:
        raise invalid("provider_domain_mismatch", f"The provider does not serve {category} models.")
    return provider


async def _embed_dim(provider: Provider, model_id: str, settings: Settings) -> int:
    config = decrypt_json(provider.config_encrypted, settings)
    return await drivers.measure_embed_dim(provider.driver, config, model_id, settings)


def _event(action: str, model: Model) -> CatalogChanged:
    return CatalogChanged(
        "model",
        action,
        str(model.id),
        project_id=str(model.project_id),
        litellm=model.category != "embedding",  # embeddings run in process (C10 reversed)
    )


@router.get("/model-catalog", response_model=CatalogList, summary="Static model catalog")
async def list_catalog(
    actor: CatalogReader,
    session: SessionDep,
    driver: ProviderDriver | None = None,
    model_id: str | None = None,
):
    """Used by "fill from catalog". An empty result means the model is not in the catalog."""
    query = select(ModelCatalogEntry).order_by(ModelCatalogEntry.driver, ModelCatalogEntry.model_id)
    if driver is not None:
        query = query.where(ModelCatalogEntry.driver == driver.value)
    if model_id is not None:
        query = query.where(ModelCatalogEntry.model_id == model_id)
    rows = await session.scalars(query)
    return CatalogList(data=[CatalogEntryOut.model_validate(r, from_attributes=True) for r in rows])


@router.get("/projects/{project_id}/models", response_model=ModelList, summary="List models")
async def list_models(project_id: UUID, actor: ProjectReader, session: SessionDep):
    key = await _project_key(session, project_id)
    rows = await session.scalars(
        select(Model)
        .where(Model.project_id == project_id, Model.deleted_at.is_(None))
        .order_by(Model.key)
    )
    return ModelList(data=[model_out(m, key) for m in rows])


@router.post(
    "/projects/{project_id}/models",
    response_model=ModelOut,
    status_code=201,
    summary="Register a model",
)
@audited("create_model", "model")
async def create_model(
    project_id: UUID,
    body: ModelCreate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    """Embedding models: `embed_dim` is measured through the provider and must equal EMBED_DIM
    (400 `embed_dim_mismatch`); 409 `embedding_probe_unavailable` if it cannot be measured."""
    key = await _project_key(session, project_id)
    provider = await _provider_for(session, project_id, body.provider_id, body.category)
    taken = await session.scalar(
        select(Model.id).where(
            Model.project_id == project_id, Model.key == body.key, Model.deleted_at.is_(None)
        )
    )
    if taken is not None:
        raise conflict("model_key_taken", "This model key is already used in the project.")
    embed_dim = None
    if body.category == "embedding":
        embed_dim = await _embed_dim(provider, body.model_id, settings)
    model = Model(
        **body.model_dump(mode="json", exclude={"provider_id"}),
        provider_id=body.provider_id,
        project_id=project_id,
        embed_dim=embed_dim,
        created_by=actor.actor_id,
    )
    session.add(model)
    await session.flush()
    await session.refresh(model)
    publish_on_commit(session, _event("created", model))
    return model_out(model, key)


@router.get(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Get a model"
)
async def get_model(project_id: UUID, model_id: UUID, actor: ProjectReader, session: SessionDep):
    model = await _get(session, project_id, model_id)
    return model_out(model, await _project_key(session, project_id))


@router.patch(
    "/projects/{project_id}/models/{model_id}", response_model=ModelOut, summary="Update a model"
)
@audited("update_model", "model", load_before=_before)
async def update_model(
    project_id: UUID,
    model_id: UUID,
    body: ModelUpdate,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    settings: SettingsDep,
):
    model = await _get(session, project_id, model_id)
    changes = body.model_dump(mode="json", exclude_unset=True)
    category = changes.get("category", model.category)
    provider = await _provider_for(session, project_id, model.provider_id, category)
    if category == "embedding" and ({"category", "model_id"} & changes.keys()):
        model.embed_dim = await _embed_dim(
            provider, changes.get("model_id", model.model_id), settings
        )
    elif category != "embedding":
        model.embed_dim = None
    for field, value in changes.items():
        setattr(model, field, value)
    await session.flush()
    await session.refresh(model)
    publish_on_commit(session, _event("updated", model))
    return model_out(model, await _project_key(session, project_id))


@router.delete(
    "/projects/{project_id}/models/{model_id}",
    status_code=204,
    summary="Delete a model (soft delete)",
)
@audited("delete_model", "model", load_before=_before)
async def delete_model(
    project_id: UUID,
    model_id: UUID,
    request: Request,
    actor: ProjectAdmin,
    session: SessionDep,
    resource_id: ModelIdDep,
) -> None:
    model = await _get(session, project_id, model_id)
    model.deleted_at = func.now()
    publish_on_commit(session, _event("deleted", model))
