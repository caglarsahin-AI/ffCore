"""Internal endpoints for the service account (SERVICE_TOKEN) only; not under /api/v1.

`POST /internal/embed`: the ingest worker gets embeddings from the API process, which is the
only process that loads the embedding model (brief 04 step 8, C10).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from ffcore.api.common import ERROR_RESPONSES, not_implemented
from ffcore.api.knowledge_schemas import EmbedRequest, EmbedResponse
from ffcore.core.auth import Actor, resolve_actor
from ffcore.core.errors import ApiError

router = APIRouter(prefix="/internal", tags=["internal"], responses=ERROR_RESPONSES)


async def service_actor(actor: Annotated[Actor, Depends(resolve_actor)]) -> Actor:
    if not (actor.actor_type == "system" and actor.actor_id == "service"):
        raise ApiError(403, "permission_error", "service_account_required", "Internal endpoint.")
    return actor


ServiceActor = Annotated[Actor, Depends(service_actor)]


@router.post("/embed", response_model=EmbedResponse)
async def internal_embed(body: EmbedRequest, actor: ServiceActor):
    raise not_implemented()
