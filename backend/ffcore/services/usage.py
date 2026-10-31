"""usage_daily (03c): reporting rows, one per project, UTC day, model, API key and user.

Written once per finished model call by the quota gate (K-03c-0008, decision A): LiteLLM's spend
log carries neither our API key id nor a cost for streamed calls (U1/U2), so the backend records
what it decided on. Budgets are never read from here (C20: Redis). A call on a model without a
price adds to `unpriced_requests`, not to a cost of 0 (FOLLOWUP-69). A failed write never breaks
the call; it is logged `usage_write_failed` and counted in Redis (`USAGE_WRITE_FAILED_KEY`).
"""

import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import text

from ffcore.core import db

log = logging.getLogger("ffcore.usage")

USAGE_WRITE_FAILED_KEY = "ffcore:usage:write_failed"
NO_KEY = uuid.UUID(int=0)

_UPSERT = text(
    """
    INSERT INTO usage_daily (project_id, date, model, api_key_id, user_id, input_tokens,
        output_tokens, cost_usd, requests, unpriced_requests)
    VALUES (:project_id, :date, :model, :api_key_id, :user_id, :input_tokens, :output_tokens,
        :cost_usd, 1, :unpriced)
    ON CONFLICT (project_id, date, model,
        coalesce(api_key_id, '00000000-0000-0000-0000-000000000000'::uuid), coalesce(user_id, ''))
    DO UPDATE SET input_tokens = usage_daily.input_tokens + EXCLUDED.input_tokens,
        output_tokens = usage_daily.output_tokens + EXCLUDED.output_tokens,
        cost_usd = usage_daily.cost_usd + EXCLUDED.cost_usd,
        requests = usage_daily.requests + 1,
        unpriced_requests = usage_daily.unpriced_requests + EXCLUDED.unpriced_requests,
        updated_at = now()
    """
)


async def record(
    *,
    project_id,
    model: str,
    api_key_id,
    user_id,
    input_tokens: int,
    output_tokens: int,
    cost_usd: Decimal | None,
    day: date | None = None,
    redis=None,
) -> bool:
    """One finished call. Returns False (and counts the loss) when the row could not be
    written; never raises."""
    try:
        async with db.session_scope() as session:
            await session.execute(
                _UPSERT,
                {
                    "project_id": uuid.UUID(str(project_id)),
                    "date": day or datetime.now(UTC).date(),
                    "model": model,
                    "api_key_id": uuid.UUID(str(api_key_id)) if api_key_id else None,
                    "user_id": str(user_id) if user_id else None,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost_usd if cost_usd is not None else Decimal(0),
                    "unpriced": 0 if cost_usd is not None else 1,
                },
            )
            await session.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - reporting must not break the call; loss is counted
        log.error(
            "usage_write_failed project_id=%s model=%s error=%s",
            project_id,
            model,
            type(exc).__name__,
        )
        if redis is not None:
            try:
                await redis.incr(USAGE_WRITE_FAILED_KEY)
            except Exception:  # noqa: BLE001
                log.error("usage_write_failed_count_lost")
        return False
