"""Readiness (`GET /readyz`) and model warmup (04a, moved from 00).

`/healthz` says the process is up; `/readyz` says it can serve: models warmed, configuration
consistent. Every failing check is named with a code; nothing is reported ready by default.
"""

from fastapi import APIRouter, status

from ffcore.api.common import not_implemented
from ffcore.knowledge.schemas import ReadyzOut

router = APIRouter(tags=["readiness"])


@router.get(
    "/readyz",
    response_model=ReadyzOut,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadyzOut}},
)
async def readyz():
    """200 when every check is ok or skipped; 503 with the same body otherwise
    (codes: warming, context_configuration_invalid, embed_dim_mismatch, ...)."""
    raise not_implemented()
