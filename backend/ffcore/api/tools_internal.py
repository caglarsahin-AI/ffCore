"""`POST /api/v1/internal/obo/verify` (05a review r1 MAJOR-1; KARARLAR "05a review r1
kararları" item 2), service account only.

FFCore's MCP services relay the caller's token and hold no signing key (K-05a-0002 S3). A
service that acts on the caller's identity itself (mcp-sql runs queries) asks here first:
signature, the audience it names (its own tool key) and lifetime, the same check as
resolve_actor. The answer is the verified claims; a refusal is 401 invalid_token /
token_expired / token_lifetime_exceeded or 403 audience_mismatch.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import Field

from ffcore.api.common import ERROR_RESPONSES
from ffcore.api.internal import ServiceActor
from ffcore.api.schemas import Strict
from ffcore.api.tools_schemas import ToolKey
from ffcore.core.auth import verify_on_behalf_of
from ffcore.core.config import Settings, get_settings

router = APIRouter(tags=["tools"], responses=ERROR_RESPONSES)


class OboVerifyRequest(Strict):
    token: Annotated[str, Field(min_length=1, max_length=4096, description="X-On-Behalf-Of JWT")]
    audience: Annotated[ToolKey, Field(description="The asking service's own tool key.")]


class OboVerifyResult(Strict):
    sub: str
    project_id: str
    exp: int
    jti: str


@router.post(
    "/internal/obo/verify", response_model=OboVerifyResult, summary="Verify an on-behalf-of token"
)
async def verify_obo(
    body: OboVerifyRequest,
    actor: ServiceActor,
    settings: Annotated[Settings, Depends(get_settings)],
):
    claims = verify_on_behalf_of(body.token, audience=body.audience, settings=settings)
    return OboVerifyResult(
        sub=claims.sub, project_id=claims.project_id, exp=claims.exp, jti=claims.jti
    )
