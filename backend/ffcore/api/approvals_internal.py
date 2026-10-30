"""`POST /api/v1/internal/approvals/sweep` (FOLLOWUP-111): a test hook for the approval TTL.

The background worker expires approvals once a minute (`services.approvals.sweep`, arq cron).
An end-to-end test cannot wait the TTL (60 minutes) and cannot shorten it without changing the
other flows, so it runs the same sweep with a chosen `now`. The hook exists only when
`FFCORE_TEST_HOOKS=1`; otherwise the path answers like any unknown path (404), before any
identity check. Service account only; not in the OpenAPI contract (docs/onaylar.md). Repeating
a call changes nothing more: the sweep's changes are conditional.
"""

import logging
from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from starlette.exceptions import HTTPException

from ffcore.api.common import ERROR_RESPONSES, invalid
from ffcore.api.internal import ServiceActor
from ffcore.api.schemas import Strict
from ffcore.core.config import Settings, get_settings
from ffcore.services import approvals

log = logging.getLogger("ffcore.approvals")
router = APIRouter(tags=["approvals"], responses=ERROR_RESPONSES)
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def test_hooks_on(settings: SettingsDep) -> None:
    if not settings.ffcore_test_hooks:
        raise HTTPException(404)


class SweepResult(Strict):
    expired: list[UUID]


@router.post(
    "/internal/approvals/sweep",
    response_model=SweepResult,
    include_in_schema=False,
    dependencies=[Depends(test_hooks_on)],
)
async def sweep_approvals(
    actor: ServiceActor,
    settings: SettingsDep,
    now: Annotated[datetime | None, Query(description="ISO 8601 with a time zone")] = None,
):
    if now is not None and now.tzinfo is None:
        raise invalid("now_without_timezone", "`now` needs a time zone (ISO 8601, e.g. Z).")
    log.warning("approvals_sweep_hook now=%s", now.isoformat() if now else "server")
    expired = await approvals.sweep(settings, now=now)
    return SweepResult(expired=[row.id for row in expired])
