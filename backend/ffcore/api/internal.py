"""Internal endpoints for the service account (SERVICE_TOKEN) only; not under /api/v1.

`POST /internal/embed`: the ingest worker gets embeddings from the API process, which is the
only process that loads the embedding model (brief 04 step 8, C10).
`POST /internal/knowledge-bases/{kb_id}/key-search` (06b): a run whose actor is an API key.
"""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ffcore.api.common import ERROR_RESPONSES
from ffcore.api.knowledge import _kb, _vector_error
from ffcore.api.knowledge_schemas import EmbedRequest, EmbedResponse, SearchHit, SearchResponse
from ffcore.core import db
from ffcore.core.auth import ROLE_ORDER, Actor, resolve_actor
from ffcore.core.config import Settings, get_settings
from ffcore.core.errors import ApiError
from ffcore.knowledge import jobs, search
from ffcore.knowledge.embed import embed
from ffcore.knowledge.vectorstore.base import VectorFilters, VectorStoreError
from ffcore.models.identity import Project
from ffcore.models.keys import ApiKey
from ffcore.models.runs import Run

router = APIRouter(prefix="/internal", tags=["internal"], responses=ERROR_RESPONSES)
# 06b: its own tag, so 04a's OpenAPI draft (and the console's types made from it) stays as is.
facade_router = APIRouter(prefix="/internal", tags=["facade-internal"], responses=ERROR_RESPONSES)


async def service_actor(actor: Annotated[Actor, Depends(resolve_actor)]) -> Actor:
    if not (actor.actor_type == "system" and actor.actor_id == "service"):
        raise ApiError(403, "permission_error", "service_account_required", "Internal endpoint.")
    return actor


ServiceActor = Annotated[Actor, Depends(service_actor)]


@router.post("/embed", response_model=EmbedResponse)
async def internal_embed(
    body: EmbedRequest,
    actor: ServiceActor,
    settings: Annotated[Settings, Depends(get_settings)],
):
    result = await embed(settings, body.texts)
    return EmbedResponse(
        model=settings.embed_model,
        dim=settings.embed_dim,
        dense=result.dense,
        sparse=[{str(k): v for k, v in weights.items()} for weights in result.sparse],
        truncated=result.truncated,
    )


# --- 06b (S2, K-06b-0002): a run whose actor is an API key searches with the key's acl_role ---


class KeySearchRequest(BaseModel):
    # Unknown fields are ignored, never read: the role comes from the key row only.
    model_config = ConfigDict(extra="ignore")

    api_key_id: UUID
    project_id: UUID
    run_id: UUID | None = None
    query: str = Field(min_length=1, max_length=2000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    hybrid: bool | None = None


def _key_refused() -> ApiError:
    return ApiError(
        403, "permission_error", "api_key_not_valid", "The API key may not search this project."
    )


@facade_router.post("/knowledge-bases/{kb_id}/key-search", response_model=SearchResponse)
async def internal_key_search(
    kb_id: UUID,
    body: KeySearchRequest,
    actor: ServiceActor,
    session: Annotated[AsyncSession, Depends(db.get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """The worker's search for a run started by an API key without a user (06b, B7): ACL is
    the key's `acl_role` and every role below it, read here from the key row. The key is checked
    again (revoked, expired, its project, the run's own key), not trusted from the caller."""
    now = datetime.now(UTC)
    key = await session.scalar(
        select(ApiKey)
        .join(Project, Project.id == ApiKey.project_id)
        .where(
            ApiKey.id == body.api_key_id,
            ApiKey.project_id == body.project_id,
            ApiKey.deleted_at.is_(None),
            ApiKey.revoked_at.is_(None),
            Project.deleted_at.is_(None),
        )
    )
    if key is None or (key.expires_at is not None and key.expires_at <= now):
        raise _key_refused()
    if body.run_id is not None:
        run_key = await session.scalar(
            select(Run.api_key_id).where(Run.id == body.run_id, Run.project_id == body.project_id)
        )
        if run_key != key.id:
            raise _key_refused()
    kb = await _kb(session, body.project_id, kb_id)
    roles = ROLE_ORDER[: ROLE_ORDER.index(key.acl_role) + 1]
    try:
        result = await search.search(
            session,
            kb,
            body.query,
            filters=VectorFilters(acl_roles=tuple(roles), acl_users=()),
            top_k=body.top_k,
            hybrid=body.hybrid,
            run_id=body.run_id,
            user_id=f"api_key:{key.id}",
            source="api",
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
